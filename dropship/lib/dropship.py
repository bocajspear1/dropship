import json
import shutil 
import importlib
import time
import os
import copy
import subprocess

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
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook


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

        self.external_switch = None

    def set_external_switch(self, external_switch):
        self.external_switch = external_switch

    def get_module(self, module_name):
        if module_name in self._module_cache:
            return self._module_cache[module_name]

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
                        out_map[mac.lower()] = ip_addr
            
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

    def _set_router_vmid(self, router_name, vmid):
        for i in range(len(self.routers)):
            if self.routers[i]['router_name'] == router_name:
                self.routers[i]['vmid'] = vmid

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

    def run_ansible(self, inventory_path, playbook_path):
        # Execute using Ansible command line
        # Ansible can be called in Python, but its broken, so we do it the old-fashioned way
        # Good work Ansible!
        results = subprocess.run([
            "/bin/sh", "-c", 'ansible-playbook -i {} {}'.format(inventory_path, playbook_path)
        ])

        return results.returncode

    def _bootstrap_routers(self):
        logger.info("Bootstrapping routers...")
        # Prepare router directory
        router_dir = dropship.constants.OutDir + "/routers/"
        if not os.path.exists(router_dir):
            os.mkdir(router_dir)


        state_file = StateFile(router_dir + "router_addr.state")

        if state_file.is_done():
            logger.warning("Router setup has already been completed")
            return

        # Check for existing state file so we don't clone again
        if not state_file.exists():

            # Clone out the necessary templates
            logger.info("Cloning routers...")
            for i in range(len(self.routers)):
                router = self.routers[i]
                template = router['template']
                template_module = self.get_module(template)
                router_name = router['router_name']

                state_file.add_system(router_name)

                display_name = "{}".format(router_name)
                vmid = self.provider.clone_vm(template_module.__IMAGE__, display_name)
                if vmid == 0:
                    return False
                self.routers[i]['vmid'] = vmid
                state_file.set_vmid(router_name, vmid)

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            self.provider.wait()
            
            logger.info("Configuring and starting routers...")
            for i in range(len(self.routers)):
                vmid = self.routers[i]['vmid']
                router_name = self.routers[i]['router_name']
                bootstrap_switch = self.config['bootstrap']['switch']
                # For first round addressing
                self.provider.set_interface(vmid, 0, bootstrap_switch)

                # While we are here, get the mac address for this interface
                mac_addr = self.provider.get_interface(vmid, 0)['mac'].lower()
                state_file.set_mac(router_name, mac_addr)

                # For second round addressing
                self.provider.set_interface(vmid, 1, bootstrap_switch)
                time.sleep(1)
                self.provider.start_vm(vmid)


            # Get IP mappings
            mac_map = self.get_address_map(state_file.get_all_macs())

            
            for router in self.routers:
                state_file.set_ip(router['router_name'], mac_map[state_file.get_system(system['system_name'])[1]])
            
            # Write a state file
            state_file.to_file()
        else:
            logger.info("Using existing router state file")

        logger.info("Generating router inventory files...")

        # Load VM data from state file
        state_file.from_file()

        # Create the 'pre' router inventory file, this is run to set the IP for a second final run on the router

        pre_router_inv = DropshipInventory()
        router_inv = DropshipInventory()


        # Stores data per template, including group and directory info
        template_group_map = {}

        for router in self.routers:
            router_name = router['router_name']
            vmid, mac_addr, ip_addr = state_file.get_system(router_name)

            self._set_router_vmid(router_name, vmid)

            router_data = self._get_router_by_name(router_name)
            
            template = router_data['template']
            template_module = self.get_module(template)
            template_name = template_module.__NAME__

            username, password = self.get_template_credentials(template)

            # Group routers of same template under a host group
            template_group = "{}_bootstrap".format(template_name)

            if not pre_router_inv.has_group(template_group):
                pre_router_inv.add_group(
                    template_group, 
                    template_module.__OSTYPE__, 
                    template_module.__METHOD__,
                    username,
                    password
                )

                router_inv.add_group(
                    template_group, 
                    template_module.__OSTYPE__, 
                    template_module.__METHOD__,
                    username,
                    password
                )

                # Create the directory to store the module's Ansible files
                ansible_dir = router_dir + "/" + template_name
                if not os.path.exists(ansible_dir):
                    os.mkdir(ansible_dir)

                # Get the module's bootstrap.yml file
                ansible_bootstrap = template_module.get_dir() + "/bootstrap.yml"
                dest_file = ansible_dir + "/bootstrap.yml"
                # Copy the bootstrap file to our working directory
                shutil.copyfile(ansible_bootstrap, dest_file)


                # Get the module's reboot.yml file
                ansible_reboot = template_module.get_dir() + "/reboot.yml"
                dest_file_reboot = ansible_dir + "/reboot.yml"
                # Copy the reboot file to our working directory
                shutil.copyfile(ansible_reboot, dest_file_reboot)

                template_group_map[template_name] = {
                    "dir": ansible_dir,
                    "group": template_group,
                    "bootstrap": dest_file,
                    "reboot": dest_file_reboot
                }


            new_network = router_data['connections'][1]
            new_network_data = self._get_network_by_name(new_network)
            new_ip = list(new_network_data.ip_range.hosts())[0]


            pre_name = "pre-{}".format(router_name) 

            pre_router_inv.add_host(template_group, pre_name, ip_addr, vars={
                "interfaces": [
                     {
                        "iface": "eth1",
                        "addr": str(new_ip) + "/{}".format(new_network_data.ip_range.prefixlen) 
                     }
                ]
            })
            
            router_inv.add_host(template_group, router_name, str(new_ip))

        pre_inventory_path = router_dir + "pre_inventory.yml"
        pre_router_inv.to_file(pre_inventory_path)
        router_inventory_path = router_dir + "inventory.yml"
        router_inv.to_file(router_inventory_path)

        pre_playbook = BasePlaybook()
        base_playbook = BasePlaybook()

        # Create pre-playbook that will set the initial IP
        for group in template_group_map:
            group_name = template_group_map[group]['group']
            pre_playbook.add_group(
                group_name,
                "Bootstrap {} routers first IP and reboot".format(group)
            )

            pre_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(template_group_map[group]['bootstrap']),
                    "name": "Run bootstrap file"
                }
            )
            pre_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(template_group_map[group]['reboot']),
                    "name": "Run reboot file"
                }
            )

        # Generate base playbook that will set the system name
        for group in template_group_map:
            group_name = template_group_map[group]['group']
            base_playbook.add_group(
                group_name, 
                "Bootstrap {} routers".format(group)
            )

            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(template_group_map[group]['bootstrap']),
                    "name": "Run bootstrap file"
                }
            )


        pre_playbook_path = router_dir + "pre_playbook.yml"
        pre_playbook.to_file(pre_playbook_path)
        base_playbook_path = router_dir + "base_playbook.yml"
        base_playbook.to_file(base_playbook_path)


        logger.info("Inventory files created!")

        

        logger.info("Running pre-inventory Ansible")
        result = self.run_ansible(pre_inventory_path, pre_playbook_path)

        if result != 0:
            logger.error("Pre-inventory Ansible failed!")
            return

        logger.info("Setting configuration IP on config interface")
        for network in self.networks:
            network_range = network.ip_range
            network_hosts = list(network_range.hosts())
            network_len = network_range.prefixlen
            
            # Setup the IP for internal network access
            subprocess.call([
                "/usr/bin/sudo", 
                '/sbin/ip',
                'addr', 
                'add', 
                '{}/{}'.format(network_hosts[len(network_hosts)-1], network_len),
                'dev',
                self.config['bootstrap']['interface']
            ])

        # Update external router connections
        for router in self.routers:
            for i in range(len(router['connections'])):
                connection = router['connections'][i]
                if connection == dropship.constants.ExternalConnection:
                    self.provider.set_interface(router['vmid'], i, self.external_switch)

        logger.info("Running main router Ansible")
        result = self.run_ansible(router_inventory_path, base_playbook_path)

        if result != 0:
            logger.error("Ansible failed!")
            return

        # Update internal router connections
        for router in self.routers:
            for i in range(len(router['connections'])):
                connection = router['connections'][i]
                if connection != dropship.constants.ExternalConnection:
                    network = self._get_network_by_name(connection)
                    self.provider.set_interface(router['vmid'], i, network.switch_id)

        # Mark the routers as completed
        state_file.mark_done()



    def complete(self):
        pass
        # self.dnsmasq.stop()

    