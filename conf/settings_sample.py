import logging

# Serafin extensions for file name filtering (default extension is the first)
SERAFIN_EXT = ['.srf', '.slf', '.res', '.geo']

# Langage (for variables detection)
LANG = 'fr'

# Number of digits to write for csv
DIGITS = 4

# CSV column delimiter
CSV_SEPARATOR = ';'

# Window size for workflow interface
SCENE_WIDTH, SCENE_HEIGHT = (2400, 1000)

# Logging level
# logging.DEBUG, logging.INFO, logging.ERROR
LOGGING_LEVEL = logging.INFO


# Number of color levels to plot
NB_COLOR_LEVELS = 512

# Color style
DEFAULT_COLOR_STYLE = 'viridis'
COLOR_SYLES = ['viridis', 'plasma', 'inferno', 'magma', 'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
               'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu', 'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']
