#!/usr/bin/env python
"""
Compute volumes (between upper and lower variables) within polygons
"""
from shapefile import ShapefileException
import sys
from tqdm import tqdm

from pyteltools.conf import settings
from pyteltools.geom import BlueKenue, Shapefile
from pyteltools.slf import Serafin
from pyteltools.slf.volume import VolumeCalculator
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def slf_volume(args):
    # Read set of lines from input file
    polygons = []
    if args.in_polygons.endswith('.i2s'):
        with BlueKenue.Read(args.in_polygons) as f:
            f.read_header()
            for poly in f.get_polygons():
                polygons.append(poly)
    elif args.in_polygons.endswith('.shp'):
        try:
            for polygon in Shapefile.get_polygons(args.in_polygons):
                polygons.append(polygon)
        except ShapefileException as e:
            logger.error(e)
            sys.exit(3)
    else:
        logger.error('File "%s" is not a i2s or shp file.' % args.in_polygons)
        sys.exit(2)

    if not polygons:
        logger.error('The file does not contain any polygon.')
        sys.exit(1)
    logger.debug('The file contains {} polygon{}.'.format(len(polygons), 's' if len(polygons) > 1 else ''))

    names = ['Polygon %d' % (i + 1) for i in range(len(polygons))]

    # Read Serafin file
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        if not resin.header.is_2d:
            logger.error('The file has to be a 2D Serafin!')
            sys.exit(3)

        # Check variables consistency
        if args.upper_var not in resin.header.var_IDs:
            logger.error('Upper variable "%s" is not in Serafin file' % args.upper_var)
            sys.exit(1)
        upper_var = args.upper_var
        lower_var = args.lower_var
        if args.lower_var is not None:
            if args.lower_var == 'init':
                lower_var = VolumeCalculator.INIT_VALUE
            else:
                if lower_var not in resin.header.var_IDs:
                    logger.error('Lower variable "%s" is not in Serafin file' % lower_var)
                    sys.exit(1)

        if args.detailed:
            volume_type = VolumeCalculator.POSITIVE
        else:
            volume_type = VolumeCalculator.NET
        calculator = VolumeCalculator(volume_type, upper_var, lower_var, resin, names, polygons, args.ech)
        calculator.construct_triangles(tqdm)
        calculator.construct_weights(tqdm)

        result = []
        for time_index in tqdm(calculator.time_indices, unit='frame'):
            i_result = [str(resin.time[time_index])]
            values = calculator.read_values_in_frame(time_index)

            for j in range(len(calculator.polygons)):
                weight = calculator.weights[j]
                volume = calculator.volume_in_frame_in_polygon(weight, values, calculator.polygons[j])
                if calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append(settings.FMT_FLOAT.format(v))
                else:
                    i_result.append(settings.FMT_FLOAT.format(volume))
            result.append(i_result)

        # Write CSV
        mode = 'w' if args.force else 'x'
        with open(args.out_csv, mode) as out_csv:
            calculator.write_csv(result, out_csv, args.sep)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf'])
parser.add_argument('in_polygons', help='set of polygons file (*.shp, *.i2s)')
parser.add_argument('--ech', type=int, help='frequency sampling of input', default=1)
parser.add_argument('--upper_var', help='upper variable', metavar='VA', required=True)
parser.add_argument('--lower_var', help='lower variable', metavar='VB', default=None)
parser.add_argument('--detailed', help='add positive and negative volumes', action='store_true')

parser.add_known_argument('out_csv')
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_volume(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error('Input file %s not found.' % e.filename)
        sys.exit(3)
    except FileExistsError as e:
        logger.error('Output file %s already exists. Remove it or add `--force` argument' % e.filename)
        sys.exit(3)
