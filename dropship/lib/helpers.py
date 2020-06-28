import os
from datetime import datetime
import copy
import subprocess
import importlib

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import logging
logger = logging.getLogger('dropship')

class ModuleManager():
    def __init__(self, out_path, module_path="./modules"):
        self._module_cache = {}
        self._module_path = module_path
        self.out_path =out_path

    def get_module(self, module_name):
        if module_name in self._module_cache:
            return self._module_cache[module_name]

        start = self._module_path.replace("./", "").replace("/", ".")

        temp = importlib.import_module(start + "." + module_name)

        module = temp.__MODULE__()

        self._module_cache[module_name] = module

        return module


def get_command_path(command):
    return subprocess.check_output(["/bin/sh", '-c', 'which {}'.format(command)]).strip().decode()

# Essentially just a flag indicating if a system has been bootstrapped/deployed
class DoneFile():
    def __init__(self, path):
        self.path = path

    def is_done(self):
        if os.path.exists(self.path):
            return True
        return False

    def mark_done(self):
        donefile = open(self.path, "w+")
        donefile.write("Done at {}\n".format(datetime.now().isoformat()))
        donefile.close()

# Stores data about in process deployments
class StateFile():
    def __init__(self, path):
        self.lines = []
        self.path = path
        self._done_file = DoneFile(self.path + ".done")
    
    def clone(self, path):
        the_clone = StateFile(path)
        the_clone.lines = copy.deepcopy(self.lines)
        return the_clone

    def exists(self):
        if os.path.exists(self.path):
            return True
        return False

    def is_done(self):
        return self._done_file.is_done()

    def mark_done(self):
        self._done_file.mark_done()

    def has_system(self, system_name):
        for line in self.lines:
            if line[0] == system_name:
                return True
        return False

    def add_full_entry(self, system_name, vmid, mac_addr, ip_addr):
        self.lines.append([system_name, vmid, mac_addr, ip_addr])

    def add_system(self, system_name):
        if not self.has_system(system_name):
            self.lines.append([system_name, 0, "", ""])
    
    def get_system(self, system_name):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                return self.lines[i][1], self.lines[i][2], self.lines[i][3]
        return None, None, None

    def set_mac(self, system_name, mac_addr):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                self.lines[i][2] = mac_addr
                return True
        return False

    def set_vmid(self, system_name, vmid):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                self.lines[i][1] = vmid
                return True
        return False

    def get_vmid(self, system_name):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                return self.lines[i][1]
        return 0

    def set_ip(self, system_name, ip_addr):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                self.lines[i][3] = ip_addr
                return True
        return False

    def set_ip_by_mac(self, mac, ip_addr):
        for i in range(len(self.lines)):
            if self.lines[i][2].lower() == mac.lower():
                self.lines[i][3] = ip_addr
                return True
        return False

    def has_dhcp(self):
        for i in range(len(self.lines)):
            if self.lines[i][3].lower() == 'dhcp':
                return True
        return False

    def from_file(self):
        self.lines = []
        if self.exists():
            infile = open(self.path, "r")
            infile_data = infile.read()
            infile.close()
            file_lines = infile_data.split("\n")
            for line in file_lines:
                if line.strip() != "":
                    line_split = line.split("|")
                    self.add_full_entry(line_split[0], line_split[1], line_split[2], line_split[3])

    def to_file(self):
        outfile = open(self.path, "w+")
        for line in self.lines:
            outfile.write("{}|{}|{}|{}\n".format(line[0], line[1], line[2], line[3]))
        outfile.close()

    def get_all_macs(self):
        mac_list = []
        for line in self.lines:
            mac = line[2]
            if mac != "":
                mac_list.append(mac)
        return mac_list
    
    def from_host_list(self, host_list):
        for host in host_list:
            self.add_full_entry(host.hostname, host.vmid, host.mac, host.connect_ip)


# Stores inventory information that is put into an Ansible inventory file
class DropshipInventory():
    
    def __init__(self):
        self.groups = {}
        self._group_metadata = {}
        self._vars = {}

    def set_global_var(self, key, value):
        self._vars[key] = value
    
    def group_list(self):
        return self.groups.keys()

    def has_group(self, group_name):
        return group_name in self.groups

    def add_group(self, group_name, os_type, connection_type, username, password):
        self.groups[group_name] = {
            "hosts": {},
            "vars": {
                "ansible_connection": connection_type,
                "ansible_network_os": os_type,
                "ansible_user": username,
                "ansible_password": password
            }
        }
        self._group_metadata[group_name] = {}

    def set_group_metadata(self, group_name, key, value):
        self._group_metadata[group_name][key] = value

    def get_group_metadata(self, group_name, key):
        return self._group_metadata[group_name][key]

    def add_group_var(self, group_name, var_name, var_value):
        self.groups[group_name]['vars'][var_name] = var_value

    def add_host(self, group_name, host_name, host_addr, vars=None):
        self.groups[group_name]['hosts'][host_name] = {
            "ansible_host": host_addr
        }

        if vars is not None:
            self.groups[group_name]['hosts'][host_name].update(vars)


    def get_inventory(self):
        return {
            "all": {
                "children": self.groups,
                "vars": self._vars,
                "hosts": {
                    "localhost": {
                        "ansible_become": 'no'
                    }
                }
            },
            
        }

    def to_file(self, path): 
        inv_data_out = dump(self.get_inventory(), Dumper=Dumper)

        out_file = open(path, "w+")
        
        out_file.write(inv_data_out)
        out_file.close()

    def from_postmod_list(self, mm, cred_map, postmod_list, host_map):
        for module_data in postmod_list:
            postmod = mm.get_module(module_data.module_name)
            postmod_group = postmod.__NAME_NORMALIZED__

            if not self.has_group(postmod_group):
                username = None
                password = None
                if postmod.__IMAGE__ in cred_map:
                    cred_split = cred_map[postmod.__IMAGE__].split(":")
                    username = cred_split[0]
                    password = cred_split[1]
                else:
                    logger.error("Could not find credentials for image '{}'".format(postmod.__IMAGE__))
                    return False
                self.add_group(
                    postmod_group, 
                    postmod.__OSTYPE__, 
                    postmod.__METHOD__,
                    username,
                    password
                )
                self.set_group_metadata(postmod_group, 'post_path', postmod.get_post_path(mm.out_path))

                if hasattr(postmod, '__BECOME_USER__'):
                    if postmod.__IMAGE__ != "DOMAIN":
                        self.add_group_var(postmod_group, 'ansible_become_user', postmod.__BECOME_USER__)
                    else:
                        self.add_group_var(postmod_group, 'ansible_become_user', username)
                    self.add_group_var(postmod_group, 'ansible_become_method', postmod.__BECOME_METHOD__)
                    self.add_group_var(postmod_group, 'ansible_become_pass', password)
                    self.add_group_var(postmod_group, 'ansible_become', 'yes')
                
                if postmod.__OSTYPE__ == "windows":
                    self.add_group_var(postmod_group, 'ansible_winrm_server_cert_validation', 'ignore')
            
            host_data = host_map[module_data.hostname]

            new_vars = {}
            for var_name in module_data.vars:
                new_vars["var_" + var_name] = module_data.vars[var_name]

            self.add_host(postmod_group, host_data.hostname, host_data.connect_ip, vars=new_vars)

    def from_host_list(self, mm, cred_map, host_list, name_prefix=""):
        for host in host_list:
            host_mod = mm.get_module(host.module_name)
            host_mod_group = host_mod.__NAME_NORMALIZED__

            if not self.has_group(host_mod_group):
                username = None
                password = None
                if host_mod.__IMAGE__ in cred_map:
                    cred_split = cred_map[host_mod.__IMAGE__].split(":")
                    username = cred_split[0]
                    password = cred_split[1]
                else:
                    logger.error("Could not find credentials for image '{}'".format(host_mod.__IMAGE__))
                    return False
                self.add_group(
                    host_mod_group, 
                    host_mod.__OSTYPE__, 
                    host_mod.__METHOD__,
                    username,
                    password
                )
                self.set_group_metadata(host_mod_group, 'bootstrap_path', host_mod.get_bootstrap_path(mm.out_path))
                self.set_group_metadata(host_mod_group, 'reboot_path', host_mod.get_reboot_path(mm.out_path))
                self.set_group_metadata(host_mod_group, 'deploy_path', host_mod.get_deploy_path(mm.out_path))
               

                if hasattr(host_mod, '__BECOME_USER__'):
                    self.add_group_var(host_mod_group, 'ansible_become_user', host_mod.__BECOME_USER__)
                    self.add_group_var(host_mod_group, 'ansible_become_method', host_mod.__BECOME_METHOD__)
                    self.add_group_var(host_mod_group, 'ansible_become_pass', password)
                    self.add_group_var(host_mod_group, 'ansible_become', 'yes')
                
                if host_mod.__OSTYPE__ == "windows":
                    self.add_group_var(host_mod_group, 'ansible_winrm_server_cert_validation', 'ignore')
            
            self.add_host(host_mod_group, "{}{}".format(name_prefix, host.hostname), host.connect_ip, vars=host.vars)
            


class BasePlaybook():
    
    def __init__(self):
        self.groups = []
        self.group_data = {}

    def add_group(self, host_group, group_desc, gather_facts=False):
        self.groups.append(host_group)
        gather = "no"
        if gather_facts:
            gather = "yes"
        self.group_data[host_group] = {
            "name": group_desc,
            "gather_facts": gather,
            "hosts": host_group,
            "tasks": []
        }

    def add_task(self, host_group, task):
        if not host_group in self.groups:
            raise ValueError("Invalid group")
        self.group_data[host_group]['tasks'].append(task)

    def get_playbook(self):
        playbook = []
        for group in self.groups:
            playbook.append(self.group_data[group])
        return playbook
    
    def to_file(self, path): 
        inv_data_out = dump(self.get_playbook(), Dumper=Dumper)

        out_file = open(path, "w+")
        
        out_file.write(inv_data_out)
        out_file.close()