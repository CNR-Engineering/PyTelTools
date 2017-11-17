#!/usr/bin/env python
"""
Interpolate on a set of points for every frame
"""

import csv
import sys
from tqdm import tqdm
from shapefile import ShapefileException

from pyteltools.conf import settings
from pyteltools.geom import Shapefile
from pyteltools.slf import Serafin
from pyteltools.slf.interpolation import MeshInterpolator
from pyteltools.utils.cli import logger, PyTelToolsArgParse


def slf_int2d(args):
    # Read set of points file
    fields, indices = Shapefile.get_attribute_names(args.in_points)
    points = []
    attributes = []
    for point, attribute in Shapefile.get_points(args.in_points, indices):
        points.append(point)
        attributes.append(attribute)

    if not points:
        logger.error('The Shapefile does not contain any point.')
        sys.exit(1)

    # Read Serafin file
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())

        if not resin.header.is_2d:
            logger.error('The file has to be a 2D Serafin!')
            sys.exit(3)

        resin.get_time()

        output_header = resin.header.copy()

        mesh = MeshInterpolator(output_header, True)
        is_inside, point_interpolators = mesh.get_point_interpolators(points)
        nb_inside = sum(map(int, is_inside))

        if nb_inside == 0:
            logger.error('No point inside the mesh.')
            sys.exit(3)
        logger.debug('The file contains {} point{}. {} point{} inside the mesh'.format(
                     len(points), 's' if len(points) > 1 else '',
                     nb_inside, 's are' if nb_inside > 1 else ' is'))

        var_IDs = output_header.var_IDs if args.vars is None else args.vars

        mode = 'w' if args.force else 'x'
        with open(args.out_csv, mode, newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=args.sep)

            header = ['time_id', 'time']
            if args.long:
                header = header + ['point_id', 'point_x', 'point_y', 'variable', 'value']
            else:
                for pt_id, (x, y) in enumerate(points):
                    for var in var_IDs:
                        header.append('Point %d %s (%s|%s)' % (pt_id + 1, var, settings.FMT_COORD.format(x),
                                                               settings.FMT_COORD.format(y)))
            csvwriter.writerow(header)

            for time_index, time in enumerate(tqdm(resin.time, unit='frame')):
                values = [time_index, time]

                for var_ID in var_IDs:
                    var = resin.read_var_in_frame(time_index, var_ID)
                    for pt_id, (point, point_interpolator) in enumerate(zip(points, point_interpolators)):
                        if args.long:
                            values_long = values + [str(pt_id + 1)] + [settings.FMT_COORD.format(x) for x in point]

                        if point_interpolator is None:
                            if args.long:
                                csvwriter.writerow(values_long + [var_ID, settings.NAN_STR])
                            else:
                                values.append(settings.NAN_STR)
                        else:
                            (i, j, k), interpolator = point_interpolator
                            int_value = settings.FMT_FLOAT.format(interpolator.dot(var[[i, j, k]]))
                            if args.long:
                                csvwriter.writerow(values_long + [var_ID, int_value])
                            else:
                                values.append(int_value)

                if not args.long: csvwriter.writerow(values)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf'])
parser.add_argument('in_points', help='set of points file (*.shp)')
parser.add_known_argument('out_csv')
parser.add_argument('--long', help='write CSV with long format (variables are also in rows) instead of wide format',
                    action='store_true')
parser.add_argument('--vars', nargs='+', help='variable(s) to extract (by default: every variables)', default=None,
                    metavar=('VA', 'VB'))
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_int2d(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
    except ShapefileException as e:
        logger.error(e)
        sys.exit(3)
    except FileNotFoundError as e:
        logger.error('Input file %s not found.' % e.filename)
        sys.exit(3)
    except FileExistsError as e:
        logger.error('Output file %s already exists. Remove it or add `--force` argument' % e.filename)
        sys.exit(3)
