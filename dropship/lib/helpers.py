import os
from datetime import datetime

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
                line_split = line.split("|")
                self.add_entry(line_split[0], line_split[1], line_split[2], line_split[3])

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

class BasePlaybook(self):
    
    def __init__(self, name):
        self.name = name
        self.groups = []
        self.group_data = {}

    def add_group(self, group_name,)

    def add_task(self, group, ):
        if not group in self.groups:
            raise ValueError("Invalid group")