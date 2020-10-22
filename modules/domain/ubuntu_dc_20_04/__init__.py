from dropship.lib.base_module import BaseModule

class UbuntuDC2004(BaseModule):
    __NAME__ = "ubuntu_dc_20_04"
    __DESC__ = "Ubuntu DC 20.04"
    __IMAGE__ = "server.linux.ubuntu_2004"
    __VARS__ = [""]
    __ROLE__ = "domain"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = ['netplan.yml']
    __DEPLOY_FILES__ = ['ntp.conf']
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"


__MODULE__ = UbuntuDC2004