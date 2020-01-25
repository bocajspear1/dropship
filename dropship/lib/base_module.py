import sys
import os
class BaseModule():

    __NAME__ = ""
    __DESC__ = ""

    def get_dir(self):
        return os.path.dirname(sys.modules[self.__class__.__module__].__file__)
