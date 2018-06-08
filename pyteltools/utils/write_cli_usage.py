"""
Write a markdown documentation file for command line scripts.

Beware: Should be run from pyteltools repository root folder (same level as Makefile).
"""

import importlib
from glob import glob
import os.path
import sys


sys.path.append(sys.argv[1])  # dirty method to import modules easily


class CommandLineScript:
    def __init__(self, path):
        self.path = path
        basename = os.path.basename(self.path)
        self.name = os.path.splitext(basename)[0]

    def help_msg(self):
        """Returns help message with description and usage"""
        mod = importlib.import_module('%s' % self.name)
        return getattr(mod, 'parser').format_help()


# Build sorted list of CLI scripts
cli_scripts = []
for file in sorted(glob(os.path.join(sys.argv[1], '*.py'))):
    if not file.endswith('__init__.py'):
        cli_scripts.append(CommandLineScript(file))


# Write a markdown file (to be integrated within github wiki)
with open(sys.argv[2], 'w') as fileout:
    # Write TOC
    fileout.write('Available **command line** scripts are:\n')
    for script in cli_scripts:
        fileout.write('* [%s.py](#%spy)\n' % (script.name, script.name))
    fileout.write('\n')
    fileout.write('A **help message** is provided for each script with the argument `-h` (e.g. `slf_base.py -h`).\n')
    fileout.write('Help messages are gathered below for each script '
                  '(and this file was in fact automatically generated).\n')
    fileout.write('\n')

    # Write help message for each script
    for script in cli_scripts:
        print(script.name)
        fileout.write('# %s.py\n' % script.name)
        fileout.write('```\n')
        fileout.write(script.help_msg())
        fileout.write('```\n')
        fileout.write('\n')
