#!/usr/bin/env python
"""
Compute the max over some variables for a serie of files (which may contain several frames).
The output file contains a single frame with the variables.
This tool has some limitations :
- vectors are not considered as such
- meshes have to be similar
"""
import numpy as np
import sys

from pyteltools.conf import settings
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_max_over_files(args):
    if args.vars is None:
        with Serafin.Read(args.in_slfs[0], args.lang) as resin:
            resin.read_header()
            var_IDs = resin.header.var_IDs if args.vars is None else args.vars
    else:
        var_IDs = args.vars

    output_header = None
    max_values = None
    for i, in_slf in enumerate(args.in_slfs):
        with Serafin.Read(in_slf, args.lang) as resin:
            resin.read_header()
            logger.info(resin.header.summary())
            if not resin.header.is_2d:
                logger.critical('The file has to be a 2D Serafin!')
                sys.exit(3)
            resin.get_time()

            for var_ID in var_IDs:
                if var_ID not in resin.header.var_IDs:
                    logger.critical('The variable %s is missing in %s' % (var_ID, in_slf))
                    sys.exit(3)

            if i == 0:
                output_header = resin.header.copy()
                output_header.empty_variables()
                for var_ID in var_IDs:
                    output_header.add_variable_from_ID(var_ID)
                max_values = np.empty((output_header.nb_var, output_header.nb_nodes),
                                      dtype=output_header.np_float_type)
            else:
                if not resin.header.same_2d_mesh(output_header):
                    logger.critical('The mesh of %s is different from the first one' % (in_slf))
                    sys.exit(1)

            for time_index, time in enumerate(resin.time):
                for j, var_ID in enumerate(var_IDs):
                    values = resin.read_var_in_frame(time_index, var_ID)
                    if time_index == 0 and i == 0:
                        max_values[j, :] = values
                    else:
                        max_values[j, :] = np.maximum(max_values[j, :], values)

    with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
        resout.write_header(output_header)
        resout.write_entire_frame(output_header, 0.0, max_values)


parser = PyTelToolsArgParse(description=__doc__)
parser.add_argument('in_slfs', help='List of Serafin input filenames', nargs='+')
parser.add_argument('out_slf', help='Serafin output filename')
parser.add_argument('--vars', nargs='+', help='variable(s) to extract (by default: all variables)', default=None,
                    metavar=('VA', 'VB'))
parser.add_argument('--lang', help="Serafin language for variables detection: 'fr' or 'en'",
                    default=settings.LANG)
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_max_over_files(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
