from dropship.lib.base_module import BaseModule

class UbuntuDC(BaseModule):
    __NAME__ = "ubuntu_dc_20_04"
    __DESC__ = "Ubuntu DC Sample 4.11+"
    __IMAGE__ = "server.linux.ubuntu_2004"
    __VARS__ = [""]
    __ROLE__ = "domain"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = ['netplan.yml']
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"


__MODULE__ = UbuntuDC