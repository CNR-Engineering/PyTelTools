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
