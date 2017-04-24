#!/usr/bin/env python
# * coding: utf8 *

import os
import logging
import logging.config
import numpy as np
from common.arg_command_line import myargparse
from slf import Serafin


if not os.path.exists('log'):
    os.makedirs('log')

# define script arguments
parser = myargparse(description=__doc__, add_args=['force', 'verbose'])
# parser.add_argument('inname', help='Serafin input filename')
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
logger.info('Start running the script..')

# ==================================================================
# =========== here goes the script =================================

if not os.path.exists('out'):
    os.makedirs('out')

with Serafin.Read('testdata\\r2d_malpasset-small_SERAFIND.slf', args.lang) as resin:
    resin.read_header()
    resin.get_time()

    print(resin.time)
    print(resin.header.var_IDs)
    print(resin.read_var_in_frame(2, 'U')[1:10])

    with Serafin.Write('out\\r2d_malpasset-small_SERAFIND_UVM.slf', args.lang, args.force) as resout:
        header = resin.header.copy()

        header.nb_var = 3
        header.var_IDs = ['U', 'V', 'M']
        header.var_names = [b'VITESSE U       ', b'VITESSE V       ', b'VITESSE SCALAIRE']
        header.var_units = [b'M/S             ', b'M/S             ', b'M/S             ']

        resout.write_header(header)

        for i in range(len(resin.time)):
            vals = resin.read_vars_in_frame(i, ['U', 'V'])
            vals = np.vstack([vals, np.sqrt(np.square(vals[0]) + np.square(vals[1]))])
            resout.write_entire_frame(header, resin.time[i], vals)


with Serafin.Read('out\\r2d_malpasset-small_SERAFIND_UVM.slf', args.lang) as resin:
    resin.read_header()
    resin.get_time()
    print(resin.time)
    print(resin.header.var_IDs)
    print(resin.read_var_in_frame(2, 'U')[1:5])
    print(resin.read_var_in_frame(2, 'V')[1:5])
    print(resin.read_var_in_frame(2, 'M')[1:5])



# ==================================================================
logger.info('Finished!')


