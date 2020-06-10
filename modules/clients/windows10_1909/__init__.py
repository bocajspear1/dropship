from dropship.lib.base_module import BaseModule

class Windows1909Client(BaseModule):
    __NAME__ = "windows10_1909"
    __DESC__ = "Windows 10 1909"
    __IMAGE__ = "client.windows.windows10_1909"
    __VARS__ = [""]
    __ROLE__ = "client"
    __METHOD__ = "winrm"
    __OSTYPE__ = "windows"
    __BOOTSTRAP_FILES__ = []
    __BECOME_METHOD__ = "runas"
    __BECOME_USER__ = "adminuser"


__MODULE__ = Windows1909Client