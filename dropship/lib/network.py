import ipaddress
import os
import shutil 

import time

import dropship.constants
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook, DoneFile

import logging
logger = logging.getLogger('dropship')

class DropshipNetwork():
    def __init__(self, dropship, name, switch_id, ip_range):
        self.name = name
        self.switch_id = switch_id
        self._dropship = dropship

        self._vars = {}
        self._hosts = {}
        self._users = {}

        # Network data
        self.domain = ""
        self.domain_short = ""
        self.domain_admin = ""
        self.admin_password = ""
        self.ip_range = ipaddress.ip_network(ip_range)
        self.dns_forwarder = ""
        self.dhcp_gateway = None
        self.network_int_dns = None
        self.dhcp_dns = None
        self.dhcp_start = None
        self.dhcp_end = None

        self.clients = []
        self.services = []
        self.users = []


        self._network_dir = ""
        self._bootstrap_dir = ""
        self._deploy_dir = ""
        self._post_dir = ""

        self._clients_configured_state_file = ""
        self._services_configured_state_file = ""

        self.pre_deploy_snapshot = False

    def set_dns_forwarder(self, server):
        self.dns_forwarder = server

    def set_dhcp_server(self, template, server_name, ip_addr, dhcp_start, dhcp_end, gateway=None, dns=None):
        if gateway is None:
            self.dhcp_gateway = str(list(self.ip_range.hosts())[0])
        if dns is None:
            self.dhcp_dns = self.network_int_dns 
            if self.dhcp_dns is None:
                raise ValueError("No DNS server found for DHCP")

        self.dhcp_start = dhcp_start
        self.dhcp_end = dhcp_end

        self.services.append({
            "template": template,
            "system_name": server_name,
            "ip_addr": ip_addr,
            'vmid': 0,
            'role': 'dhcp'
        })

    def setup_domain(self, domain, admin, admin_password):
        self.domain = domain
        self.domain_short = self.domain.split(".")[0]
        self.domain_admin = admin
        self.admin_password = admin_password
        return True

    def add_dc(self, template, dc_name, ip_addr):
        # domain_module = self._dropship.load_module(template)
        if self.network_int_dns is None:
            self.network_int_dns = ip_addr
            
        self.services.append({
            "template": template,
            "system_name": dc_name,
            "ip_addr": ip_addr,
            'vmid': 0,
            'role': 'domain'
        })

    def add_client(self, template, client_name, ip_addr='dhcp'):
        self.clients.append({
            "template": template,
            "system_name": client_name,
            "ip_addr": ip_addr,
            'vmid': 0,
            'role': 'client'
        })

    def add_user(self, firstname, lastname, username, password):
        self.users.append({
            "firstname": firstname,
            "lastname": lastname,
            "username": username,
            "password": password
        })   

    def _get_bootstrap_state_file(self, filename, hosts_list):

        state_file = StateFile(self._bootstrap_dir + "bootstrap_" + filename + ".state")

        if not state_file.exists():
            logger.info("Cloning systems...")
            for i in range(len(hosts_list)):
                system = hosts_list[i]
                template = system['template']
                template_module = self._dropship.get_module(template)
                system_name = system['system_name']

                state_file.add_system(system_name)

                display_name = "{}".format(system_name)
                vmid = self._dropship.provider.clone_vm(template_module.__IMAGE__, display_name)
                if vmid == 0:
                    logger.error("Failed to clone VM for {}".format(display_name))
                    return False
                hosts_list[i]['vmid'] = vmid
                state_file.set_vmid(system_name, vmid)

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            self._dropship.provider.wait()
            
            logger.info("Configuring networking and starting systems...")
            for i in range(len(hosts_list)):
                vmid = hosts_list[i]['vmid']
                system_name = hosts_list[i]['system_name']
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

            
            for system in hosts_list:
                state_file.set_ip(system['system_name'], mac_map[state_file.get_system(system['system_name'])[1]])

            # Write a state file
            state_file.to_file()
            
        else:
            logger.info("Using existing {} state file".format(filename))

        state_file.from_file()
        return state_file

    def _bootstrap_services(self):

        state_file = self._get_bootstrap_state_file('services', self.services)
        # Create a clone of the state file which we will update with the new IPs for the next steps
        self._services_configured_state_file = self._deploy_dir + "configured_services.state"
        next_state = state_file.clone(self._services_configured_state_file)

        if state_file.is_done():
            logger.warning("Services bootstrap has already been completed for network {}".format(self.name))
            return True

       
        logger.info("Generating services bootstrap inventory files...")

        # Load VM data from state file
        state_file.from_file()

        services_inv = DropshipInventory()

        for server in self.services:
            system_name = server['system_name']
            template = server['template']
            template_module = self._dropship.get_module(template)
            template_name = template_module.__IMAGE__

            vmid, mac_addr, ip_addr = state_file.get_system(system_name)

            username, password = self._dropship.get_image_credentials(template_module.__IMAGE__)

            # Group systems of same template under a host group
            template_group = template.replace(".", "_") + "_deploy"

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
                ansible_dir = self._bootstrap_dir + "/" + template
                if not os.path.exists(ansible_dir):
                    os.mkdir(ansible_dir)

                # Get the module's bootstrap.yml file

                ansible_bootstrap = template_module.get_dir() + "/bootstrap.yml"
                dest_file = ansible_dir + "/bootstrap.yml"

                # Check for files
                if not hasattr(template_module, '__BOOTSTRAP_FILES__'):
                    # If no files, there's no paths to change, so just copy the bootstrap file
                    shutil.copyfile(ansible_bootstrap, dest_file)
                else:
                    files_dir = ansible_dir + "/files"

                    if not os.path.exists(files_dir):
                        os.mkdir(files_dir)

                    for item in template_module.__BOOTSTRAP_FILES__:
                        shutil.copyfile(template_module.get_dir() + "/files/" + item, files_dir + "/" + item)

                    bs_file = open(ansible_bootstrap, "r")
                    bs_file_data = bs_file.read()
                    bs_file.close()

                    bs_file_data = bs_file_data.replace("+TEMPLATES+", os.path.abspath(files_dir))

                    out_bs_file = open(dest_file, "w+")
                    out_bs_file.write(bs_file_data)
                    out_bs_file.close()


                # Get the module's reboot.yml file
                ansible_reboot = template_module.get_dir() + "/reboot.yml"
                dest_file_reboot = ansible_dir + "/reboot.yml"
                # Copy the reboot file to our working directory
                shutil.copyfile(ansible_reboot, dest_file_reboot)

                services_inv.set_group_metadata(template_group, 'ansible_dir', ansible_dir)
                services_inv.set_group_metadata(template_group, 'bootstrap', dest_file)
                services_inv.set_group_metadata(template_group, 'reboot', dest_file_reboot)

                services_inv.add_group_var(template_group, 'ansible_become_user', template_module.__BECOME_USER__)
                services_inv.add_group_var(template_group, 'ansible_become_method', template_module.__BECOME_METHOD__)
                
                services_inv.add_group_var(template_group, 'ansible_become_pass', password)

            new_ip = server['ip_addr']
            
            host_vars = {
                "new_ip" : new_ip
            }
            next_state.set_ip(system_name, new_ip)

            services_inv.add_host(template_group, system_name, ip_addr, vars=host_vars)
        
        services_inv.set_global_var('new_prefix', self.ip_range.prefixlen)
        services_inv.set_global_var('new_mask', str(self.ip_range.netmask))
        services_inv.set_global_var('network_ext_dns', self.dns_forwarder)
        services_inv.set_global_var('network_int_dns', self.network_int_dns)
        services_inv.set_global_var('network_gateway', str(list(self.ip_range.hosts())[0]))
        services_inv.set_global_var('ansible_become', 'yes')
        

        services_inventory_path = self._bootstrap_dir + "bootstrap_services_inventory.yml"
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

        base_playbook_path = self._bootstrap_dir + "bootstrap_base_playbook.yml"
        base_playbook.to_file(base_playbook_path)

        result = self._dropship.run_ansible(services_inventory_path, base_playbook_path)

        if result != 0:
            logger.error("Service bootstrap Ansible failed! Please refer to Ansible output for error details.")
            return False

        for system in self.services:
            self._dropship.provider.set_interface(state_file.get_vmid(system['system_name']), 0, self.switch_id)

        # Create a state file for the deploy and post parts


        state_file.mark_done()
        next_state.to_file()
        return True

    def _bootstrap_clients(self):
        
        state_file = self._get_bootstrap_state_file('clients', self.clients)
        # Create a clone of the state file which we will update with the new IPs for the next steps
        self._clients_configured_state_file = self._deploy_dir + "configured_clients.state"
        next_state = state_file.clone(self._clients_configured_state_file)

        if state_file.is_done():
            logger.warning("Clients bootstrap has already been completed for network {}".format(self.name))
            return True

        # Check for existing state file so we don't clone again
        logger.info("Generating system bootstrap inventory files...")

        # Load VM data from state file
        state_file.from_file()

        client_inv = DropshipInventory()

        for server in self.clients:
            system_name = server['system_name']
            template = server['template']
            template_module = self._dropship.get_module(template)
            template_name = template_module.__IMAGE__

            vmid, mac_addr, ip_addr = state_file.get_system(system_name)

            username, password = self._dropship.get_image_credentials(template_module.__IMAGE__)

            # Group systems of same template under a host group
            template_group = template.replace(".", "_") + "_deploy"

            if not client_inv.has_group(template_group):
                client_inv.add_group(
                    template_group, 
                    template_module.__OSTYPE__, 
                    template_module.__METHOD__,
                    username,
                    password
                )
                client_inv.set_group_metadata(template_group, 'template', template_name)

                # Create the directory to store the module's Ansible files
                ansible_dir = self._bootstrap_dir + "/" + template
                if not os.path.exists(ansible_dir):
                    os.mkdir(ansible_dir)

                # Get the module's bootstrap.yml file

                ansible_bootstrap = template_module.get_dir() + "/bootstrap.yml"
                dest_file = ansible_dir + "/bootstrap.yml"

                # Check for files
                if not hasattr(template_module, '__BOOTSTRAP_FILES__'):
                    # If no files, there's no paths to change, so just copy the bootstrap file
                    shutil.copyfile(ansible_bootstrap, dest_file)
                else:
                    files_dir = ansible_dir + "/files"

                    if not os.path.exists(files_dir):
                        os.mkdir(files_dir)

                    for item in template_module.__BOOTSTRAP_FILES__:
                        shutil.copyfile(template_module.get_dir() + "/files/" + item, files_dir + "/" + item)

                    bs_file = open(ansible_bootstrap, "r")
                    bs_file_data = bs_file.read()
                    bs_file.close()

                    bs_file_data = bs_file_data.replace("+TEMPLATES+", os.path.abspath(files_dir))

                    out_bs_file = open(dest_file, "w+")
                    out_bs_file.write(bs_file_data)
                    out_bs_file.close()


                # Get the module's reboot.yml file
                ansible_reboot = template_module.get_dir() + "/reboot.yml"
                dest_file_reboot = ansible_dir + "/reboot.yml"
                # Copy the reboot file to our working directory
                shutil.copyfile(ansible_reboot, dest_file_reboot)

                client_inv.set_group_metadata(template_group, 'ansible_dir', ansible_dir)
                client_inv.set_group_metadata(template_group, 'bootstrap', dest_file)
                client_inv.set_group_metadata(template_group, 'reboot', dest_file_reboot)

                client_inv.add_group_var(template_group, 'ansible_become_user', template_module.__BECOME_USER__)
                client_inv.add_group_var(template_group, 'ansible_become_method', template_module.__BECOME_METHOD__)
                
                client_inv.add_group_var(template_group, 'ansible_become_pass', password)

            new_ip = server['ip_addr']
            
            host_vars = {
                "new_ip" : new_ip
            }
            next_state.set_ip(system_name, new_ip)

            client_inv.add_host(template_group, system_name, ip_addr, vars=host_vars)
        
        client_inv.set_global_var('new_prefix', self.ip_range.prefixlen)
        client_inv.set_global_var('new_mask', str(self.ip_range.netmask))
        client_inv.set_global_var('network_int_dns', self.network_int_dns)
        client_inv.set_global_var('network_gateway', str(list(self.ip_range.hosts())[0]))
        client_inv.set_global_var('ansible_become', 'yes')
        client_inv.set_global_var('ansible_winrm_server_cert_validation', 'ignore')
        

        client_inventory_path = self._bootstrap_dir + "bootstrap_client_inventory.yml"
        client_inv.to_file(client_inventory_path)

        base_playbook = BasePlaybook()

        for group_name in client_inv.group_list():
            
            base_playbook.add_group(
                group_name,
                "Bootstrap {} services".format(client_inv.get_group_metadata(group_name,'template'))
            )

            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(client_inv.get_group_metadata(group_name,'bootstrap')),
                    "name": "Run bootstrap file"
                }
            )
            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(client_inv.get_group_metadata(group_name,'reboot')),
                    "name": "Run reboot file"
                }
            )

        base_playbook_path = self._bootstrap_dir + "bootstrap_base_playbook.yml"
        base_playbook.to_file(base_playbook_path)

        result = self._dropship.run_ansible(client_inventory_path, base_playbook_path)

        if result != 0:
            logger.error("Service bootstrap Ansible failed! Please refer to Ansible output for error details.")
            return False

        for system in self.clients:
            self._dropship.provider.set_interface(state_file.get_vmid(system['system_name']), 0, self.switch_id)

        state_file.mark_done()
        next_state.to_file()
        return True

    def bootstrap(self):
        # Bootstrap output directories

        self._network_dir = dropship.constants.OutDir + "/" + self.name + "/"
        if not os.path.exists(self._network_dir):
            os.mkdir(self._network_dir)

        self._bootstrap_dir = dropship.constants.OutDir + "/" + self.name + "/bootstrap/"
        if not os.path.exists(self._bootstrap_dir):
            os.mkdir(self._bootstrap_dir)

        self._deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy/"
        if not os.path.exists(self._deploy_dir):
            os.mkdir(self._deploy_dir)

        self._post_dir = dropship.constants.OutDir + "/" + self.name + "/post/"
        if not os.path.exists(self._post_dir):
            os.mkdir(self._post_dir)

        # First bootstrap services

        ok = self._bootstrap_services()

        if ok:
            return self._bootstrap_clients() 
        else:
            return ok


    def _do_deploy(self, name, system_list, state_file):

        logger.info("Starting deployment for {}".format(name))
        system_deploy_inventory = DropshipInventory()

        for system in system_list:

            system_name = system['system_name']

            done_file = DoneFile(self._deploy_dir + system_name + ".done")

            if done_file.is_done():
                logger.warning("Deployment for system {} already done".format(system_name))
                continue

            template = system['template']
            template_module = self._dropship.get_module(template)
            template_group = template.replace(".", "_") + "_deploy"

            vmid, mac_addr, ip_addr = state_file.get_system(system_name)

            # If we want pre-deployment snapshots, make them
            if self.pre_deploy_snapshot:
                error, ok = self._dropship.provider.snapshot_vm(vmid, "pre_configure")

                if error is not None:
                    logger.error("Snapshot failed! - {}".format(error))
                    return False
                
                logger.info("Waiting for snapshot to complete...")
                self._dropship.provider.wait()

            system_vars = {}

            if not system_deploy_inventory.has_group(template_group):
                username, password = self._dropship.get_image_credentials(template_module.__IMAGE__)
                system_deploy_inventory.add_group(
                    template_group, 
                    template_module.__OSTYPE__, 
                    template_module.__METHOD__, 
                    username, 
                    password
                )

                # Create the directory to store the module's Ansible files
                ansible_dir = self._deploy_dir + "/" + template
                if not os.path.exists(ansible_dir):
                    os.mkdir(ansible_dir)

                # Get the module's bootstrap.yml file
                ansible_deploy = template_module.get_dir() + "/deploy.yml"
                deploy_file = ansible_dir + "/deploy.yml"

                # Check for files
                if not hasattr(template_module, '__DEPLOY_FILES__'):
                    # If no files, there's no paths to change, so just copy the bootstrap file
                    shutil.copyfile(ansible_deploy, deploy_file)
                else:
                    files_dir = ansible_dir + "/files"

                    if not os.path.exists(files_dir):
                        os.mkdir(files_dir)

                    for item in template_module.__DEPLOY_FILES__:
                        shutil.copyfile(template_module.get_dir() + "/files/" + item, files_dir + "/" + item)

                    bs_file = open(ansible_deploy, "r")
                    bs_file_data = bs_file.read()
                    bs_file.close()
                    # Replace +FILE+ placeholder
                    bs_file_data = bs_file_data.replace("+FILES+", os.path.abspath(files_dir))

                    out_bs_file = open(deploy_file, "w+")
                    out_bs_file.write(bs_file_data)
                    out_bs_file.close()

                # Get the module's reboot.yml file
                ansible_reboot = template_module.get_dir() + "/reboot.yml"
                reboot_file = ansible_dir + "/reboot.yml"
                # Copy the reboot file to our working directory
                shutil.copyfile(ansible_reboot, reboot_file)

                system_deploy_inventory.set_group_metadata(template_group, 'ansible_dir', ansible_dir)
                system_deploy_inventory.set_group_metadata(template_group, 'deploy', deploy_file)
                system_deploy_inventory.set_group_metadata(template_group, 'reboot', reboot_file)
                system_deploy_inventory.set_group_metadata(template_group, 'template', template)

                system_deploy_inventory.add_group_var(template_group, 'ansible_become_user', template_module.__BECOME_USER__)
                system_deploy_inventory.add_group_var(template_group, 'ansible_become_method', template_module.__BECOME_METHOD__)
                system_deploy_inventory.add_group_var(template_group, 'ansible_become_pass', password)

            
            system_deploy_inventory.add_host(
                template_group, 
                system_name,
                ip_addr,
                vars=system_vars
            )

        system_deploy_inventory.set_global_var('network_prefix', self.ip_range.prefixlen)
        system_deploy_inventory.set_global_var('network_mask', str(self.ip_range.netmask))
        system_deploy_inventory.set_global_var('network_ext_dns', self.dns_forwarder)
        system_deploy_inventory.set_global_var('network_int_dns', self.network_int_dns)
        system_deploy_inventory.set_global_var('network_gateway', str(list(self.ip_range.hosts())[0]))
        system_deploy_inventory.set_global_var('domain_long', self.domain)
        system_deploy_inventory.set_global_var('domain_short', self.domain_short)
        system_deploy_inventory.set_global_var('domain_admin_pass', self.admin_password)
        system_deploy_inventory.set_global_var('ansible_become', 'yes')
        system_deploy_inventory.set_global_var('dhcp_start', self.dhcp_start)
        system_deploy_inventory.set_global_var('dhcp_end', self.dhcp_end)
        system_deploy_inventory.set_global_var('ansible_winrm_server_cert_validation', 'ignore')
        system_deploy_inventory.set_global_var('network_users', self.users)

        system_inv_path = self._deploy_dir + name + "_deploy_inventory.yml"
        system_deploy_inventory.to_file(system_inv_path)

        logger.info("Inventory file for system deployment created!")

        base_playbook = BasePlaybook()

        if len(system_deploy_inventory.group_list()) == 0:
            logger.info("All deployments seem to be done, continuing on...")
            return True

        for group_name in system_deploy_inventory.group_list():
            
            base_playbook.add_group(
                group_name,
                "Deploy {} system".format(system_deploy_inventory.get_group_metadata(group_name,'template'))
            )

            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(system_deploy_inventory.get_group_metadata(group_name,'deploy')),
                    "name": "Run deploy file"
                }
            )
            base_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(system_deploy_inventory.get_group_metadata(group_name,'reboot')),
                    "name": "Run reboot file"
                }
            )
            base_playbook.add_task(
                group_name,
                {
                    "become": "no",
                    "delegate_to": "localhost",
                    "shell": "touch " + os.path.abspath(self._deploy_dir) + "/{{ inventory_hostname }}.done",
                    "name": "Create the system done file"
                }
            )

        base_playbook_path = self._deploy_dir + name + "_base_playbook.yml"
        base_playbook.to_file(base_playbook_path)

        logger.info("Base playbook file for system deployment created!")

        logger.info("Running Ansible...")

        result = self._dropship.run_ansible(system_inv_path, base_playbook_path)

        if result != 0:
            logger.error("Ansible failed! Please refer to Ansible output for error details.")
            return False

        return True

    def _deploy_services(self):

        
        state_file = StateFile(self._services_configured_state_file)
        state_file.from_file()

        if state_file.is_done():
            logger.warning("Deployment for services already done")
            return True

        return self._do_deploy("services", self.services, state_file)

    def _deploy_clients(self):
        state_file = StateFile(self._clients_configured_state_file)
        state_file.from_file()

        if state_file.is_done():
            logger.warning("Deployment for clients already done")
            return True

        if state_file.has_dhcp():
            logger.info("DHCP option detected, getting host mapping from DHCP server...")
            dhcp_template_module = None
            dhcp_server_info = {}
            for server in self.services:
                if server['role'] == 'dhcp':
                    dhcp_template_module = self._dropship.get_module(server['template'])
                    dhcp_server_info = server
            
            if dhcp_template_module is None:
                logger.error("No DHCP module found!")
                return False

            dhcp_inventory = DropshipInventory()

            services_state_file = StateFile(self._services_configured_state_file)
            services_state_file.from_file()

            username, password = self._dropship.get_image_credentials(dhcp_template_module.__IMAGE__)
            group = 'template'
            dhcp_inventory.add_group(
                group, 
                dhcp_template_module.__OSTYPE__, 
                dhcp_template_module.__METHOD__, 
                username, 
                password
            )

            dhcp_inventory.add_host(
                group, 
                dhcp_server_info['system_name'],
                services_state_file.get_system(dhcp_server_info['system_name'])[2]
            )

            dhcp_inventory.add_group_var(group, 'ansible_become_user', dhcp_template_module.__BECOME_USER__)
            dhcp_inventory.add_group_var(group, 'ansible_become_method', dhcp_template_module.__BECOME_METHOD__)
            dhcp_inventory.add_group_var(group, 'ansible_become_pass', password)
            dhcp_inventory.add_group_var(group, 'ansible_become', 'yes')

            # Create the directory to store the module's Ansible files
            ansible_dir = self._deploy_dir + "/_dhcp/"
            if not os.path.exists(ansible_dir):
                os.mkdir(ansible_dir)

            # Get the module's bootstrap.yml file
            dhcp_file_source = dhcp_template_module.get_dir() + "/dhcp.yml"
            dhcp_file_dest = ansible_dir + "dhcp.yml"

            # Check for files
            if not hasattr(dhcp_template_module, '__DHCPCOLLECT_FILES__'):
                # If no files, there's no paths to change, so just copy the bootstrap file
                shutil.copyfile(dhcp_file_source, dhcp_file_dest)
            else:
                files_dir = ansible_dir + "files"

                if not os.path.exists(files_dir):
                    os.mkdir(files_dir)

                for item in template_module.__DHCPCOLLECT_FILES__:
                    shutil.copyfile(dhcp_template_module.get_dir() + "/files/" + item, files_dir + "/" + item)

                bs_file = open(dhcp_file_source, "r")
                bs_file_data = bs_file.read()
                bs_file.close()
                # Replace +FILE+ placeholder
                bs_file_data = bs_file_data.replace("+FILES+", os.path.abspath(files_dir))

                out_bs_file = open(dhcp_file_dest, "w+")
                out_bs_file.write(bs_file_data)
                out_bs_file.close()


            dhcp_inventory.set_group_metadata(group, 'dhcp_file', dhcp_file_dest)

            output_dir = os.path.abspath(ansible_dir + "fetch/") + "/"
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)
            dhcp_inventory.add_group_var(group, 'dhcp_output_dir', output_dir)

            dhcp_inventory_path = self._deploy_dir + "dhcp_collect_inv.yml"
            dhcp_inventory.to_file(dhcp_inventory_path)

            dhcp_playbook = BasePlaybook()

            for group_name in dhcp_inventory.group_list():
            
                dhcp_playbook.add_group(
                    group_name,
                    "Getting DHCP leases from server"
                )

                dhcp_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(dhcp_inventory.get_group_metadata(group_name,'dhcp_file')),
                        "name": "Run dhcp file"
                    }
                )

            dhcp_playbook_path = self._deploy_dir + "dhcp_playbook.yml"
            dhcp_playbook.to_file(dhcp_playbook_path)

            logger.info("Running DHCP collection Ansible...")

            result = self._dropship.run_ansible(dhcp_inventory_path, dhcp_playbook_path)

            if result != 0:
                logger.error("DHCP collection Ansible failed! Please refer to Ansible output for error details.")
                return False

            dhcp_data_file = open("{}/dhcp.txt".format(output_dir))
            dhcp_data = dhcp_data_file.read()
            dhcp_data_file.close()

            for line in dhcp_data.split("\n"):
                line = line.strip().replace("\r", "")
                if line != "":

                    line_split = line.split("|")

                    state_file.set_ip_by_mac(line_split[0], line_split[1])

            state_file.to_file()

        
        return self._do_deploy("clients", self.clients, state_file)

    def deploy(self):
        
        logger.info("Setting interface to {} network switch".format(self.name))
        self._dropship.provider.set_interface(
            self._dropship.config['commander']['vmid'], 
            self._dropship.config['commander']['interface'], 
            self.switch_id
        )   

        ok = self._deploy_services()

        if ok:
            self._deploy_clients()
        

        # state_file = StateFile(self._clients_configured_state_file)

        # state_file.from_file()

        # post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        # os.mkdir(post_dir)
        
        



        