import sys
import os
import shutil

class BaseModule():

    __NAME__ = ""
    __DESC__ = ""
    __IMAGE__ = ""

    @property
    def __IMAGE_NORMALIZED__(self):
        return self.__IMAGE__.replace(".", "_")

    @property
    def __NAME_NORMALIZED__(self):
        return self.__NAME__.replace(".", "_")

    def get_dir(self):
        return os.path.dirname(sys.modules[self.__class__.__module__].__file__)

    def get_module_path(self, out_dir):
        return out_dir + "/mod_" + self.__NAME_NORMALIZED__

    def get_bootstrap_path(self, out_dir):
        return self.get_module_path(out_dir) + "/bootstrap.yml"

    def get_reboot_path(self, out_dir):
        return self.get_module_path(out_dir) + "/reboot.yml"

    def get_deploy_path(self, out_dir):
        return self.get_module_path(out_dir) + "/deploy.yml"

    def prepare_bootstrap(self, out_dir):

        module_dir = self.get_module_path(out_dir)
        if not os.path.exists(module_dir):
            os.mkdir(module_dir)

        # Get the module's bootstrap.yml file
        mod_bootstrap_src = self.get_dir() + "/bootstrap.yml"
        dest_file = self.get_bootstrap_path(out_dir) 
        # Copy the bootstrap file to our working directory
        shutil.copyfile(mod_bootstrap_src, dest_file)

        self._prepare_reboot(out_dir)

    def _prepare_reboot(self, out_dir):
        # Get the module's reboot.yml file
        mod_reboot_src = self.get_dir() + "/reboot.yml"
        mod_reboot_dst = self.get_reboot_path(out_dir)
        # Copy the reboot file to our working directory
        shutil.copyfile(mod_reboot_src, mod_reboot_dst)
