import logging

from pyteltools.conf.settings import LOGGING_LEVEL


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(LOGGING_LEVEL)
