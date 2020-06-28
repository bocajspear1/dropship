import requests
import os

from dropship.lib.base_module import BaseModule

class WindowsRSAT(BaseModule):
    __NAME__ = "windows_RSAT"
    __DESC__ = "Sets up RSAT tools for remote management of the AD"
    __IMAGE__ = "client.windows.windows10_1909"
    __VARS__ = []
    __ROLE__ = "post"
    __METHOD__ = "winrm"
    __OSTYPE__ = "windows"
    __POST_FILES__ = ["rsat.msu"]
    __BECOME_METHOD__ = "runas"
    __BECOME_USER__ = "adminuser"

    def before_post(self, builder):
        url = 'https://download.microsoft.com/download/1/D/8/1D8B5022-5477-4B9A-8104-6A71FF9D98AB/WindowsTH-RSAT_WS_1803-x64.msu'
        r = requests.get(url, allow_redirects=True)
        if not os.path.exists(self.get_dir() + "/files"):
            os.mkdir(self.get_dir() + "/files")
        open(self.get_dir() + "/files/rsat.msu", 'wb').write(r.content)



__MODULE__ = WindowsRSAT