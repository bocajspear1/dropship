
class Host():

    def __init__(self, hostname, module_name, ip_addr, role):
        self.hostname = hostname 
        self.module_name = module_name
        self.role = role
        self.ip_addr = ip_addr 
        self.vars = {}
