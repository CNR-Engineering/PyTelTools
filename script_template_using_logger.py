#!/usr/bin/env python3

"""
An example of script using logger
tested using:
> python script_template_using_logger.py testdata\test.slf
> python script_template_using_logger.py testdata\test.slf -v
> python script_template_using_logger.py testdata\test.slf -vv
> python script_template_using_logger.py testdata\f2d_confluence.slf --lang en
"""

import os
import logging
import logging.config
from common.arg_command_line import myargparse
from slf.Serafin import Read

if not os.path.exists('log'):
    os.makedirs('log')

# define script arguments
parser = myargparse(description=__doc__, add_args=['force', 'verbose'])
parser.add_argument('inname', help='Serafin input filename')
# parser.add_argument('outname', help='Serafin output filename')
parser.add_argument('--lang', type=str, help='Language used in the input file (fr or en)', default='fr')
args = parser.parse_args()

# handle the verbosity/debug option
levels = ['WARNING', 'INFO', 'DEBUG']
loglevel = levels[min(len(levels), args.verbose)]  # capped to number of levels

# apply logging configurations
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: \n%(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'filename': os.path.join(os.path.dirname(__file__), 'log', '%s.log' % __file__[:3])
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
})

# create a logger
logger = logging.getLogger(__name__)

# running the script
logger.error('Start running the script..')

# ==================================================================
# =========== here goes the script =================================

with Read(args.inname, args.lang) as resin:
    resin.read_header()
    resin.get_time()
    print(resin.header.var_names)
    print(resin.header.var_IDs)
    print(resin.time[1:10])
    print(resin.read_var_in_frame(1, 'U')[1:4])  # read the first 3 values of U in the second frame

# ==================================================================
logger.info('Finished!')