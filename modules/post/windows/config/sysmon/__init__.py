import requests
import os

from dropship.lib.base_module import BaseModule

class WindowsRSAT(BaseModule):
    __NAME__ = "windows_sysmon"
    __DESC__ = "Sets up system"
    __IMAGE__ = "client.windows.windows10_1909"
    __VARS__ = []
    __ROLE__ = "post"
    __METHOD__ = "winrm"
    __OSTYPE__ = "windows"
    __POST_FILES__ = ["Sysmon.zip", "sysmonconfig.xml"]
    __BECOME_METHOD__ = "runas"
    __BECOME_USER__ = "adminuser"

    def before_post(self, builder):
        if not os.path.exists(self.get_dir() + "/files"):
            os.mkdir(self.get_dir() + "/files")

        url = 'https://download.sysinternals.com/files/Sysmon.zip'
        r = requests.get(url, allow_redirects=True)
        open(self.get_dir() + "/files/Sysmon.zip", 'wb').write(r.content)

        config_url = 'https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml'
        r = requests.get(config_url, allow_redirects=True)
        open(self.get_dir() + "/files/sysmonconfig.xml", 'wb').write(r.content)



__MODULE__ = WindowsRSAT