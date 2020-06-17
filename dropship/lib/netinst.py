import ipaddress
import os
import shutil 

import time

import dropship.constants
from dropship.lib.helpers import StateFile, DropshipInventory, BasePlaybook, DoneFile

import logging
logger = logging.getLogger('dropship')

class NetworkInstance():
    def __init__(self, defname, switch_id, ip_range, prefix=""):
        self.defname = defname
        self.name = "{}{}_{}".format(prefix, defname, int(time.time()))
        self.switch_id = switch_id
        self.ip_range = ipaddress.ip_network(ip_range)
        
        self._vars = {}

        self._hosts = {}
        self._users = {}

        self._network_dir = ""
        self._bootstrap_dir = ""
        self._deploy_dir = ""
        self._post_dir = ""

        self._clients_configured_state_file = ""
        self._services_configured_state_file = ""

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

    def add_host(self, host_obj):
        self._hosts[host_obj.hostname] = host_obj

    def set_var(self, var_name, var_value):
        self._vars[var_name] = var_value

    def var_check(self):
        for net_var in dropship.constants.RequiredVariablesNetwork:
            if net_var not in self._vars:
                logger.error("Required network variable '{}' not found".format(net_var))
                return False

        return True

    def do_build(self, dropship):
        pass