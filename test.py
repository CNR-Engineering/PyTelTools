#!/usr/bin/env python
# * coding: utf8 *

import os
import logging
import logging.config
import numpy as np
from common.arg_command_line import myargparse
from slf import Serafin
from slf.SerafinVariables import get_additional_computations, do_calculations_in_frame, filter_necessary_equations


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
    print(resin.read_var_in_frame(2, 'U')[1:5])
    print(resin.read_var_in_frame(2, 'V')[1:5])

    selected_var_IDs = ['U', 'V', 'H', 'Q']
    additional_computations = get_additional_computations(resin.header.var_IDs)
    necessary_equations = filter_necessary_equations(additional_computations, selected_var_IDs)
    print('Need to do %d additional computation' % len(necessary_equations))

    with Serafin.Write('out\\r2d_malpasset-small_SERAFIND_UVM.slf', args.lang, args.force) as resout:
        output_header = resin.header.copy()
        output_header.nb_var = len(selected_var_IDs)
        output_header.var_IDs = selected_var_IDs
        output_header.var_names, output_header.var_units = [], []
        for var_ID in selected_var_IDs:
            name, unit = resin.header.specifications.ID_to_name_unit(var_ID)
            output_header.var_names.append(name)
            output_header.var_units.append(unit)

        resout.write_header(output_header)

        for index in range(len(resin.time)):
            vals = do_calculations_in_frame(necessary_equations, resin, index, selected_var_IDs)
            resout.write_entire_frame(output_header, resin.time[index], vals)


with Serafin.Read('out\\r2d_malpasset-small_SERAFIND_UVM.slf', args.lang) as resin:
    resin.read_header()
    resin.get_time()
    print(resin.time)
    print(resin.header.var_IDs)
    print(resin.read_var_in_frame(2, 'U')[1:5])
    print(resin.read_var_in_frame(2, 'V')[1:5])
    print(resin.read_var_in_frame(2, 'Q')[1:5])



# ==================================================================
logger.info('Finished!')


