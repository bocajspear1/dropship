

import logging
import coloredlogs

logger = logging.getLogger('dropship')
coloredlogs.install(level='DEBUG', logger=logger)

from dropship.lib.dropship import Dropship