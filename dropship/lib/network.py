import ipaddress
import os
import shutil 

import time

import dropship.constants
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook

import logging
logger = logging.getLogger('dropship')

class DropshipNetwork():
    def __init__(self, dropship, name, switch_id, ip_range):
        self.name = name
        self.switch_id = switch_id
        self._dropship = dropship
        
        # Network data
        self.domain = ""
        self.domain_admin = ""
        self.admin_password = ""
        self.ip_range = ipaddress.ip_network(ip_range)

        self.clients = []
        self.services = []
        self.users = []


        self._network_dir = ""
        self._bootstrap_dir = ""

    def setup_domain(self, domain, admin, admin_password):
        self.domain = domain
        self.domain_admin = admin
        self.admin_password = admin_password

    def add_dc(self, template, dc_name, ip_addr):
        # domain_module = self._dropship.load_module(template)
        self.services.append({
            "template": template,
            "system_name": dc_name,
            "ip_addr": ip_addr,
            'vmid': 0
        })
        pass


    def bootstrap(self):
        # Bootstrap output directories
        self._network_dir = dropship.constants.OutDir + "/" + self.name + "/"
        if not os.path.exists(self._network_dir):
            os.mkdir(self._network_dir)

        self._bootstrap_dir = dropship.constants.OutDir + "/" + self.name + "/bootstrap/"
        if not os.path.exists(self._bootstrap_dir):
            os.mkdir(self._bootstrap_dir)

        # First bootstrap services

        state_file = StateFile(self._network_dir + "services_addr.state")

        if state_file.is_done():
            logger.warning("Services setup has already been completed")
            return

        # Check for existing state file so we don't clone again
        if not state_file.exists():
            logger.info("Cloning services systems...")
            for i in range(len(self.services)):
                system = self.services[i]
                template = system['template']
                template_module = self._dropship.get_module(template)
                system_name = system['system_name']

                state_file.add_system(system_name)

                display_name = "{}".format(system_name)
                vmid = self._dropship.provider.clone_vm(template_module.__IMAGE__, display_name)
                if vmid == 0:
                    return False
                self.services[i]['vmid'] = vmid
                state_file.set_vmid(system_name, vmid)

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            self._dropship.provider.wait()
            
            logger.info("Configuring networking and starting systems...")
            for i in range(len(self.services)):
                vmid = self.services[i]['vmid']
                system_name = self.services[i]['system_name']
                bootstrap_switch = self._dropship.config['bootstrap']['switch']
                # Set the interface to be on bootstrap switch
                self._dropship.provider.set_interface(vmid, 0, bootstrap_switch)

                # While we are here, get the mac address for this interface
                mac_addr = self._dropship.provider.get_interface(vmid, 0)['mac'].lower()
                state_file.set_mac(system_name, mac_addr)

                time.sleep(1)
                self._dropship.provider.start_vm(vmid)

            # Get IP mappings
            mac_map = self._dropship.get_address_map(state_file.get_all_macs())

            
            for system in self.services:
                state_file.set_ip(system['system_name'], mac_map[mac_addr])

            # Write a state file
            state_file.to_file()
        else:
            logger.info("Using existing services state file")

        logger.info("Generating system inventory files...")

        # Load VM data from state file
        state_file.from_file()

        services_inv = DropshipInventory()

        for server in self.services:
            system_name = server['system_name']
            template = server['template']
            template_module = self._dropship.get_module(template)
            template_name = template_module.__NAME__

            vmid, mac_addr, ip_addr = state_file.get_system(system_name)

            username, password = self._dropship.get_template_credentials(template)

            # Group systems of same template under a host group
            template_group = "{}_bootstrap".format(template_name)

            if not services_inv.has_group(template_group):
                services_inv.add_group(
                    template_group, 
                    template_module.__OSTYPE__, 
                    template_module.__METHOD__,
                    username,
                    password
                )
                services_inv.set_group_metadata(template_group, 'template', template_name)

                # Create the directory to store the module's Ansible files
                ansible_dir = self._network_dir + "/" + template_name
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

                services_inv.set_group_metadata(template_group, 'ansible_dir', ansible_dir)
                services_inv.set_group_metadata(template_group, 'bootstrap', dest_file)
                services_inv.set_group_metadata(template_group, 'reboot', dest_file_reboot)


            new_ip = server['ip_addr']
            

            services_inv.add_host(template_group, system_name, ip_addr, vars={
                "new_ip" : new_ip
            })
        
        services_inventory_path = self._network_dir + "bootstrap_services_inventory.yml"
        services_inv.to_file(services_inventory_path)

        base_playbook = BasePlaybook()

        for group_name in services_inv.group_list():
            
            base_playbook.add_group(
                group_name,
                "Bootstrap {} services".format(services_inv.get_group_metadata(group_name,'template'))
            )

            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(services_inv.get_group_metadata(group_name,'bootstrap')),
                    "name": "Run bootstrap file"
                }
            )
            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(services_inv.get_group_metadata(group_name,'reboot')),
                    "name": "Run reboot file"
                }
            )

        base_playbook_path = self._network_dir + "bootstrap_base_playbook.yml"
        base_playbook.to_file(base_playbook_path)
        
        # deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy"
        # os.mkdir(deploy_dir)

        # post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        # os.mkdir(post_dir)
        
        



        