
class Interface():

    def __init__(self, network_name, offset=None, ip_addr=None):
        self._offset = offset
        self.ip_addr = ip_addr
        self.mac = None
        self.network_name = network_name

    def has_offset(self):
        return self._offset is not None

    def set_offset_addr(self, network_addr):
        self.ip_addr = list(network_addr.hosts())[int(self._offset)]

    def __str__(self):
        if self.mac is not None:
            return "{}[{}]".format(self.ip_addr, self.mac)
        else:
            return "{}".format(self.ip_addr)

class Host():

    def __init__(self, hostname, network_name, module_name, in_ip_addr, role):
        self.hostname = hostname 
        self.module_name = module_name
        self.role = role
        self.network_name = network_name
        self.vmid = None
        # IP Ansible will use to connect to the host, not always the host's final IP
        self.connect_ip = None
            
        self.interfaces = [] 
        if in_ip_addr is not None:
            self.interfaces.append(Interface(self.network_name, ip_addr=in_ip_addr))

        self.vars = {}

    @property
    def interface(self):
        if len(self.interfaces) >= 1:
            return self.interfaces[0]
        else:
            return None

    @property
    def ip_addr(self):
        if len(self.interfaces) >= 1:
            return self.interfaces[0].ip_addr
        else:
            return None

    @ip_addr.setter
    def ip_addr(self, set_addr):
        if len(self.interfaces) >= 1:
            self.interfaces[0].ip_addr = set_addr

    @property
    def mac(self):
        if len(self.interfaces) >= 1:
            return self.interfaces[0].mac
        else:
            return None

    @mac.setter
    def mac(self, set_mac):
        if len(self.interfaces) >= 1:
            self.interfaces[0].mac = set_mac

class Router(Host):
    def __init__(self, hostname, module_name):
        super().__init__(hostname, None, module_name, None, 'router')
        

    def add_interface(self, network_name, ip_addr=None, offset=None):
        self.interfaces.append(Interface(network_name, ip_addr=ip_addr, offset=offset))

