from dropship.lib.base_module import BaseModule

class UbuntuDHCP(BaseModule):
    __NAME__ = "ubuntu_dhcp"
    __DESC__ = "Ubuntu DHCP server"
    __IMAGE__ = "server.linux.ubuntu_1804"
    __VARS__ = [""]
    __ROLE__ = "dhcp"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = ['netplan.yml']
    __DEPLOY_FILES__ = ['dnsmasq.conf']
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"

__MODULE__ = UbuntuDHCP