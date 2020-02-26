from dropship.lib.base_module import BaseModule

class VyosRouter(BaseModule):
    __NAME__ = "vyos_router"
    __DESC__ = "VyOS Router"
    __IMAGE__ = "linux.vyos"
    __VARS__ = [""]
    __PROVIDES__ = "router"
    __METHOD__ = "network_cli"
    __OSTYPE__ = "vyos"


__MODULE__ = VyosRouter