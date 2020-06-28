from dropship.lib.base_module import BaseModule

class WindowsLocalAdmin(BaseModule):
    __NAME__ = "windows_localadmin"
    __DESC__ = "Sets user specified to be a local administrator"
    __IMAGE__ = "client.windows.windows10_1909"
    __VARS__ = ["username"]
    __ROLE__ = "post"
    __METHOD__ = "winrm"
    __OSTYPE__ = "windows"
    __POST_FILES__ = []
    __BECOME_METHOD__ = "runas"
    __BECOME_USER__ = "adminuser"


__MODULE__ = WindowsLocalAdmin