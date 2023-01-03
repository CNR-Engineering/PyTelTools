from collections import OrderedDict
import logging
from multiprocessing import cpu_count


# ~> GENERAL CONFIGURATION

# Logging level
# logging.DEBUG, logging.INFO, logging.ERROR
LOGGING_LEVEL = logging.INFO

# Logging formats
LOGGING_FMT_CLI = '%(message)s'
LOGGING_FMT_GUI = '%(asctime)s - [%(levelname)s] - \n%(message)s'

# Color logging messages (requires coloredlogs package)"
COLOR_LOGS = True

# CPU Cores for parallel computation (workflow multi-folder view)
NCSIZE = cpu_count()

# Path to ArGIS Python executable (for `outil_carto.py`)
PY_ARCGIS = 'C:\\Python27\\ArcGIS10.8\\python.exe'

# ~> SERAFIN

# Use to define mesh origin coordinates (in iparam array)
ENABLE_MESH_ORIGIN = True

# Serafin extensions for file name filtering (default extension is the first)
SERAFIN_EXT = ['.srf', '.slf', '.res', '.geo']

# Language (for variables detection)
LANG = 'fr'

# ~> INPUTS/OUTPUTS

# Format to write float values (in CSV, LandXML, VTK)
FMT_FLOAT = '{:.5e}'  # 1.53849e5 (6 significant numbers)

# Format to write x, y (and z) coordinates (in CSV, LandXML, VTK)
FMT_COORD = '{:.4f}'  # 153849.2841

# Representation of a "Not A Number" value (to write in CSV files)
NAN_STR = '#N/A'

# CSV column delimiter
CSV_SEPARATOR = ';'

# Write XYZ header
WRITE_XYZ_HEADER = True

# Arcpy png resolution
ARCPY_PNG_DPI = 192

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
## Discrete color map (loop over the list if more are required)
DEFAULT_COLORS = OrderedDict([('Blue', '#1f77b4'), ('Orange', '#ff7f0e'), ('Green', '#2ca02c'), ('Red', '#d62728'),
                              ('Purple', '#9467bd'), ('Brown', '#8c564b'), ('Pink', '#e377c2'), ('DarkGray', '#7f7f7f'),
                              ('Yellow', '#bcbd22'), ('Cyan', '#17becf')])

## Continous color map
## See https://matplotlib.org/examples/color/colormaps_reference.html to preview color rendering
DEFAULT_COLOR_STYLE = 'coolwarm'
COLOR_SYLES = ['ocean', 'gist_earth', 'terrain', 'gnuplot', 'gnuplot2', 'CMRmap',
               'gist_rainbow', 'rainbow', 'jet',   # Miscellaneous colormaps
               'viridis', 'plasma', 'inferno', 'magma',  # Perceptually Uniform Sequential colormaps
               'Spectral', 'coolwarm', 'seismic',  # Diverging colormaps
               'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',  # Sequential colormaps
               'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu', 'GnBu', 'PuBu',
               'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']

# Default axis label for coordinates
X_AXIS_LABEL, Y_AXIS_LABEL = 'X (m)', 'Y (m)'
X_AXIS_LABEL_DISTANCE = 'Distance (m)'
Y_AXIS_LABEL_CROSS_SECTION = ''  # If empty then it is automatically computed from input Serafin language
TITLE_CROSS_SECTION = ''

# Number of bins for EWSD distribution (for GUI `Compare Resultats`)
NB_BINS_EWSD = 100
