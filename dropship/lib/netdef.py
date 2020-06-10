import shlex 
import logging
import re


from dropship.lib.helpers import ModuleManager

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
            print(line_split)
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
            elif line_split[0] == "HOST":
                if len(line_split) != 4:
                    logger.error("Invalid HOST line: '{}'".format(line))
                    return False

                hostname = line_split[1]
                mod_name = line_split[2]
                ip_addr = line_split[3]

                if ip_addr.lower() == "dhcp":
                    self._dhcp_seen = True

                mod_obj = self.mm.get_module(mod_name)
                mod_role = mod_obj.__ROLE__
                print(mod_role)

                if mod_role not in self._seen_roles:
                    self._seen_roles.append(mod_role)
                

        return self._after_check()

    def _after_check(self):
        if self._dhcp_seen and 'dhcp' not in self._seen_roles:
            logger.error("DHCP set for an address, but no 'dhcp' role module loaded")
            return False
        return True
        
