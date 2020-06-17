import shlex 
import logging
import re

from dropship.lib.helpers import ModuleManager
from dropship.lib.netinst import NetworkInstance
from dropship.lib.host import Host

logger = logging.getLogger('dropship')

class NetworkDefinition():

    def __init__(self, def_data, module_path=None):
        self._def_data = def_data
        self.name = ""
        self.range = ""
        self.domain = None
        self.vars = {}
        self._seen_roles = []
        self._dhcp_seen = False
        self._domain = None
        self._hosts = []
        if module_path is None:
            self.mm = ModuleManager()
        else:
            self.mm = ModuleManager(module_path=module_path)

    def parse(self):
        lines = self._def_data.split("\n")
        for line in lines:
            line = line.strip()
            if line == "":
                continue
            line_split = shlex.split(line, " ")
            
            if line_split[0] == "NETWORK":
                if len(line_split) != 2:
                    logger.error("Invalid NETWORK line: '{}'".format(line))
                    return False
                self.name = line_split[1]
            elif line_split[0] == "RANGE":
                if len(line_split) != 2:
                    logger.error("Invalid RANGE line: '{}'".format(line))
                    return False
                if not re.match(r"[0-9]{1,3}\.[0-9a-z]{1,3}\.[0-9a-z]{1,3}\.[0-9a-z]{1,3}/[0-9]{1,2}", line_split[1]):
                    logger.error("Invalid RANGE line: '{}'".format(line))
                    return False
                self.range = line_split[1]
            elif line_split[0] == "DOMAIN":
                if len(line_split) != 4:
                    logger.error("Invalid DOMAIN line: '{}'".format(line))
                    return False
                self._domain = (line_split[1], line_split[2], line_split[3])
            elif line_split[0] == "VAR":
                if len(line_split) != 3:
                    logger.error("Invalid VAR line: '{}'".format(line))
                    return False
                
                self.vars[line_split[1].lower()] = line_split[2]
            elif line_split[0] == "HOST":
                if len(line_split) != 4:
                    logger.error("Invalid HOST line: '{}'".format(line))
                    return False

                hostname = line_split[1]
                mod_name = line_split[2]
                ip_addr = line_split[3]

                for host in self._hosts:
                    if host.hostname == hostname:
                        logger.error("Host '{}' is already set in definition:".format(hostname))
                        return False

                if ip_addr.lower() == "dhcp":
                    self._dhcp_seen = True

                mod_obj = self.mm.get_module(mod_name)
                mod_role = mod_obj.__ROLE__
                # print(mod_role)

                if mod_role not in self._seen_roles:
                    self._seen_roles.append(mod_role)

                host = Host(hostname, mod_name, ip_addr, mod_role)

                self._hosts.append(host)
                

        return self._after_check()

    def _after_check(self):
        if self._dhcp_seen and 'dhcp' not in self._seen_roles:
            logger.error("DHCP set for an address, but no 'dhcp' role module loaded")
            return False
        
        if self._domain is not None and 'domain' not in self._seen_roles:
            logger.error("DOMAIN entry seen, but no 'domain' role module loaded")
            return False

        return True

    def _check_for_octet(self, addr_str, octet_var, octet_val):
        if ".{}.".format(octet_var) in addr_str:
            return addr_str.replace(".{}.".format(octet_var), ".{}.".format(octet_val))
        else:
            return addr_str

    def create_instance(self, instance_data):
        lines = instance_data.split("\n")
        
        inst_vars = {}
        inst_name = None
        inst_switch = None
        inst_prefix = ""
        inst_range = self.range
        octets = {}

        for line in lines:
            line = line.strip()
            if line == "":
                continue
            line_split = shlex.split(line, " ")
            if line_split[0] == "NETINSTANCE":
                if len(line_split) != 2:
                    logger.error("Invalid NETINSTANCE line: '{}'".format(line))
                    return None
                inst_name = line_split[1]
            elif line_split[0] == "SWITCH":
                if len(line_split) != 2:
                    logger.error("Invalid SWITCH line: '{}'".format(line))
                    return None
                inst_switch = line_split[1]
            elif line_split[0] == "VAR":
                if len(line_split) != 3:
                    logger.error("Invalid VAR line: '{}'".format(line))
                    return None
                inst_vars[line_split[1].lower()] = line_split[2]
            elif line_split[0] == "PREFIX":
                if len(line_split) != 2:
                    logger.error("Invalid PREFIX line: '{}'".format(line))
                    return None
                inst_prefix = line_split[1]
            elif line_split[0] == "OCTET":
                if len(line_split) != 3:
                    logger.error("Invalid OCTET line: '{}'".format(line))
                    return None
                octet_var = line_split[1]
                octet_val = line_split[2]
                octets[octet_var] = octet_val
                inst_range = self._check_for_octet(inst_range, octet_var, octet_val)

        if inst_name is None:
            logger.error("Instance does not have a name".format(line))
            return None
        if inst_switch is None:
            logger.error("Instance does not have a switch".format(line))
            return None
        netinst = NetworkInstance(self.name, inst_switch, inst_range, prefix=inst_prefix)

        # Add hosts to the network instance
        for host in self._hosts:
            for octet in octets:
                host.ip_addr = self._check_for_octet(host.ip_addr, octet, octets[octet])
            netinst.add_host(host)

        netinst.set_var("network_gateway", str(list(netinst.ip_range.hosts())[0]))
        netinst.set_var("network_netmask", str(netinst.ip_range.netmask))
        netinst.set_var("network_prefix", str(netinst.ip_range.prefixlen))

        if "domain" in self._seen_roles:
            for host in self._hosts:
                if host.role == "domain":
                    netinst.set_var("network_dns_server", host.ip_addr)

        if self._domain is not None:
            netinst.set_var("domain_long", self._domain[0])
            netinst.set_var("domain_short", self._domain[0].split(".")[0])
            netinst.set_var("domain_admin_password", self._domain[2])
            netinst.set_var("domain_admin_username", self._domain[1])

        for def_var in self.vars:
            netinst.set_var(def_var, self.vars[def_var])

        for inst_var in inst_vars:
            netinst.set_var(inst_var, inst_vars[inst_var])

        is_ok = netinst.var_check()
        if not is_ok:
            return None

        return netinst
        
