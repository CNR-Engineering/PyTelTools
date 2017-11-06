import logging

from pyteltools.conf import settings


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(settings.LOGGING_LEVEL)
