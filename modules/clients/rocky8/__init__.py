from dropship.lib.base_module import BaseModule

class Rocky8(BaseModule):
    __NAME__ = "rocky8"
    __DESC__ = "Rocky 8 Client"
    __IMAGE__ = "client.linux.rocky8"
    __VARS__ = [""]
    __ROLE__ = "client"
    __METHOD__ = "ssh"
    __OSTYPE__ = "debian"
    __BOOTSTRAP_FILES__ = []
    __DEPLOY_FILES__ = []
    __BECOME_METHOD__ = "sudo"
    __BECOME_USER__ = "root"

__MODULE__ = Rocky8