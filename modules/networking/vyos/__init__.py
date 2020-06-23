from dropship.lib.base_module import BaseModule

class VyosRouter(BaseModule):
    __NAME__ = "vyos_router"
    __DESC__ = "VyOS Router"
    __IMAGE__ = "networking.linux.vyos"
    __VARS__ = [""]
    __ROLE__ = "router"
    __METHOD__ = "network_cli"
    __OSTYPE__ = "vyos"

    def get_interface_name(self, interface_num):
        return "eth{}".format(interface_num)



__MODULE__ = VyosRouter