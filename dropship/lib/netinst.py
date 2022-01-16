import ipaddress
import os
import shutil 

import time

import dropship.constants
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook, DoneFile

import logging
logger = logging.getLogger('dropship')

class NetworkInstance():
    def __init__(self, instname, defname, switch_id, ip_range, prefix=""):
        self.defname = defname
        self.name = instname
        self.switch_id = switch_id
        self.ip_range = ipaddress.ip_network(ip_range)
        
        self._vars = {}

        self._hosts = {}
        self._routers = {}
        self._users = {}

        self._postmods = []

        self._network_dir = ""
        self._bootstrap_dir = ""
        self._deploy_dir = ""
        self._post_dir = ""

        self._bootstrap_dir = ""
        self._clients_configured_state_file = ""
        self._services_configured_state_file = ""

        self._prefix = prefix

    @property
    def vars(self):
        return self._vars

    def describe(self):
        print("Network instance '{}'".format(self.name))
        print("Instance of network '{}'".format(self.defname))
        print("IP address range: {}".format(self.ip_range.with_prefixlen))
        print("=== HOSTS ===")
        for host in self._hosts:
            print("  * {}".format(host)) 
            print("      Role: {}".format(self._hosts[host].role))     
            print("      IP: {}".format(self._hosts[host].ip_addr))     

        print("=== VARIABLES ===")
        for var in self._vars:
            print("  {}: {}".format(var, self._vars[var]))

    @property
    def has_dhcp(self):
        for hostname in self._hosts:
            print(self._hosts[hostname].ip_addr)
            if self._hosts[hostname].ip_addr == 'dhcp':
                return True

        return False
    
    def add_postmod(self, post_module):
        self._postmods.append(post_module)

    def add_host(self, host_obj):
        self._hosts[host_obj.hostname] = host_obj

    def add_user(self, user_obj):
        self._users[user_obj.username] = user_obj

    def set_var(self, var_name, var_value):
        self._vars[var_name] = var_value

    def var_check(self):
        for net_var in dropship.constants.RequiredVariablesNetwork:
            if net_var not in self._vars:
                logger.error("Required network variable '{}' not found".format(net_var))
                return False

        return True

    def get_clients(self):
        return_list = []
        for hostname in self._hosts:
            if self._hosts[hostname].role in ("client",):
                return_list.append(self._hosts[hostname])
        
        return return_list

    def get_services(self):
        domain = []
        dhcp = []
        other_services = []
        for hostname in self._hosts:
            if self._hosts[hostname].role == "domain":
                domain.append(self._hosts[hostname])
            elif self._hosts[hostname].role == "dhcp":
                dhcp.append(self._hosts[hostname])
            elif self._hosts[hostname].role in ("service",):
                other_services.append(self._hosts[hostname])
        
        return domain + dhcp + other_services

    def get_routers(self):
        return_list = []
        for hostname in self._hosts:
            if self._hosts[hostname].role == "router":
                return_list.append(self._hosts[hostname])
        
        return return_list

    def _get_bootstrap_state_file(self, builder, filename, host_list):

        state_file = StateFile(self._bootstrap_dir + "/bootstrap_" + filename + ".state")

        if not state_file.exists():
            
            logger.info("Cloning systems...")
            for i in range(len(host_list)):
                host = host_list[i]
                hostname = host.hostname
                host_mod = builder.mm.get_module(host.module_name)

                state_file.add_system(hostname)

                display_name = "{}{}".format(self._prefix, hostname)
                vmid = builder.provider.clone_vm(host_mod.__IMAGE__, display_name)
                if vmid == 0:
                    logger.error("Failed to clone VM for {}".format(display_name))
                    return False
                host_list[i].vmid = vmid
                state_file.set_vmid(hostname, vmid)
                builder.add_vmid(vmid)

            # Wait for clones
            logger.info("Waiting for clones to complete...")
            builder.provider.wait()
            
            logger.info("Configuring networking and starting systems...")
            for i in range(len(host_list)):
                vmid = host_list[i].vmid
                hostname = host_list[i].hostname
                bootstrap_switch = builder.config['bootstrap']['switch']
                # Set the interface to be on bootstrap switch
                builder.provider.set_interface(vmid, 0, bootstrap_switch)

                # While we are here, get the mac address for this interface
                mac_addr = builder.provider.get_interface(vmid, 0)['mac'].lower()
                state_file.set_mac(hostname, mac_addr)
                host_list[i].mac = mac_addr

                time.sleep(1)
                builder.provider.start_vm(vmid)

            # Get IP mappings
            mac_map = builder.wait_for_address_map(state_file.get_all_macs())

            for host in host_list:
                state_file.set_ip(host.hostname, mac_map[host.mac])

            # Write a state file
            state_file.to_file()
        else:
            logger.info("Using existing {} state file".format(filename))

        state_file.from_file()
        return state_file

    def _get_bootstrap_inventory(self, builder, state_file, host_list):
        # Fill in data from state file
        for i in range(len(host_list)):
            state_file_data = state_file.get_system(host_list[i].hostname)
            host_list[i].vmid = state_file_data[0]
            host_list[i].connect_ip = state_file_data[2]

        host_inv = DropshipInventory()

        # Set vars for pre-inventory
        for i in range(len(host_list)):
            router_mod = builder.mm.get_module(host_list[i].module_name)
            # Ensure module files are set up
            router_mod.prepare_bootstrap(builder.mm.out_path)

            host_list[i].vars['new_ip'] = host_list[i].ip_addr

        host_inv.from_host_list(builder.mm, builder.config['credentials'], host_list)

        for var in self._vars:
            host_inv.set_global_var(var, self._vars[var])

        return host_inv

    def _get_bootstrap_playbook(self, builder, system_type, inventory):
        bootstrap_playbook = BasePlaybook()

        for group_name in inventory.group_list():
            bootstrap_playbook.add_group(
                group_name,
                "Bootstrap {} {}".format(group_name, system_type)
            )

            bootstrap_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(inventory.get_group_metadata(group_name, 'bootstrap_path')),
                    "name": "Run bootstrap file"
                }
            )
            bootstrap_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(inventory.get_group_metadata(group_name, 'shutdown_path')),
                    "name": "Run shutdown file"
                }
            )
        
        return bootstrap_playbook

    # Run bootstrap for this instance
    # The bootstrap also populates the VMID for the hosts
    def run_bootstrap(self, builder):
        self._bootstrap_dir = builder.ensure_subdir("sys_services_bootstrap")
        
        services_list = self.get_services()

        builder.dnsmasq.start()
        services_state_file = self._get_bootstrap_state_file(builder, "services", services_list)

        if not services_state_file.is_done():     
            logger.info("Generating services bootstrap inventory files...")

            services_inv = self._get_bootstrap_inventory(builder, services_state_file, services_list)

            services_inv_path = self._bootstrap_dir + "/inventory.yml"
            services_inv.to_file(services_inv_path)

            services_playbook = self._get_bootstrap_playbook(builder, "services", services_inv)

            services_playbook_path = self._bootstrap_dir + "/base_playbook.yml"
            services_playbook.to_file(services_playbook_path)

            logger.info("Services inventory files created!")

            logger.info("Running services bootstrap Ansible")
            result = builder.run_ansible(services_inv_path, services_playbook_path)

            if result != 0:
                logger.error("Services Ansible bootstrap failed!")
                return False

            # Move hosts to the network's switch and restart them
            for service in services_list:
                builder.provider.set_interface(service.vmid, 0, self.switch_id)
                builder.provider.wait_until_shutdown(service.vmid)
                builder.provider.start_vm(service.vmid)
            
            services_state_file.mark_done() 
        else:
            logger.warning("Services bootstrap has already been completed for network {}".format(self.name))
        
        

        self._bootstrap_dir = builder.ensure_subdir("sys_clients_bootstrap")

        clients_list = self.get_clients()

        clients_state_file = self._get_bootstrap_state_file(builder, "clients", clients_list)

        if not clients_state_file.is_done():
            logger.info("Generating client bootstrap inventory files...")

            clients_inv = self._get_bootstrap_inventory(builder, clients_state_file, clients_list)

            clients_inv_path = self._bootstrap_dir + "/inventory.yml"
            clients_inv.to_file(clients_inv_path)

            clients_playbook = self._get_bootstrap_playbook(builder, "clients", clients_inv)

            clients_playbook_path = self._bootstrap_dir + "/base_playbook.yml"
            clients_playbook.to_file(clients_playbook_path)

            logger.info("Client inventory files created!")

            logger.info("Running clients bootstrap Ansible")
            result = builder.run_ansible(clients_inv_path, clients_playbook_path)

            if result != 0:
                logger.error("Clients Ansible bootstrap failed!")
                return False

            # Move hosts to the network's switch and restart them
            for client in clients_list:
                builder.provider.set_interface(client.vmid, 0, self.switch_id)     
                builder.provider.wait_until_shutdown(client.vmid)
                # Don't restart the clients, we will wait until DHCP service is set up
                # This also makes sure clients don't get bootstrap DHCP

            clients_state_file.mark_done()
        else:
            logger.warning("Client bootstrap has already been completed for network {}".format(self.name))
        
        builder.dnsmasq.stop()
        # Since we have access to the state files, load the vmid for our current hosts
        for hostname in self._hosts:
            if services_state_file.has_system(hostname):
                state_file_data = services_state_file.get_system(hostname)
                self._hosts[hostname].vmid = state_file_data[0]
                self._hosts[hostname].mac = state_file_data[1]
            elif clients_state_file.has_system(hostname):
                state_file_data = clients_state_file.get_system(hostname)
                self._hosts[hostname].vmid = state_file_data[0]
                self._hosts[hostname].mac = state_file_data[1]
         
        return True

    def _get_deploy_inventory(self, builder, host_list):

        for i in range(len(host_list)):
            # Trust we already set the DHCP address
            if host_list[i].ip_addr != 'dhcp':
                host_list[i].connect_ip = host_list[i].ip_addr

        host_inv = DropshipInventory()

        # Set vars for inventory
        for i in range(len(host_list)):
            router_mod = builder.mm.get_module(host_list[i].module_name)
            # Ensure module files are set up
            router_mod.prepare_deploy(builder.mm.out_path)

        host_inv.from_host_list(builder.mm, builder.config['credentials'], host_list)

        for var in self._vars:
            host_inv.set_global_var(var, self._vars[var])

        user_list = []
        for username in self._users:
            user_list.append(self._users[username].to_dict())
        host_inv.set_global_var('network_users', user_list)

        return host_inv

    def _get_deploy_playbook(self, builder, system_type, inventory):
        bootstrap_playbook = BasePlaybook()

        for group_name in inventory.group_list():
            bootstrap_playbook.add_group(
                group_name,
                "Deploy {} {}".format(group_name, system_type)
            )

            bootstrap_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(inventory.get_group_metadata(group_name, 'deploy_path')),
                    "name": "Run bootstrap file"
                }
            )
            bootstrap_playbook.add_task(
                group_name,
                {
                    "include_tasks": os.path.abspath(inventory.get_group_metadata(group_name, 'shutdown_path')),
                    "name": "Run shutdown file"
                }
            )
        
        return bootstrap_playbook

    def _deploy_routers(self, builder):
        router_dir = builder.ensure_subdir("sys_routers_deploy")

        routers_list = self.get_routers()

        deploy_done_file = DoneFile(router_dir + "/router_deploy.done")

        if not deploy_done_file.is_done():

            for i in range(len(routers_list)):
                router_mod = builder.mm.get_module(routers_list[i].module_name)
                # Ensure module files are set up
                router_mod.prepare_deploy(builder.mm.out_path)
                print(routers_list[i].vmid)
                conf_iface = routers_list[i].interfaces[1]
                if conf_iface.has_offset():
                    conf_iface.set_offset_addr(self.ip_range)
                routers_list[i].connect_ip = str(conf_iface.ip_addr)
                print(routers_list[i].connect_ip)
            
            router_deploy_inv = DropshipInventory()
            router_deploy_inv.from_host_list(builder.mm, builder.config['credentials'], routers_list)
            deploy_inventory_path = router_dir + "/inventory.yml"
            router_deploy_inv.to_file(deploy_inventory_path)

            deploy_playbook = BasePlaybook()

            # Create the deploy playbook
            for group_name in router_deploy_inv.group_list():
                deploy_playbook.add_group(
                    group_name,
                    "Deploy {} routers".format(group_name)
                )

                deploy_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(router_deploy_inv.get_group_metadata(group_name, 'deploy_path')),
                        "name": "Run deploy file"
                    }
                )
                deploy_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(router_deploy_inv.get_group_metadata(group_name, 'shutdown_path')),
                        "name": "Run shutdown file"
                    }
                )

            deploy_playbook_path = router_dir + "/deploy_playbook.yml"
            deploy_playbook.to_file(deploy_playbook_path)

            logger.info("Running router deploy Ansible")
            result = builder.run_ansible(deploy_inventory_path, deploy_playbook_path)

            if result != 0:
                logger.error("Ansible deploy failed!")
                return

            time.sleep(10)
            logger.info("Restarting routers")
            for i in range(len(routers_list)):
                vmid = routers_list[i].vmid
                builder.provider.wait_until_shutdown(vmid)
                builder.provider.start_vm(vmid)
            
            deploy_done_file.mark_done()
        else:
            logger.warning("Router deploy has already been completed")

        return True

    def _deploy_services(self, builder):
        services_dir = builder.ensure_subdir("sys_services_deploy")

        deploy_done_file = DoneFile(services_dir + "/services_deploy.done")

        if not deploy_done_file.is_done():

            services_list = self.get_services()
            if 'snapshots' in builder.config:
                if 'pre_deploy' in builder.config['snapshots'] and builder.config['snapshots']['pre_deploy'] == True:
                    for service in services_list:
                        logger.info("Creating pre-deploy snapshot for VM {}[{}]".format(service.hostname, service.vmid))
                        error, ok = builder.provider.snapshot_vm(service.vmid, "pre_deploy")

                        if error is not None:
                            logger.error("Snapshot failed! - {}".format(error))
                            return False
                
                    logger.info("Waiting for snapshots to complete...")
                    builder.provider.wait()
            
                
            services_inv_path = services_dir + "/inventory.yml"
            services_inv = self._get_deploy_inventory(builder, services_list)
            services_inv.to_file(services_inv_path)
            service_playbook_path = services_dir + "/base_playbook.yml"
            service_playbook = self._get_deploy_playbook(builder, "services", services_inv)
            service_playbook.to_file(service_playbook_path)

            logger.info("Running services deploy Ansible")
            result = builder.run_ansible(services_inv_path, service_playbook_path)

            if result != 0:
                logger.error("Ansible deploy failed!")
                return False

            # Immediately restart services
            time.sleep(10)
            for service in services_list:
                builder.provider.wait_until_shutdown(service.vmid)
                builder.provider.start_vm(service.vmid)

            
            deploy_done_file.mark_done()
        else:
            logger.warning("Services deploy has already been completed")

        return True

    def _deploy_clients(self, builder):
        clients_dir = builder.ensure_subdir("sys_clients_deploy")

        deploy_done_file = DoneFile(clients_dir + "/clients_deploy.done")

        if not deploy_done_file.is_done():

            clients_list = self.get_clients()

            for i in range(len(clients_list)):
                clients_list[i].connect_ip = clients_list[i].ip_addr

            if 'snapshots' in builder.config:
                if 'pre_deploy' in builder.config['snapshots'] and builder.config['snapshots']['pre_deploy'] == True:
                    for client in clients_list:
                        logger.info("Creating pre-deploy snapshot for VM {}[{}]".format(client.hostname, client.vmid))
                        error, ok = builder.provider.snapshot_vm(client.vmid, "pre_deploy")

                        if error is not None:
                            logger.error("Snapshot failed! - {}".format(error))
                            return False
                
                    logger.info("Waiting for snapshots to complete...")
                    builder.provider.wait()

            # Clients were not immediately restarted when bootstrapped, do that now
            for client in clients_list:
                builder.provider.wait_until_shutdown(client.vmid)
                builder.provider.start_vm(client.vmid)

            if self.has_dhcp:
                logger.info("DHCP option detected, getting host mapping from DHCP server...")
                dhcp_server_host = None
                dhcp_server_mod = None
                for hostname in self._hosts:
                    if self._hosts[hostname].role == "dhcp" and dhcp_server_mod is None:
                        logger.info("Found DHCP server '{}'".format(hostname))
                        dhcp_server_mod = builder.mm.get_module(self._hosts[hostname].module_name)
                        dhcp_server_host = self._hosts[hostname]

                if dhcp_server_mod is None:
                    logger.error("dhcp address set, but found no DHCP server")
                    return False
                

                dhcp_done = False

                while not dhcp_done:
                    time.sleep(15)

                    dhcp_inventory = DropshipInventory()
                    dhcp_server_host.connect_ip = dhcp_server_host.ip_addr
                    dhcp_inventory.from_host_list(builder.mm, builder.config['credentials'], [dhcp_server_host])
                    dhcp_server_mod.prepare_dhcp(builder.mm.out_path)
                    dhcp_group = list(dhcp_inventory.group_list())[0]

                    dhcp_collect_dir = os.path.abspath(builder.ensure_subdir("sys_clients_deploy/_dhcp")) + "/"

                    dhcp_inventory.set_group_metadata(dhcp_group, 'dhcp_file', dhcp_server_mod.get_dhcp_path(builder.mm.out_path))
                    dhcp_inventory.add_group_var(dhcp_group, 'dhcp_output_dir', dhcp_collect_dir)

                    dhcp_inventory_path = clients_dir + "/dhcp_collect_inv.yml"
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
                                "include_tasks": os.path.abspath(dhcp_inventory.get_group_metadata(group_name, 'dhcp_file')),
                                "name": "Run dhcp file"
                            }
                        )

                    dhcp_playbook_path = clients_dir + "/dhcp_playbook.yml"
                    dhcp_playbook.to_file(dhcp_playbook_path)

                    logger.info("Running DHCP collection Ansible...")

                    result = builder.run_ansible(dhcp_inventory_path, dhcp_playbook_path)

                    if result != 0:
                        logger.error("DHCP collection Ansible failed! Please refer to Ansible output for error details.")
                        return False

                    dhcp_data_file = open("{}/dhcp.txt".format(dhcp_collect_dir))
                    dhcp_data = dhcp_data_file.read()
                    dhcp_data_file.close()

                    for line in dhcp_data.split("\n"):
                        line = line.strip().replace("\r", "")
                        if line == "":
                            continue
                        line_split = line.split("|")
                        mac_addr = line_split[0]
                        ip_addr = line_split[1]
                        for i in range(len(clients_list)):
                            print(clients_list[i].mac, mac_addr.lower())
                            if clients_list[i].mac.lower() == mac_addr.lower():
                                clients_list[i].connect_ip = ip_addr
                                print(clients_list[i].connect_ip, ip_addr)

                    all_addr_set = True
                    dhcp_host_list = []
                    for client in clients_list:
                        if client.connect_ip == 'dhcp':
                            all_addr_set = False

                    if all_addr_set == False:
                        logger.info("Waiting for server to set all IPs")
                        time.sleep(45)
                    else:
                        dhcp_done = True

                client_state_file = StateFile(clients_dir + "/clients.state")
                client_state_file.from_host_list(clients_list)
                client_state_file.to_file()

            
            clients_inv_path = clients_dir + "/inventory.yml"
            clients_inv = self._get_deploy_inventory(builder, clients_list)
            clients_inv.to_file(clients_inv_path)
            clients_playbook_path = clients_dir + "/base_playbook.yml"
            clients_playbook = self._get_deploy_playbook(builder, "clients", clients_inv)
            clients_playbook.to_file(clients_playbook_path)

            logger.info("Running clients deploy Ansible")
            result = builder.run_ansible(clients_inv_path, clients_playbook_path)

            time.sleep(10)
            for client in clients_list:
                builder.provider.wait_until_shutdown(client.vmid)
                builder.provider.start_vm(client.vmid)

            if result != 0:
                logger.error("Ansible deploy failed!")
                return False
            deploy_done_file.mark_done()
        else:
            logger.warning("Clients deploy has already been completed")

        return True

    def run_deploy(self, builder):
        self._deploy_dir = builder.ensure_subdir("sys_services_deploy")

        # Move the commander VM to the instance's switch
        builder.provider.set_interface(builder.config['commander']['vmid'], builder.config['commander']['interface'], self.switch_id)        

        logger.info("Running router deploy...")
        ok = self._deploy_routers(builder)
        if not ok:
            return False

        logger.info("Running services deploy...")
        ok = self._deploy_services(builder)
        if not ok:
            return False

        logger.info("Running clients deploy...")
        ok = self._deploy_clients(builder)
        if not ok:
            return False

        return True

    def run_post(self, builder):

        # Move the commander VM to the instance's switch
        builder.provider.set_interface(builder.config['commander']['vmid'], builder.config['commander']['interface'], self.switch_id)        

        # Add domain credentials to credential map
        builder.config['credentials']["DOMAIN"] = "{}@{}:{}".format(self._vars['domain_admin_username'], self._vars['domain_long'], self._vars['domain_admin_password']) 

        clients_dir = builder.ensure_subdir("sys_clients_deploy")

        client_state_file = StateFile(clients_dir + "/clients.state")
        client_state_file.from_file()

        # Fill in data from state file
        for hostname in self._hosts:
            if client_state_file.has_system(hostname):
                state_file_data = client_state_file.get_system(hostname)
                self._hosts[hostname].connect_ip = state_file_data[2]

        # Ensure modules are all set up
        for module in self._postmods:
            mod_obj = builder.mm.get_module(module.module_name)
            if hasattr(mod_obj, 'before_post'):
                logger.info("Running 'before_post' for module {}".format(module.module_name))
                mod_obj.before_post(builder)
            mod_obj.prepare_post(builder.mm.out_path)

        post_dir = builder.ensure_subdir("sys_all_post")

        post_done_file = DoneFile(post_dir + "/post_run.done")

        if not post_done_file.is_done():

            post_inv_path = post_dir + "/inventory.yml"

            post_inv = DropshipInventory()
            post_inv.from_postmod_list(builder.mm, builder.config['credentials'], self._postmods, self._hosts)

            for var in self._vars:
                post_inv.set_global_var(var, self._vars[var])

            post_inv.to_file(post_inv_path)

            post_playbook = BasePlaybook()

            for group_name in post_inv.group_list():
                
                post_playbook.add_group(
                    group_name,
                    "Run post module '{}'".format(group_name)
                )

                post_playbook.add_task(
                    group_name,
                    {
                        "include_tasks": os.path.abspath(post_inv.get_group_metadata(group_name, 'post_path')),
                        "name": "Run post file"
                    }
                )

            post_playbook_path = post_dir + "/base_playbook.yml"
            post_playbook.to_file(post_playbook_path)

            logger.info("Running post module Ansible")
            result = builder.run_ansible(post_inv_path, post_playbook_path)

            if result != 0:
                logger.error("Ansible for post modules failed!")
                return False
            post_done_file.mark_done()
        else:
            logger.warning("Services deploy has already been completed")

        return True
        