#!/usr/bin/env python
"""
Extract last temporal frame of a 2D/3D Serafin file
"""

import numpy as np
import sys

from pyteltools.geom.transformation import Transformation
from pyteltools.slf import Serafin
from pyteltools.utils.cli import logger, PyTelToolsArgParse


def slf_last(args):
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

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

        values = np.empty((output_header.nb_var, output_header.nb_nodes), dtype=output_header.np_float_type)
        with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
            resout.write_header(output_header)

            time_index = len(resin.time) - 1
            time = resin.time[-1] if args.time is None else args.time

            for i, var_ID in enumerate(output_header.var_IDs):
                values[i, :] = resin.read_var_in_frame(time_index, var_ID)

            resout.write_entire_frame(output_header, time, values)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])
parser.add_argument('--time', help='time in seconds to write last frame (set to frame time by default)', type=float)
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_last(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
