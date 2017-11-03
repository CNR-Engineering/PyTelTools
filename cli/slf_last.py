#!/usr/bin/python3
"""
Extract last temporal frame of a 2D/3D Serafin file
"""

import numpy as np
import sys

from utils.util import logger, MyArgParse
from PyTelTools.geom.transformation import Translation
from PyTelTools.slf import Serafin


def slf_last(args):
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

        # Convert to single precision
        if args.to_single_precision:
            if resin.header.is_double_precision():
                output_header.to_single_precision()
            else:
                logger.warn('Input file is already single precision! Argument `--to_single_precision` is ignored')

        values = np.empty((output_header.nb_var, resin.header.nb_nodes), dtype=resin.header.np_float_type)
        with Serafin.Write(args.out_slf, args.lang) as resout:
            resout.write_header(resin.header)

            time_index = -1
            time = resin.time[-1] if args.time is None else args.time

            for i, var_ID in enumerate(resin.header.var_IDs):
                values[i, :] = resin.read_var_in_frame(time_index, var_ID)

            resout.write_entire_frame(output_header, time, values)


parser = MyArgParse(description=__doc__, add_args=['in_slf', 'out_slf', 'shift'])
parser.add_argument('--time', help='time in seconds to write last frame (set to frame time by default)', type=float)
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_last(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(2)
