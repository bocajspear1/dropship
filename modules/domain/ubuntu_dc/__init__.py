from dropship.lib.base_module import BaseModule

class UbuntuDC(BaseModule):
    __NAME__ = "ubuntu_dc"
    __DESC__ = "Ubuntu DC"
    __IMAGE__ = "linux.ubuntu_1804_server"
    __VARS__ = [""]
    __PROVIDES__ = "domain"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_TEMPLATES__ = ['netplan.yml']


__MODULE__ = UbuntuDC