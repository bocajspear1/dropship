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

    def get_shutdown_path(self, out_dir):
        return self.get_module_path(out_dir) + "/shutdown.yml"

    def get_deploy_path(self, out_dir):
        return self.get_module_path(out_dir) + "/deploy.yml"

    def get_dhcp_path(self, out_dir):
        return self.get_module_path(out_dir) + "/dhcp.yml"

    def get_post_path(self, out_dir):
        return self.get_module_path(out_dir) + "/post.yml"

    def prepare_bootstrap(self, out_dir):

        module_dir = self.get_module_path(out_dir)
        if not os.path.exists(module_dir):
            os.mkdir(module_dir)

        # Get the module's bootstrap.yml file
        mod_bootstrap_src = self.get_dir() + "/bootstrap.yml"
        dest_file = self.get_bootstrap_path(out_dir) 
        # Copy the bootstrap file to our working directory
        if not hasattr(self, '__BOOTSTRAP_FILES__') or len(self.__BOOTSTRAP_FILES__) == 0:
            # If no files, there's no paths to change, so just copy the bootstrap file
            shutil.copyfile(mod_bootstrap_src, dest_file)
        else:
            self._prepare_stage_files(mod_bootstrap_src, dest_file, self.__BOOTSTRAP_FILES__, out_dir)

        self._prepare_shutdown(out_dir)

    def prepare_deploy(self, out_dir):
        module_dir = self.get_module_path(out_dir)
        if not os.path.exists(module_dir):
            os.mkdir(module_dir)
        mod_deploy_src = self.get_dir() + "/deploy.yml"
        dest_file = self.get_deploy_path(out_dir) 

        # Copy the deploy file to our working directory
        if not hasattr(self, '__DEPLOY_FILES__') or len(self.__DEPLOY_FILES__) == 0:
            # If no files, there's no paths to change, so just copy the bootstrap file
            shutil.copyfile(mod_deploy_src, dest_file)
        else:
            self._prepare_stage_files(mod_deploy_src, dest_file, self.__DEPLOY_FILES__, out_dir)

        self._prepare_shutdown(out_dir)

    def prepare_dhcp(self, out_dir):
        module_dir = self.get_module_path(out_dir)
        if not os.path.exists(module_dir):
            os.mkdir(module_dir)
        mod_dhcp_src = self.get_dir() + "/dhcp.yml"
        dest_file = self.get_dhcp_path(out_dir) 

        # Copy the dhcp file to our working directory
        if not hasattr(self, '__DHCPCOLLECT_FILES__') or len(self.__DHCPCOLLECT_FILES__) == 0:
            # If no files, there's no paths to change, so just copy the dhcp file
            shutil.copyfile(mod_dhcp_src, dest_file)
        else:
            self._prepare_stage_files(mod_dhcp_src, dest_file, self.__DHCPCOLLECT_FILES__, out_dir)

    def prepare_post(self, out_dir):
        module_dir = self.get_module_path(out_dir)
        if not os.path.exists(module_dir):
            os.mkdir(module_dir)
        mod_post_src = self.get_dir() + "/post.yml"
        dest_file = self.get_post_path(out_dir) 

        # Copy the dhcp file to our working directory
        if not hasattr(self, '__POST_FILES__') or len(self.__POST_FILES__) == 0:
            # If no files, there's no paths to change, so just copy the dhcp file
            shutil.copyfile(mod_post_src, dest_file)
        else:
            self._prepare_stage_files(mod_post_src, dest_file, self.__POST_FILES__, out_dir)

    def _prepare_shutdown(self, out_dir):
        # Get the module's shutdown.yml file
        mod_shutdown_src = self.get_dir() + "/shutdown.yml"
        mod_shutdown_dst = self.get_shutdown_path(out_dir)
        # Copy the shutdown file to our working directory
        shutil.copyfile(mod_shutdown_src, mod_shutdown_dst)

    def _prepare_stage_files(self, src_file, dest_file, files, out_dir):
        files_dir = self.get_module_path(out_dir) + "/files"

        if not os.path.exists(files_dir):
            os.mkdir(files_dir)

        for item in files:
            shutil.copyfile(self.get_dir() + "/files/" + item, files_dir + "/" + item)

        bs_file = open(src_file, "r")
        bs_file_data = bs_file.read()
        bs_file.close()

        bs_file_data = bs_file_data.replace("+FILES+", os.path.abspath(files_dir))

        out_bs_file = open(dest_file, "w+")
        out_bs_file.write(bs_file_data)
        out_bs_file.close()