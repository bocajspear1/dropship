import os
from datetime import datetime

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


# Stores data about in process deployments
class StateFile():
    def __init__(self, path):
        self.lines = []
        self.path = path

    def exists(self):
        if os.path.exists(self.path):
            return True
        return False

    def is_done(self):
        if os.path.exists(self.path + ".done"):
            return True
        return False

    def mark_done(self):
        donefile = open(self.path + ".done", "w+")
        donefile.write("Done at {}".format(datetime.now().isoformat()))
        donefile.close()

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

    def set_ip(self, system_name, ip_addr):
        for i in range(len(self.lines)):
            if self.lines[i][0] == system_name:
                self.lines[i][3] = ip_addr
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