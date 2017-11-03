#!/usr/bin/python3
"""
Write a markdown documentation file for command line scripts.

/!\ Should be run from PyTelTools repository root folder (same level as Makefile).
"""

import importlib
import os.path
from glob import glob


class CommandLineScript:
    def __init__(self, path):
        self.path = path
        basename = os.path.basename(self.path)
        self.name = os.path.splitext(basename)[0]

    def help_msg(self):
        """Returns help message with description and usage"""
        mod = importlib.import_module(self.name)
        return getattr(mod, 'parser').format_help()


# Build sorted list of CLI scripts
cli_scripts = []
for file in sorted(glob('*.py')):
    if not file.endswith('__init__.py'):
        cli_scripts.append(CommandLineScript(file))


# Write a markdown file (to be integrated within github wiki)
with open(os.path.join('..', 'doc', 'cli_usage.md'), 'w') as fileout:
    # Write TOC
    for script in cli_scripts:
        fileout.write('* [%s](#%s)\n' % (script.name, script.name))
    fileout.write('\n')

    # Write help message for each script
    for script in cli_scripts:
        print(script.name)
        fileout.write('# %s\n' % script.name)
        fileout.write('```\n')
        fileout.write(script.help_msg())
        fileout.write('```\n')
        fileout.write('\n')
