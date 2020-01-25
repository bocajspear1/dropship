import json
import shutil 
import os
import ipaddress
import importlib

import dropship.constants

from dropship.lib.proxmox import ProxmoxProvider

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
            "connection": connection_to
        })

    def prepare(self):
        # Prepare output directories
        network_dir = dropship.constants.OutDir + "/" + self.name + "/"
        os.mkdir(network_dir)

        bootstrap_dir = dropship.constants.OutDir + "/" + self.name + "/bootstrap"
        os.mkdir(bootstrap_dir)
        
        deploy_dir = dropship.constants.OutDir + "/" + self.name + "/deploy"
        os.mkdir(deploy_dir)

        post_dir = dropship.constants.OutDir + "/" + self.name + "/post"
        os.mkdir(post_dir)
        
        bootstrap_inv = {}

        # Clone out the necessary templates
        for i in range(len(self.routers)):
            router = self.routers[i]
            template = router['template']
            router_name = router['system_name']
            display_name = "{}".format(router_name)
            self._dropship.provider.clone_vm(template, display_name)

        # Create bootstrap config for networking 
        for i in range(len(self.routers)):
            router = self.routers[i]
            template = router['template']
            router_name = router['system_name']
            router_module = self._dropship.load_module(template)
            temp_name = "{}-{}".format(i, router_name)
            print(temp_name)

class Dropship():
    
    def __init__(self, provider_name, config_path, module_path="./modules"):
        if provider_name not in ["proxmox"]:
            raise ValueError("Provider '{}' not supported".format(provider_name))
        
        self._provider_name = provider_name
        self._config_path = config_path
        self._module_path = module_path
        self.networks = []

        # TODO

        self.config = json.load(open(config_path, "r"))

        self.provider = ProxmoxProvider(self.config['proxmox']['host'])

    def load_module(self, module_name):
        module_split = module_name.split(".")
        category = module_split[0]
        name = module_split[1]

        start = self._module_path.replace("./", "").replace("/", ".")

        temp = importlib.import_module(start + "." + category + "." + name)

        module = temp.__MODULE__()

        return module

    def add_network(self, name, switch_id, ip_range):
        net = DropshipNetwork(self, name, switch_id, ip_range)
        self.networks.append(net)
        return net

    def connect(self, username, password):
        self.provider.connect(username, password)

    # Create the Ansible files
    def prepare(self):
        if os.path.exists(dropship.constants.OutDir):
            shutil.rmtree(dropship.constants.OutDir)
        os.mkdir(dropship.constants.OutDir)
        for network in self.networks:
            network.prepare()

    