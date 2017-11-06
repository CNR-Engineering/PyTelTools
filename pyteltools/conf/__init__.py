import os
from simple_settings import LazySettings
import sys


# Add default configuration
settings_list = ['pyteltools.conf.default_settings']

# Add user configuration if `PYTELTOOLS_SETTINGS` environment variable is present and not empty
settings_env = os.environ.get('PYTELTOOLS_SETTINGS')
if settings_env is not None:
    if settings_env:
        settings_list.append(settings_env)

try:
    settings = LazySettings(*settings_list)
    settings.as_dict()  # Only check if settings could be read
except FileNotFoundError:
    sys.stderr.write('User configuration file could not be found\n')
    sys.stderr.write('File "%s" does not exist (or check `PYTELTOOLS_SETTINGS` environment file)\n' % settings_env)
    sys.exit(1)
