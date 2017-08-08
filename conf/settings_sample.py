import logging


# ~> GENERAL CONFIGURATION

# Logging level
# logging.DEBUG, logging.INFO, logging.ERROR
LOGGING_LEVEL = logging.INFO

# ~> SERAFIN

# Serafin extensions for file name filtering (default extension is the first)
SERAFIN_EXT = ['.srf', '.slf', '.res', '.geo']

# Langage (for variables detection)
LANG = 'fr'

# ~> INPUTS/OUTPUTS

# Number of digits to write for csv
DIGITS = 4

# CSV column delimiter
CSV_SEPARATOR = ';'

# ~> VISUALIZATION

# Figure size (in inches)
FIG_SIZE = (8, 6)

# Figure output dot density
FIG_OUT_DPI = 100

# Window size (in pixels) for workflow scheme interface
SCENE_SIZE = (2400, 1000)

# Number of color levels to plot
NB_COLOR_LEVELS = 512

# Color style
DEFAULT_COLOR_STYLE = 'viridis'
COLOR_SYLES = ['viridis', 'plasma', 'inferno', 'magma', 'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
               'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu', 'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']
