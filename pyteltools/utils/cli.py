"""
Prepare module logger

Handles some exceptions (if `in_slf` or `out_slf` arguments are present)
"""

import argparse
import logging
import sys

from pyteltools.conf import settings
from pyteltools.slf.Serafin import logger as slf_logger


LINE_WIDTH = 80

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(settings.LOGGING_LEVEL)


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


class PyTelToolsArgParse(argparse.ArgumentParser):
    """
    Derived ArgumentParser with improved help message rendering
    """
    def __init__(self, add_args=[], description=None, *args, **kwargs):
        kwargs['formatter_class'] = CustomFormatter
        new_description = '_' * LINE_WIDTH + '\n' + description + '_' * LINE_WIDTH + '\n'
        super().__init__(add_help=False, description=new_description, *args, **kwargs)
        self._positionals.title = self._title_group('Positional and compulsory arguments')
        self._optionals.title = self._title_group('Optional arguments')
        self.group_general = None

        if 'in_slf' in add_args:
            self.add_argument('in_slf', help='Serafin input filename')
        if 'out_slf' in add_args:
            self.add_argument('out_slf', help='Serafin output filename')
            self.add_argument('--to_single_precision', help='force Serafin output to be single precision',
                              action='store_true')
            self.add_argument('--toggle_endianness', help='toggle output file endianness (between big/little endian)',
                              action='store_true')
        if any(arg in add_args for arg in ('in_slf', 'out_slf')):
            self.add_argument('--lang', help='Serafin language for variables detection (`fr` or `en`)',
                              default=settings.LANG)
        if 'shift' in add_args:
            self.add_argument('--shift', type=float, nargs=2, help='translation (x_distance, y_distance)',
                              metavar=('X', 'Y'))

    @staticmethod
    def _title_group(label):
        """Decorates group title label"""
        return '~> '+ label

    def add_argument_group(self, name, *args, **kwargs):
        """Add title group decoration"""
        return super().add_argument_group(self._title_group(name), *args, **kwargs)

    def add_group_general(self, add_args=[]):
        """Add group for optional general arguments (commonly used in PyTelTools)"""
        self.group_general = self.add_argument_group('General optional arguments')
        if 'force' in add_args:
            self.group_general.add_argument('-f' '--force', help='force output overwrite', action='store_true')
        if 'verbose' in add_args:
            self.group_general.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
        self.group_general.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                                        help='show this help message and exit')

    def parse_args(self, *args, **kwargs):
        new_args = super().parse_args(*args, **kwargs)

        if self.group_general is None:
            self.add_group_general()  # add only help message

        # Set module logger verbosity
        if 'verbose' in new_args:
            if new_args.verbose:
                logger.setLevel(logging.DEBUG)
                slf_logger.setLevel(logging.DEBUG)

        # Input Serafin file
        if 'in_slf' in new_args:
            try:
                with open(new_args.in_slf):
                    pass
            except FileNotFoundError:
                logger.error('No such file or directory: %s' % new_args.in_slf)
                sys.exit(1)

        if any(arg in new_args for arg in ('in_slf', 'out_slf')):
            if 'slf_lang' not in new_args:
                new_args.in_lang = settings.LANG

        return new_args
