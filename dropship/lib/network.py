import ipaddress
import os
import logging
import time

import dropship.constants

logger = logging.getLogger('dropship')

class DropshipNetwork():
    def __init__(self, dropship, name, switch_id, ip_range):
        self.name = name
        self._switch_id = switch_id
        self._dropship = dropship
        
        # Network data
        self.domain = ""
        self.domain_admin = ""
        self.admin_password = ""
        self._ip_range = ipaddress.ip_network(ip_range)

        self.clients = []
        self.dcs = []
        self.routers = []
        self.users = []


        self._network_dir = ""
        self._bootstrap_dir = ""

    def add_router(self, template, system_name, connection_to):
        self.routers.append({
            "template": template,
            "system_name": system_name,
            "connection": connection_to,
            "vmid": 0
        })

    def _get_all_addresses(self, mac_list):
        out_map = {}

        done = False
        counter = 0

        while not done and counter < 300:
            for mac in mac_list:
                if mac not in out_map:
                    ip_addr = self._dropship.dnsmasq.get_ip_by_mac(mac)
                    if ip_addr is not None:
                        out_map[mac] = ip_addr
            
            if len(out_map.keys()) == len(mac_list):
                done = True

            counter += 1
            logger.info("Waiting for DHCP to assign addresses...")
            time.sleep(5)

        return out_map

    def _networking_bootstrap(self):

        addr_state_file = self._bootstrap_dir + "router_addr.state"
        print(addr_state_file)

        if not os.path.exists(addr_state_file):

            logger.info("Cloning routers...")
            # Clone out the necessary templates
            for i in range(len(self.routers)):
                router = self.routers[i]
                template = router['template']
                router_name = router['system_name']
                display_name = "{}".format(router_name)
                vmid = self._dropship.provider.clone_vm(template, display_name)
                if vmid == 0:
                    return False
                self.routers[i]['vmid'] = vmid

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            self._dropship.provider.wait()
            
            mac_list = []
            vm_mac_map = {}

            logger.info("Configuring and starting routers...")
            for i in range(len(self.routers)):
                vmid = self.routers[i]['vmid']
                router_name = self.routers[i]['system_name']
                bootstrap_switch = self._dropship.config['bootstrap']['switch']
                # For first round addressing
                self._dropship.provider.set_interface(vmid, 0, bootstrap_switch)

                # While we are here, get the mac address for this interface
                mac_addr = self._dropship.provider.get_interface(vmid, 0)['mac'].lower()
                vm_mac_map[router_name] = mac_addr
                mac_list.append(mac_addr)

                # For second round addressing
                self._dropship.provider.set_interface(vmid, 1, bootstrap_switch)
                time.sleep(1)
                self._dropship.provider.start_vm(vmid)

            # Get IP mappings
            mac_map = self._get_all_addresses(mac_list)

            # Write a state file
            state_file = open(addr_state_file, "w+")
            for i in range(len(self.routers)):
                router = self.routers[i]
                template = router['template']
                router_name = router['system_name']
                vmid = router['vmid']
                mac_addr = vm_mac_map[router_name]
                ip_addr = mac_map[mac_addr]
                state_file.write("{}|{}|{}|{}|{}\n".format(router_name, template, vmid, mac_addr, ip_addr))
            state_file.close()
        else:
            logger.info("Using existing networking state file")


        # Create bootstrap config for networking 
        # for i in range(len(self.routers)):
        #     router = self.routers[i]
        #     template = router['template']
        #     router_name = router['system_name']
        #     router_module = self._dropship.load_module(template)
        #     temp_name = "{}-{}".format(i, router_name)
        #     print(temp_name)


    def bootstrap(self):
        # Bootstrap output directories
        self._network_dir = dropship.constants.OutDir + "/" + self.name + "/"
        if not os.path.exists(self._network_dir):
            os.mkdir(self._network_dir)

        self._bootstrap_dir = dropship.constants.OutDir + "/" + self.name + "/bootstrap/"
        if not os.path.exists(self._bootstrap_dir):
            os.mkdir(self._bootstrap_dir)
        
        # deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy"
        # os.mkdir(deploy_dir)

        # post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        # os.mkdir(post_dir)
        
        self._networking_bootstrap()



        