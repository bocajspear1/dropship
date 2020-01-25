from dropship.lib.base_module import BaseModule

class SambaDC(BaseModule):
    __NAME__ = "samba_dc"
    __DESC__ = "A Samba-based DC"
    __IMAGE__ = "ubuntu1804_server"


__MODULE__ = SambaDC