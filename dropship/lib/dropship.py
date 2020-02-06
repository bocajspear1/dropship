import json
import shutil 
import importlib
import time
import os

import logging
logger = logging.getLogger('dropship')

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import dropship.constants

from dropship.lib.proxmox import ProxmoxProvider
from dropship.lib.dnsmasq import DropshipDNSMasq
from dropship.lib.network import DropshipNetwork


class Dropship():
    
    def __init__(self, provider_name, config_path, module_path="./modules"):
        if provider_name not in ["proxmox"]:
            raise ValueError("Provider '{}' not supported".format(provider_name))
        
        self._provider_name = provider_name
        self._config_path = config_path
        self._module_path = module_path
        self.networks = []
        self.routers = []

        self._router_map = {
            "EXTERNAL": []
        }
        
        self._module_cache = {}

        # TODO

        self.config = json.load(open(config_path, "r"))

        self.provider = ProxmoxProvider(self.config['proxmox'], self.config['vm_map'])
        self.dnsmasq = DropshipDNSMasq(self.config['bootstrap'])

    def get_module(self, module_name):
        if module_name in self._module_cache:
            return self._module_cache[self._module_cache]

        module_split = module_name.split(".")
        category = module_split[0]
        name = module_split[1]

        start = self._module_path.replace("./", "").replace("/", ".")

        temp = importlib.import_module(start + "." + category + "." + name)

        module = temp.__MODULE__()

        self._module_cache[module_name] = module

        return module

    def add_network(self, name, switch_id, ip_range):
        net = DropshipNetwork(self, name, switch_id, ip_range)
        self.networks.append(net)
        return net

    def add_router(self, router_name, template):
        self.routers.append({
            "template": template,
            "router_name": router_name,
            "connections": [],
            "vmid": 0
        })

    def connect_router(self, router_name, network_name):
        for i in range(len(self.routers)):
            router = self.routers[i]
            if router['router_name'] == router_name:
                self.routers[i]['connections'].append(network_name)
                if network_name not in self._router_map:
                    self._router_map[network_name] = []
                self._router_map[network_name].append(router['router_name'])
                return
        raise ValueError("Invalid router")

    def connect(self, username, password):
        self.provider.connect(username, password)

    # Create the Ansible files
    def bootstrap(self):
        self.dnsmasq.start()

        
        if not os.path.exists(dropship.constants.OutDir):
            os.mkdir(dropship.constants.OutDir)

        # Bootstrap the routers
        self._bootstrap_routers()
        



        for network in self.networks:
            network.bootstrap()

    def get_address_map(self, mac_list):
        out_map = {}

        done = False
        counter = 0

        while not done and counter < 300:
            for mac in mac_list:
                if mac not in out_map:
                    ip_addr = self.dnsmasq.get_ip_by_mac(mac)
                    if ip_addr is not None:
                        out_map[mac] = ip_addr
            
            if len(out_map.keys()) == len(mac_list):
                done = True

            counter += 1
            logger.info("Waiting for DHCP to assign addresses...")
            time.sleep(5)

        return out_map

    def _get_router_by_name(self, router_name):
        for router in self.routers:
            if router['router_name'] == router_name:
                return router
        return None

    def _get_network_by_name(self, network_name):
        for net in self.networks:
            if net.name == network_name:
                return net
        return None

    def get_template_credentials(self, template_name):
        if template_name in self.config['credentials']:
            cred_split = self.config['credentials'][template_name].split(":")
            return cred_split[0], cred_split[1]
        else:
            return None, None

    def _bootstrap_routers(self):
        logger.info("Bootstrapping routers...")
        # Prepare router directory
        router_dir = dropship.constants.OutDir + "/routers/"
        if not os.path.exists(router_dir):
            os.mkdir(router_dir)

        router_state_file = router_dir + "router_addr.state"

        # Check for existing state file so we don't clone again
        if not os.path.exists(router_state_file):

            
            # Clone out the necessary templates
            logger.info("Cloning routers...")
            for i in range(len(self.routers)):
                router = self.routers[i]
                template = router['template']
                router_name = router['router_name']
                display_name = "{}".format(router_name)
                vmid = self.provider.clone_vm(template, display_name)
                if vmid == 0:
                    return False
                self.routers[i]['vmid'] = vmid

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            self.provider.wait()
            
            mac_list = []
            vm_mac_map = {}

            logger.info("Configuring and starting routers...")
            for i in range(len(self.routers)):
                vmid = self.routers[i]['vmid']
                router_name = self.routers[i]['router_name']
                bootstrap_switch = self.config['bootstrap']['switch']
                # For first round addressing
                self.provider.set_interface(vmid, 0, bootstrap_switch)

                # While we are here, get the mac address for this interface
                mac_addr = self.provider.get_interface(vmid, 0)['mac'].lower()
                vm_mac_map[router_name] = mac_addr
                mac_list.append(mac_addr)

                # For second round addressing
                self.provider.set_interface(vmid, 1, bootstrap_switch)
                time.sleep(1)
                self.provider.start_vm(vmid)

            # Get IP mappings
            mac_map = self.get_address_map(mac_list)

            # Write a state file
            state_file = open(router_state_file, "w+")
            for i in range(len(self.routers)):
                router = self.routers[i]
                template = router['template']
                router_name = router['router_name']
                vmid = router['vmid']
                mac_addr = vm_mac_map[router_name]
                ip_addr = mac_map[mac_addr]
                state_file.write("{}|{}|{}|{}\n".format(router_name, vmid, mac_addr, ip_addr))
            state_file.close()
        else:
            logger.info("Using existing router state file")

        logger.info("Generating router inventory file...")

        # Load from state file
        state_file = state_file = open(router_state_file, "r")
        state_data = state_file.readlines()
        state_file.close()

        router_inv = {
            "all": {
                "children": {}
            }
        }

        router_groups = []

        for line in state_data:
            line_split = line.strip().split("|")
            router_name = line_split[0]
            vmid = line_split[1]
            mac_addr = line_split[2]
            ip_addr = line_split[3]
            router_data = self._get_router_by_name(router_name)
            template = router_data['template']
            template_module = self.get_module(template)

            username, password = self.get_template_credentials(template)

            template_group = "{}_bootstrap".format(template_module.__NAME__)
            if template_group not in router_inv['all']['children']:
                router_groups.append(template_group)
                router_inv['all']['children'][template_group] = {
                    "hosts": {},
                    "vars": {
                        "ansible_connection": template_module.__METHOD__,
                        "ansible_network_os": template_module.__OSTYPE__,
                        "ansible_user": username,
                        "ansible_password": password
                    }
                }

            new_network = router_data['connections'][1]
            new_ip = list(self._get_network_by_name(new_network).ip_range.hosts())[0]

            pre_name = "pre-{}".format(router_name) 
            router_inv['all']['children'][template_group][pre_name] = {
                "ansible_host": ip_addr,
                "interfaces": {
                    "eth1": str(new_ip)
                }
            }


        yamlOut = dump(router_inv, Dumper=Dumper)
        print(yamlOut)


    def complete(self):
        self.dnsmasq.stop()

    