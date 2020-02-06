#!/usr/bin/env python
"""
Perform a vertical operation on a 3D results file to get 2D
"""

import numpy as np
import sys
from tqdm import tqdm

from pyteltools.geom.transformation import Transformation
import pyteltools.slf.misc as operations
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_3d_to_2d(args):
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        if resin.header.is_2d:
            logger.critical('The input file is not 3D.')
            sys.exit(1)
        if 'Z' not in resin.header.var_IDs:
            logger.critical('The elevation variable Z is not found in the Serafin file.')
            sys.exit(1)
        if args.layer is not None:
            upper_plane = resin.header.nb_planes
            if args.layer < 1 or args.layer > upper_plane:
                logger.critical('Layer has to be in [1, %i]' % upper_plane)
                sys.exit(1)

        output_header = resin.header.copy_as_2d()
        # Shift mesh coordinates if necessary
        if args.shift:
            output_header.transform_mesh([Transformation(0, 1, 1, args.shift[0], args.shift[1], 0)])

        # Toggle output file endianness if necessary
        if args.toggle_endianness:
            output_header.toggle_endianness()

        # Convert to single precision
        if args.to_single_precision:
            if resin.header.is_double_precision():
                output_header.to_single_precision()
            else:
                logger.warn('Input file is already single precision! Argument `--to_single_precision` is ignored')

        if args.aggregation is not None:
            if args.aggregation == 'max':
                operation_type = operations.MAX
            elif args.aggregation == 'min':
                operation_type = operations.MIN
            else:  # args.aggregation == 'mean'
                operation_type = operations.MEAN
            selected_vars = [var for var in output_header.iter_on_all_variables()]
            vertical_calculator = operations.VerticalMaxMinMeanCalculator(operation_type, resin, output_header,
                                                                          selected_vars, args.vars)
            output_header.set_variables(vertical_calculator.get_variables())  # sort variables

        # Add some elevation variables
        for var_ID in args.vars:
            output_header.add_variable_from_ID(var_ID)

        with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
            resout.write_header(output_header)

            vars_2d = np.empty((output_header.nb_var, output_header.nb_nodes_2d), dtype=output_header.np_float_type)
            for time_index, time in enumerate(tqdm(resin.time, unit='frame')):
                if args.aggregation is not None:
                    vars_2d = vertical_calculator.max_min_mean_in_frame(time_index)
                else:
                    for i, var in enumerate(output_header.var_IDs):
                        vars_2d[i, :] = resin.read_var_in_frame_as_3d(time_index, var)[args.layer - 1, :]
                resout.write_entire_frame(output_header, time, vars_2d)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--layer', help='layer number (1=lower, nb_planes=upper)', type=int, metavar=1)
group.add_argument('--aggregation', help='operation over the vertical', choices=('max', 'min', 'mean'))
parser.add_argument('--vars', nargs='+', help='variable(s) deduced from Z', default=[], choices=('B', 'S', 'H'))
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_3d_to_2d(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
