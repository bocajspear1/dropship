import shlex 
import logging
import re

from dropship.lib.helpers import ModuleManager
from dropship.lib.netinst import NetworkInstance
from dropship.lib.host import Host, Router
from dropship.lib.user import User
from dropship.lib.postmod import PostModule

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
        self._users = []
        self._postmods = []

        if module_path is None:
            self.mm = ModuleManager("./out")
        else:
            self.mm = ModuleManager("./out", module_path=module_path)

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
            elif line_split[0] == "USER":
                if len(line_split) != 5:
                    logger.error("Invalid USER line: '{}'".format(line))
                    return False
                self._users.append((line_split[1], line_split[2], line_split[3], line_split[4]))
            elif line_split[0] == "VAR":
                if len(line_split) != 3:
                    logger.error("Invalid VAR line: '{}'".format(line))
                    return False
                
                self.vars[line_split[1].lower()] = line_split[2]
            elif line_split[0] == "POSTMOD":
                if len(line_split) < 3:
                    logger.error("Invalid POSTMOD line: '{}'".format(line))
                    return False
                
                
                hostname = line_split[1]
                mod_name = line_split[2]
                mod_vars = line_split[3:]

                self._postmods.append((hostname, mod_name, mod_vars))
                
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

                host = Host(hostname, self.name, mod_name, ip_addr, mod_role)

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
        inst_of = None
        inst_switch = None
        inst_prefix = ""
        inst_range = self.range
        octets = {}
        routers = []

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
            if line_split[0] == "INSTOF":
                if len(line_split) != 2:
                    logger.error("Invalid INSTOF line: '{}'".format(line))
                    return None
                inst_of = line_split[1]
            if line_split[0] == "ROUTER":
                if len(line_split) < 3:
                    logger.error("Invalid ROUTER line: '{}'".format(line))
                    return None
                router_name = line_split[1]
                router_module = line_split[2]
                router_interfaces = line_split[3:]

                mod_obj = self.mm.get_module(router_module)
                if mod_obj.__ROLE__ != "router":
                    logger.error("Module '{}' is not role 'router'".format(router_module))
                    return None

                router = Router(router_name, router_module)
                for iface in router_interfaces:
                    if "=" not in iface:
                        logger.error("Invalid ROUTER line: '{}', invalid interface definition".format(line))
                        return None
                    iface_split = iface.split("=")
                    if iface_split[1].isnumeric():
                        router.add_interface(iface_split[0], offset=iface_split[1])
                    else:
                        router.add_interface(iface_split[0], ip_addr=iface_split[1])


                routers.append(router)
            elif line_split[0] == "SWITCH":
                if len(line_split) != 2:
                    logger.error("Invalid SWITCH line: '{}'".format(line))
                    return None
                inst_switch = line_split[1]
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
        if inst_of is None:
            logger.error("Instance does not have a network its defining".format(line))
            return None
        if inst_switch is None:
            logger.error("Instance does not have a switch".format(line))
            return None
        netinst = NetworkInstance(inst_name, self.name, inst_switch, inst_range, prefix=inst_prefix)

        # Add routers to the network instance
        for router in routers:
            netinst.add_host(router)

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
                    netinst.set_var("network_domain_controller", host.ip_addr)

        if self._domain is not None:
            netinst.set_var("domain_long", self._domain[0])
            netinst.set_var("domain_short", self._domain[0].split(".")[0])
            netinst.set_var("domain_admin_password", self._domain[2])
            netinst.set_var("domain_admin_username", self._domain[1])

        for def_var in self.vars:
            for octet in octets:
                self.vars[def_var] = self._check_for_octet(self.vars[def_var], octet, octets[octet])
            netinst.set_var(def_var, self.vars[def_var])

        for inst_var in inst_vars:
            netinst.set_var(inst_var, inst_vars[inst_var])

        for user_data in self._users:
            user_obj = User(user_data[0], user_data[1], user_data[2], user_data[3])
            netinst.add_user(user_obj)

        for postmod in self._postmods:
            
            hostname = postmod[0]
            mod_name = postmod[1]
            mod_vars = postmod[2]

            print(hostname, mod_name)

            mod_obj = self.mm.get_module(mod_name)
            if mod_obj.__ROLE__ != "post":
                logger.error("Module '{}' is not role 'post'".format(mod_name))
                return None

            postmod_inst = PostModule(hostname, mod_name)

            for var_group in mod_vars:
                if "=" not in iface:
                    logger.error("Invalid POSTMOD line: '{}', invalid variable definition".format(line))
                    return None
                var_split = var_group.split("=")
                var_name = var_split[0]
                var_val = var_split[1]
                for octet in octets:
                    var_val = self._check_for_octet(var_val, octet, octets[octet])
                print(var_name, var_val)
                postmod_inst.vars[var_name] = var_val

            for check_var in mod_obj.__VARS__:
                if check_var not in postmod_inst.vars:
                    logger.error("Variable '{}' not set for module {}".format(check_var, mod_name))
                    return None

            netinst.add_postmod(postmod_inst)

        is_ok = netinst.var_check()
        if not is_ok:
            return None

        return netinst
        
