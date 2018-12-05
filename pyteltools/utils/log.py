import coloredlogs
import logging

from pyteltools.conf import settings


# Overwrite some default styles
has_bold = coloredlogs.CAN_USE_BOLD_FONT
LEVEL_STYLES = coloredlogs.DEFAULT_LEVEL_STYLES
FIELD_STYLES = coloredlogs.DEFAULT_FIELD_STYLES
FIELD_STYLES['levelname'] = {'color': 'white', 'bold': has_bold}  # Avoid 'black' color for Windows


# Create a logger object
def new_logger(name):
    """!
    Get a new logger
    @param name <str>: logger name
    """
    logger = logging.getLogger(name)
    if settings.COLOR_LOGS:
        coloredlogs.install(logger=logger, level=settings.LOGGING_LEVEL, fmt=settings.LOGGING_FMT_CLI,
                            level_styles=LEVEL_STYLES, field_styles=FIELD_STYLES)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(settings.LOGGING_FMT_CLI))
        logger.addHandler(handler)
        logger.setLevel(settings.LOGGING_LEVEL)
    return logger


def set_logger_level(level):
    """
    Overwrite level of all loggers of PyTelTools (only `outil_carto` is ignored)
    Useful for external calling without having to modify settings
    """
    from pyteltools.geom.util import logger as geom_logger
    geom_logger.setLevel(level)
    from pyteltools.slf.util import logger as slf_logger
    slf_logger.setLevel(level)
    from pyteltools.utils.cli_base import logger as cli_logger
    cli_logger.setLevel(level)
    from pyteltools.workflow.util import logger as wk_logger
    wk_logger.setLevel(level)
