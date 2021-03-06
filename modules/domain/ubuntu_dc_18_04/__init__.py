from dropship.lib.base_module import BaseModule

class UbuntuDC(BaseModule):
    __NAME__ = "ubuntu_dc"
    __DESC__ = "Ubuntu DC"
    __IMAGE__ = "server.linux.ubuntu_1804"
    __VARS__ = [""]
    __ROLE__ = "domain"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = ['netplan.yml']
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"


__MODULE__ = UbuntuDC