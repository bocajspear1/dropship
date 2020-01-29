import json
import shutil 

import importlib
import time

import os

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
        

        # TODO

        self.config = json.load(open(config_path, "r"))

        self.provider = ProxmoxProvider(self.config['proxmox'], self.config['vm_map'])
        self.dnsmasq = DropshipDNSMasq(self.config['bootstrap'])

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
    def bootstrap(self):
        self.dnsmasq.start()

        
        if os.path.exists(dropship.constants.OutDir):
            shutil.rmtree(dropship.constants.OutDir)
        os.mkdir(dropship.constants.OutDir)


        for network in self.networks:
            network.bootstrap()

    def complete(self):
        self.dnsmasq.stop()

    