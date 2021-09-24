from dropship.lib.base_module import BaseModule

class Xubuntu2004(BaseModule):
    __NAME__ = "xubuntu_2004"
    __DESC__ = "Xubuntu 20.04 Client"
    __IMAGE__ = "client.linux.xubuntu_2004"
    __VARS__ = [""]
    __ROLE__ = "client"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = []
    __DEPLOY_FILES__ = []
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"

__MODULE__ = Xubuntu2004