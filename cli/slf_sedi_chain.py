#!/usr/bin/env python
"""
Estimate roughly bottom evolution from a 2D result in case of cohesive sediments
Basic implementation of Krone/Partheniades laws
"""
from copy import copy
import numpy as np
import sys

from pyteltools.geom.transformation import Transformation
from pyteltools.slf import Serafin
from pyteltools.slf.variable.variables_2d import FRICTION_LAWS, get_US_equation, STRICKLER_ID
from pyteltools.slf.variables import do_calculations_in_frame, get_necessary_equations
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_sedi_chain(args):
    # Check that float parameters are positive (especially ws!)
    for arg in ('Cmud', 'ws', 'C', 'M'):
        if getattr(args, arg) < 0:
            logger.critical('The argument %s has to be positive' % args)
            sys.exit(1)

    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        us_equation = get_US_equation(args.friction_law)
        necessary_equations = get_necessary_equations(resin.header.var_IDs, ['TAU'],
                                                      is_2d=True, us_equation=us_equation)

        if resin.header.nb_frames < 1:
            logger.critical('The input file must have at least one frame!')
            sys.exit(1)

        output_header = resin.header.copy()
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

        output_header.empty_variables()
        output_header.add_variable_from_ID('B')
        output_header.add_variable_from_ID('EV')

        with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
            resout.write_header(output_header)

            prev_time = None
            prev_tau = None
            initial_bottom = resin.read_var_in_frame(0, 'B')
            bottom = copy(initial_bottom)
            for time_index, time in enumerate(resin.time):
                tau = do_calculations_in_frame(necessary_equations, resin, time_index, ['TAU'],
                                               output_header.np_float_type, is_2d=True, us_equation=us_equation,
                                               ori_values={})[0]
                if prev_time is not None:
                    dt = time - prev_time
                    mean_tau = (prev_tau + tau)/2
                    if args.Tcd > 0:
                        bottom += args.ws * args.C * \
                                  (1 - np.clip(mean_tau/args.Tcd, a_min=None, a_max=1.)) * dt / args.Cmud
                    if args.Tce > 0:
                        bottom -= args.M * (np.clip(mean_tau/args.Tce, a_min=1., a_max=None) - 1.) * dt / args.Cmud

                evol_bottom = bottom - initial_bottom
                resout.write_entire_frame(output_header, time, np.vstack((bottom, evol_bottom)))

                prev_time = time
                prev_tau = tau


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])
help_friction_laws = ', '.join(['%i=%s' % (i, law) for i, law in enumerate(FRICTION_LAWS)])
parser.add_argument('--friction_law', type=int, help='friction law identifier: %s' % help_friction_laws,
                    choices=range(len(FRICTION_LAWS)), default=STRICKLER_ID)
parser.add_argument('--Cmud', help='mud concentration (liquid) [kg/m³]', type=float, default=1200)
group_deposition = parser.add_argument_group('Deposition', 'Parameters of Krone deposition law')
group_deposition.add_argument('--Tcd', help='critical Shear Stress for Deposition [Pa]', type=float, default=0.0)
group_deposition.add_argument('--ws', help='settling velocity [m/s]', type=float)
group_deposition.add_argument('--C', help='concentration (for deposition law) [kg/m³]', type=float)
group_erosion = parser.add_argument_group('Erosion', 'Parameters of Partheniades erosion law')
group_erosion.add_argument('--Tce', help='critical Shear Stress for Erosion [Pa]', type=float, default=0.0)
group_erosion.add_argument('--M', help='Partheniades coefficient', type=float)
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_sedi_chain(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
