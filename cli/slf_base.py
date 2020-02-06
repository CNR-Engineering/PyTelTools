#!/usr/bin/env python
"""
Performs multiple operations on a Serafin file:
- compute and/or remove variables
- mesh transformations (coordinates)
- select frames
"""

import sys
from tqdm import tqdm

from pyteltools.geom.transformation import Transformation
from pyteltools.slf import Serafin
from pyteltools.slf.variables import do_calculations_in_frame, get_necessary_equations
from pyteltools.slf.variable.variables_2d import FRICTION_LAWS, get_US_equation, STRICKLER_ID
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_base(args):
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        output_header = resin.header.copy()
        # Shift mesh coordinates if necessary
        if args.shift:
            output_header.transform_mesh([Transformation(0, 1, 1, args.shift[0], args.shift[1], 0)])
        # Set mesh origin coordinates
        if args.set_mesh_origin:
            output_header.set_mesh_origin(args.set_mesh_origin[0], args.set_mesh_origin[1])

        # Toggle output file endianness if necessary
        if args.toggle_endianness:
            output_header.toggle_endianness()

        # Convert to single precision
        if args.to_single_precision:
            if resin.header.is_double_precision():
                output_header.to_single_precision()
            else:
                logger.warn('Input file is already single precision! Argument `--to_single_precision` is ignored')

        # Remove variables if necessary
        if args.var2del:
            output_header.empty_variables()
            for var_ID, var_name, var_unit in zip(resin.header.var_IDs, resin.header.var_names, resin.header.var_units):
                if var_ID not in args.var2del:
                    output_header.add_variable(var_ID, var_name, var_unit)

        # Add new derived variables
        if args.var2add is not None:
            for var_ID in args.var2add:
                if var_ID in output_header.var_IDs:
                    logger.warn('Variable %s is already present (or asked)' % var_ID)
                else:
                    output_header.add_variable_from_ID(var_ID)

        us_equation = get_US_equation(args.friction_law)
        necessary_equations = get_necessary_equations(resin.header.var_IDs, output_header.var_IDs,
                                                      is_2d=resin.header.is_2d, us_equation=us_equation)

        with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
            resout.write_header(output_header)

            for time_index, time in tqdm(resin.subset_time(args.start, args.end, args.ech), unit='frame'):
                values = do_calculations_in_frame(necessary_equations, resin, time_index, output_header.var_IDs,
                                                  output_header.np_float_type, is_2d=output_header.is_2d,
                                                  us_equation=us_equation, ori_values={})
                resout.write_entire_frame(output_header, time, values)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])

parser.add_argument('--set_mesh_origin', type=float, nargs=2, help='Mesh origin coordinates (x, y)', metavar=('X', 'Y'))

group_var = parser.add_argument_group('Serafin variables (optional)',
    'See variables abbrevations on https://github.com/CNR-Engineering/PyTelTools/wiki/Notations-of-variables')
group_var.add_argument('--var2del', nargs='+', help='variable(s) to delete', default=[], metavar=('VA', 'VB'))
group_var.add_argument('--var2add', nargs='+', help='variable(s) to add', default=[], metavar=('VA', 'VB'))
help_friction_laws = ', '.join(['%i=%s' % (i, law) for i, law in enumerate(FRICTION_LAWS)])
group_var.add_argument('--friction_law', type=int, help='friction law identifier: %s' % help_friction_laws,
                       choices=range(len(FRICTION_LAWS)), default=STRICKLER_ID)

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
        sys.exit(1)
