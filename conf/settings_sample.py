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

# Map size (in inches)
MAP_SIZE = (10, 10)

# Map output dot density
MAP_OUT_DPI = 100

# Window size (in pixels) for workflow scheme interface
SCENE_SIZE = (2400, 1000)

# Number of color levels to plot
NB_COLOR_LEVELS = 512

# Color style
## See https://matplotlib.org/examples/color/colormaps_reference.html to preview color rendering
DEFAULT_COLOR_STYLE = 'jet'
COLOR_SYLES = ['ocean', 'gist_earth', 'terrain', 'gist_stern', 'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix',
               'brg', 'hsv', 'gist_rainbow', 'rainbow', 'jet', 'nipy_spectral', 'gits_ncar',  # Miscellaneous colormaps
               'viridis', 'plasma', 'inferno', 'magma',  # Perceptually Uniform Sequential colormaps
               'Spectral', 'coolwarn', 'seismic',  # Diverging colormaps
               'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',  # Sequential colormaps
               'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu', 'GnBu', 'PuBu',
               'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']

# Default axis label for coordinates
X_AXIS_LABEL, Y_AXIS_LABEL = 'X (m)', 'Y (m)'
