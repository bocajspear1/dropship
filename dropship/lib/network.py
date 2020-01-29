import ipaddress
import os
import logging

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

    def add_router(self, template, system_name, connection_to):
        self.routers.append({
            "template": template,
            "system_name": system_name,
            "connection": connection_to,
            "vmid": 0
        })

    def bootstrap(self):
        # Nootstrap output directories
        network_dir = dropship.constants.OutDir + "/" + self.name + "/"
        os.mkdir(network_dir)

        bootstrap_dir = dropship.constants.OutDir + "/" + self.name + "/bootstrap"
        os.mkdir(bootstrap_dir)
        
        deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy"
        os.mkdir(deploy_dir)

        post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        os.mkdir(post_dir)
        
        bootstrap_inv = {}


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
        
        for i in range(len(self.routers)):
            vmid = self.routers[i]['vmid']
            bootstrap_switch = self._dropship.config['bootstrap']['switch']
            # For first round addressing
            self._dropship.provider.set_interface(vmid, 0, bootstrap_switch)
            # For second round addressing
            self._dropship.provider.set_interface(vmid, 1, bootstrap_switch)

        # Create bootstrap config for networking 
        for i in range(len(self.routers)):
            router = self.routers[i]
            template = router['template']
            router_name = router['system_name']
            router_module = self._dropship.load_module(template)
            temp_name = "{}-{}".format(i, router_name)
            print(temp_name)