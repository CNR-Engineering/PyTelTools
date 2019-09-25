#!/usr/bin/env python
"""
Compute the max or min over some variables for a serie of files (which may contain several frames).
This operation can be performed only on some zones defined by polygon(s).
In this case the values in the area not covered by the polygons are set to the first file and first frame.
The output file contains a single frame with the variables.

This tool has some limitations:
- vectors are not considered as such
- meshes have to be similar
"""
import numpy as np
from shapefile import ShapefileException
from shapely.geometry import Point
import sys

from pyteltools.conf import settings
from pyteltools.geom import Shapefile
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_max_over_files(args):
    if args.vars is None:
        with Serafin.Read(args.in_slfs[0], args.lang) as resin:
            resin.read_header()
            var_IDs = resin.header.var_IDs if args.vars is None else args.vars
    else:
        var_IDs = args.vars

    if args.operation == 'max':
        fun = np.maximum
    elif args.operation == 'min':
        fun = np.minimum
    else:
        raise NotImplementedError

    # Read polygons
    if args.in_polygons is not None:
        if not args.in_polygons.endswith('.shp'):
            logger.critical('File "%s" is not a shp file.' % args.in_polygons)
            sys.exit(3)
        polygons = []
        try:
            for polygon in Shapefile.get_polygons(args.in_polygons):
                polygons.append(polygon)
        except ShapefileException as e:
            logger.error(e)
            sys.exit(3)

        if not polygons:
            logger.error('The file does not contain any polygon.')
            sys.exit(1)
        logger.info('The file contains {} polygon{}.'.format(len(polygons), 's' if len(polygons) > 1 else ''))
    else:
        polygons = None

    output_header = None
    out_values = None  # min or max values
    mask_nodes = None
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
                out_values = np.empty((output_header.nb_var, output_header.nb_nodes),
                                      dtype=output_header.np_float_type)
                if polygons is not None:
                    mask_nodes = np.zeros(output_header.nb_nodes, dtype=bool)
                    for idx_node, (x, y) in enumerate(zip(output_header.x, output_header.y)):
                        point = Point(x, y)
                        for polygon in polygons:
                            if polygon.contains(point):
                                mask_nodes[idx_node] = True
                                break
                    logger.info('Number of nodes inside polygon(s): %i (over %i)'
                                % (mask_nodes.sum(), output_header.nb_nodes))
                else:
                    mask_nodes = np.ones(output_header.nb_nodes, dtype=bool)
            else:
                if not resin.header.same_2d_mesh(output_header):
                    logger.critical('The mesh of %s is different from the first one' % in_slf)
                    sys.exit(1)

            for time_index, time in enumerate(resin.time):
                for j, var_ID in enumerate(var_IDs):
                    values = resin.read_var_in_frame(time_index, var_ID)
                    if time_index == 0 and i == 0:
                        out_values[j, :] = values
                    else:
                        out_values[j, mask_nodes] = fun(out_values[j, mask_nodes], values[mask_nodes])

    with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
        resout.write_header(output_header)
        resout.write_entire_frame(output_header, 0.0, out_values)


parser = PyTelToolsArgParse(description=__doc__)
parser.add_argument('in_slfs', help='List of Serafin input filenames', nargs='+')
parser.add_argument('out_slf', help='Serafin output filename')
parser.add_argument('--operation', help='min or max function selector', choices=('min', 'max'), default='max')
parser.add_argument('--in_polygons', help='file containing polygon(s)')
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
