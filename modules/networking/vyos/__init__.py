from dropship.lib.base_module import BaseModule

class VyosRouter(BaseModule):
    __NAME__ = "vyos_router"
    __DESC__ = "VyOS Router"
    __IMAGE__ = "vyos"
    __VARS__ = [""]


__MODULE__ = VyosRouter