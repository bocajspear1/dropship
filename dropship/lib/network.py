import ipaddress
import os

import time

import dropship.constants

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
        domain_module = self._dropship.load_module(template)
        self.services.append(domain_module)




    def _networking_bootstrap(self):

       pass

        

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

        # First bootstrap services

        for server in self.services:
            
        
        # deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy"
        # os.mkdir(deploy_dir)

        # post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        # os.mkdir(post_dir)
        
        self._networking_bootstrap()



        