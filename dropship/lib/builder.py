import json
import logging
import os
import time
import subprocess

from dropship.lib.proxmox import ProxmoxProvider
from dropship.lib.dnsmasq import DropshipDNSMasq
from dropship.lib.helpers import ModuleManager
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook, DoneFile
import dropship.constants

logger = logging.getLogger('dropship')

class DropshipBuilder():

    def __init__(self, config_path,  module_path=None):
        self._config_path = config_path
        self.config = json.loads(open(self._config_path, "r").read())

        self.provider = None
        self.dnsmasq = None

        self.external_switch = None
        self._router_dir = ""
        self._routers = []

        self._instances = {}

        if module_path is None:
            self.mm = ModuleManager("./out")
        else:
            self.mm = ModuleManager("./out", module_path=module_path)

    def run_ansible(self, inventory_path, playbook_path):
        # Execute using Ansible command line
        # Ansible can be called in Python, but its broken, so we do it the old-fashioned way
        # Good work Ansible!
        results = subprocess.run([
            "/bin/sh", "-c", 'ansible-playbook -i {} {}'.format(inventory_path, playbook_path)
        ])

        return results.returncode

    def add_instance(self, instance_name, instance_obj):
        self._instances[instance_name] = instance_obj

    def wait_for_address_map(self, mac_list):
        out_map = {}

        done = False
        counter = 0

        while not done and counter < 5000:
            for mac in mac_list:
                if mac not in out_map:
                    ip_addr = self.dnsmasq.get_ip_by_mac(mac)
                    if ip_addr is not None:
                        out_map[mac.lower()] = ip_addr
            
            if len(out_map.keys()) == len(mac_list):
                ok = True
                for mac in mac_list:
                    if mac not in out_map:
                        ok = False
                if ok:
                    done = True

            counter += 1
            logger.info("{} - Waiting for DHCP to assign addresses...".format(counter))
            time.sleep(5)

        print(mac_list)
        print(out_map)
        return out_map

    def init_provider(self):
        # Load the provider
        if not 'provider' in self.config:
            logger.error("provider key not found")
            return False

        if self.config['provider'] == "proxmox":
            self.provider = ProxmoxProvider(self.config['proxmox'], self.config['vm_map'])
        else:
            logger.log("Invalid provider '{}'".format(self.config['provider']))
            return False

    def ensure_subdir(self, path):
        new_path = dropship.constants.OutDir + "/" + path
        new_path = os.path.normpath(new_path)
        if not os.path.exists(new_path):
            os.mkdir(new_path)
        return new_path

    def run_build(self):

        self.dnsmasq = DropshipDNSMasq(self.config['bootstrap'])
        self.external_switch = self.config['external_switch_id']

        logger.info("Setting configuration IP on config interface")
        for instance_name in self._instances:
            instance = self._instances[instance_name]
            instance_range = instance.ip_range
            network_hosts = list(instance_range.hosts())
            prefix_len = instance_range.prefixlen
            
            # Setup the IP for internal network access
            subprocess.call([
                "/usr/bin/sudo", 
                '/sbin/ip',
                'addr', 
                'add', 
                '{}/{}'.format(network_hosts[len(network_hosts)-1], prefix_len),
                'dev',
                self.config['bootstrap']['interface']
            ])

        switch_net_map = {}

        # Create all switches and get instance routers
        for instance_name in self._instances:
            inst = self._instances[instance_name]
            ok = self.provider.create_switch(inst.switch_id)
            if not ok:
                logger.error("Failed to create switch '{}'".format(inst.switch_id))
                return False
            switch_net_map[inst.name] = inst.switch_id

            self._routers += inst.get_routers()

        
        # Ensure the output directory has been created
        self.ensure_subdir("")

        # Connect the commander configuration interface up to the bootstrap switch
        bootstrap_switch = self.config['bootstrap']['switch']

        # Ensure the bootstrap switch exists
        ok = self.provider.create_switch(bootstrap_switch)
        if not ok:
            logger.error("Failed to create bootstrap switch '{}'".format(bootstrap_switch))
            return False
        self.provider.set_interface(self.config['commander']['vmid'], self.config['commander']['interface'], bootstrap_switch)

        self.dnsmasq.start()
        ok = self._bootstrap_routers()
        if not ok:
            logger.error("Failed to run bootstrap routers")
            return False

        for instance_name in self._instances:
            instance = self._instances[instance_name]
            ok = instance.run_bootstrap(self)
            if not ok:
                logger.error("Failed to run bootstrap for instance '{}'".format(instance_name))
                return False

        time.sleep(2)
        self.dnsmasq.stop()

        for instance_name in self._instances:
            instance = self._instances[instance_name]
            ok = instance.run_deploy(self)
            if not ok:
                logger.error("Failed to run deploy for instance '{}'".format(instance_name))
                return False

        for instance_name in self._instances:
            instance = self._instances[instance_name]
            ok = instance.run_post(self)
            if not ok:
                logger.error("Failed to run post for instance '{}'".format(instance_name))
                return False
        
        logger.info("All modules completed successfully!")


    def _bootstrap_routers(self):
        logger.info("Bootstrapping routers...")
        self._router_dir = self.ensure_subdir("sys_routers")

        state_file = StateFile(self._router_dir + "/router_bootstrap.state")

        if not state_file.is_done():
           
            # Check for existing state file so we don't clone again
            if not state_file.exists():

                # Clone out the necessary templates
                logger.info("Cloning routers...")
                for i in range(len(self._routers)):
                    router = self._routers[i]
                    router_mod = self.mm.get_module(router.module_name)
                    router_name = router.hostname

                    state_file.add_system(router_name)

                    display_name = "{}".format(router_name)
                    vmid = self.provider.clone_vm(router_mod.__IMAGE__, display_name)
                    if vmid == 0:
                        logger.error("Failed to clone {} system {}".format(router.module_name, router_name))
                        return False
                    
                    self._routers[i].vmid = vmid
                    state_file.set_vmid(router_name, vmid)

                # Wait for clones
                logger.info("Waiting for clones to complete...")
                self.provider.wait()

                logger.info("Configuring and starting routers...")
                for i in range(len(self._routers)):
                    router = self._routers[i]
                    
                    bootstrap_switch = self.config['bootstrap']['switch']
                    # For first round addressing
                    self.provider.set_interface(router.vmid, 0, bootstrap_switch)

                    # While we are here, get the mac address for this interface
                    mac_addr = self.provider.get_interface(router.vmid, 0)['mac'].lower()
                    state_file.set_mac(router.hostname, mac_addr)

                    # For second round addressing
                    self.provider.set_interface(router.vmid, 1, bootstrap_switch)
                    time.sleep(1)
                    self.provider.start_vm(router.vmid)

                # Get IP mappings
                mac_map = self.wait_for_address_map(state_file.get_all_macs())

                for router in self._routers:
                    state_file.set_ip(router.hostname, mac_map[state_file.get_system(router.hostname)[1]])
                
                # Write a state file
                state_file.to_file()

            else:
                logger.info("Using existing router state file")

            logger.info("Generating router inventory files...")

            # Load VM data from state file
            state_file.from_file()

            # Fill in data from state file
            for i in range(len(self._routers)):
                state_file_data = state_file.get_system(self._routers[i].hostname)
                self._routers[i].vmid = state_file_data[0]
                self._routers[i].connect_ip = state_file_data[2]
        
                print(self._routers[i].vmid)

            # This inventory is for the first run of the router bootstrap process
            # It connects to the external interface to set the internal interface
            # which is used for the rest of the configuration
            pre_router_inv = DropshipInventory()

            # Set vars for pre-inventory
            for i in range(len(self._routers)):
                router_mod = self.mm.get_module(self._routers[i].module_name)
                # Ensure module files are set up
                router_mod.prepare_bootstrap(self.mm.out_path)

                iface = self._routers[i].interfaces[1]
                if iface.has_offset():
                    iface.set_offset_addr(self._instances[iface.network_name].ip_range)

                new_ip = str(iface.ip_addr) 
                instance_network = self._instances[iface.network_name]
                self._routers[i].vars['interfaces'] = [
                     {
                        "iface": router_mod.get_interface_name(1),
                        "addr":  new_ip,
                        "prefix": str(instance_network.ip_range.prefixlen),
                        "netmask": str(instance_network.ip_range.netmask)
                     }
                ]
                self._routers[i].vars['new_ip_set'] = new_ip

            
            pre_router_inv.from_host_list(self.mm, self.config['credentials'], self._routers, name_prefix='pre-')
            
            pre_inventory_path = self._router_dir + "/pre_inventory.yml"
            pre_router_inv.to_file(pre_inventory_path)

            # Set vars for inventory
            for i in range(len(self._routers)):
                self._routers[i].vars['interfaces'].clear()
                for j in range(len(self._routers[i].interfaces)):
                    
                    # Skip second interface, we are already setting that in the previous step
                    if j == 1:
                        continue

                    self._routers[i].connect_ip = self._routers[i].vars['new_ip_set']
                    del self._routers[i].vars['new_ip_set']

                    iface = self._routers[i].interfaces[j]

                    if iface.has_offset():
                        iface.set_offset_addr(self._instances[iface.network_name].ip_range)
                    
                    if iface.network_name != dropship.constants.ExternalConnection:
                        instance_network = self._instances[iface.network_name]
                        iface_addr = str(iface.ip_addr)
                        self._routers[i].vars['interfaces'].append(
                            {
                                "iface": self.mm.get_module(self._routers[i].module_name).get_interface_name(j),
                                "addr": iface_addr,
                                "prefix": str(instance_network.ip_range.prefixlen),
                                "netmask": str(instance_network.ip_range.netmask)
                            }
                        )
            
            router_inv = DropshipInventory()
            router_inv.from_host_list(self.mm, self.config['credentials'], self._routers)
            router_inventory_path = self._router_dir + "/inventory.yml"
            router_inv.to_file(router_inventory_path)



            pre_playbook = BasePlaybook()
            base_playbook = BasePlaybook()

            # Create pre-playbook that will set the initial IP
            for group_name in pre_router_inv.group_list():
                pre_playbook.add_group(
                    group_name,
                    "Bootstrap {} routers first IP and reboot".format(group_name)
                )

                pre_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(pre_router_inv.get_group_metadata(group_name, 'bootstrap_path')),
                        "name": "Run bootstrap file"
                    }
                )
                pre_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(pre_router_inv.get_group_metadata(group_name, 'reboot_path')),
                        "name": "Run reboot file"
                    }
                )

            # Generate base playbook that will set the system name
            for group_name in router_inv.group_list():
                base_playbook.add_group(
                    group_name, 
                    "Bootstrap {} routers".format(group_name)
                )

                base_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(pre_router_inv.get_group_metadata(group_name, 'bootstrap_path')),
                        "name": "Run bootstrap file"
                    }
                )


            pre_playbook_path = self._router_dir + "/pre_playbook.yml"
            pre_playbook.to_file(pre_playbook_path)
            base_playbook_path = self._router_dir + "/base_playbook.yml"
            base_playbook.to_file(base_playbook_path)


            logger.info("Inventory files created!")

            logger.info("Running pre-inventory Ansible")
            result = self.run_ansible(pre_inventory_path, pre_playbook_path)

            if result != 0:
                logger.error("Pre-inventory Ansible failed!")
                return
            
            logger.info("Setting router external interfaces to correct switch")
            # Update external router connections
            for router in self._routers:
                for i in range(len(router.interfaces)):
                    instance_conn = router.interfaces[i]
                    if instance_conn.network_name == dropship.constants.ExternalConnection:
                        self.provider.set_interface(router.vmid, i, self.external_switch)

            logger.info("Running main router Ansible")
            result = self.run_ansible(router_inventory_path, base_playbook_path)

            if result != 0:
                logger.error("Ansible failed!")
                return

            # Update internal router connections
            for router in self._routers:
                for i in range(len(router.interfaces)):
                    instance_conn = router.interfaces[i]
                    if instance_conn.network_name != dropship.constants.ExternalConnection:
                        instance = self._instances[instance_conn.network_name]
                        self.provider.set_interface(router.vmid, i, instance.switch_id)

            # Mark the routers as completed
            state_file.mark_done()    
        else:
            logger.warning("Router bootstrap has already been completed")
        
        
        # Always update routers with VMID data from statefile
        state_file.from_file()
        for i in range(len(self._routers)):
            
            state_file_data = state_file.get_system(self._routers[i].hostname)
            self._routers[i].vmid = state_file_data[0]
        
        return True

        

        