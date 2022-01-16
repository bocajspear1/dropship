from dropship.lib.base_module import BaseModule

class CentOS7(BaseModule):
    __NAME__ = "centos7"
    __DESC__ = "CentOS 7 GUI-less Client"
    __IMAGE__ = "client.linux.centos7"
    __VARS__ = [""]
    __ROLE__ = "client"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = []
    __DEPLOY_FILES__ = []
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"

__MODULE__ = CentOS7