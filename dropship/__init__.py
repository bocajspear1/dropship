

import logging
import coloredlogs

logger = logging.getLogger('dropship')
coloredlogs.install(level='DEBUG', logger=logger)
