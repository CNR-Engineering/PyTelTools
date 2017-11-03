#!/usr/bin/python3
"""
Performs multiple operations on a Serafin file:
- compute and/or remove variables
- mesh transformations (coordinates)
- select frames
"""

import sys
from tqdm import tqdm

from utils.util import logger, MyArgParse
from PyTelTools.geom.transformation import Translation
from PyTelTools.slf import Serafin
from PyTelTools.slf.variables import do_calculations_in_frame, get_necessary_equations


def slf_base(args):
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        output_header = resin.header.copy()
        # Shift mesh coordinates if necessary
        if args.shift:
            output_header.transform_mesh(Translation(args.shift[0], args.shift[1], 0))

        # Toogle output file endianness if necessary
        if args.toggle_endianness:
            output_header.toggle_endianness()

        # Remove variables if necessary
        output_header.empty_variables()
        for var_ID, var_name, var_unit in zip(resin.header.var_IDs, resin.header.var_names, resin.header.var_units):
            if args.var2del is not None:
                if var_ID not in args.var2del:
                    output_header.add_variable(var_ID, var_name, var_unit)
            else:
                output_header.add_variable(var_ID, var_name, var_unit)

        # Add new derived variables
        if args.var2add is not None:
            for var_ID in args.var2add:
                if var_ID in output_header.var_IDs:
                    logger.warn('Variable %s is already present (or asked)' % var_ID)
                else:
                    output_header.add_variable_from_ID(var_ID)

        # Convert to single precision
        if args.to_single_precision:
            if resin.header.is_double_precision():
                output_header.to_single_precision()
            else:
                logger.warn('Input file is already single precision! Argument `--to_single_precision` is ignored')

        necessary_equations = get_necessary_equations(resin.header.var_IDs, output_header.var_IDs,
                                                      is_2d=resin.header.is_2d)

        with Serafin.Write(args.out_slf, args.lang) as resout:
            resout.write_header(resin.header)

            for time_index, time in tqdm(resin.subset_time(args.start, args.end, args.ech), unit='frame'):
                values = do_calculations_in_frame(necessary_equations, resin, time_index, output_header.var_IDs,
                                                  output_header.np_float_type, is_2d=output_header.is_2d,
                                                  us_equation=None)
                resout.write_entire_frame(output_header, time, values)


parser = MyArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])

group_var = parser.add_argument_group('Serafin variables (optional)',
    'See variables abbrevations on https://github.com/CNR-Engineering/PyTelTools/wiki/Notations-of-variables')
group_var.add_argument('--var2del', nargs='+', help='variable(s) to delete', default=[], metavar=('V1', 'V2'))
group_var.add_argument('--var2add', nargs='+', help='variable(s) to add', default=[], metavar=('V1', 'V2'))

group_temp = parser.add_argument_group('Temporal operations (optional)')
group_temp.add_argument('--ech', type=int, help='frequency sampling of input', default=1)
group_temp.add_argument('--start', type=float, help='minimum time (in seconds)', default=-float('inf'))
group_temp.add_argument('--end', type=float, help='maximum time (in seconds)', default=float('inf'))

parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_base(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(2)
