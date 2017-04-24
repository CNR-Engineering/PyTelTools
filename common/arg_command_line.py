"""
Custom argparse with a custom formatter_class and optional arguments
"""

import logging
import argparse
import sys


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


class myargparse(argparse.ArgumentParser):
    """
    force and verbose are optional arguments
    """
    def __init__(self, add_args=[], *args, **kwargs):
        kwargs['formatter_class'] = CustomFormatter
        super(myargparse, self).__init__(*args, **kwargs)

        for arg in add_args:
            if arg == 'force':
                self.add_argument('--force', '-f', help='force output overwrite', action='store_true')
            elif arg == 'verbose':
                self.add_argument('--verbose', '-v', help='increase output verbosity', action='count', default=0)
            else:
                sys.exit("Unknown argument: '{}'".format(arg))
