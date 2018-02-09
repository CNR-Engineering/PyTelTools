#!/usr/bin/env python
"""
Compute bottom friction force on multiple zones

Outputs:
* write a SerafinOutput variables : 'W', 'US', 'TAU'
* write the values in stdout

Assumes Strickler friction law
"""

import numpy as np
from shapefile import ShapefileException
from shapely.geometry import Point
import sys
from tqdm import tqdm

from pyteltools.geom import Shapefile
from pyteltools.slf import Serafin
from pyteltools.slf.variables import do_calculations_in_frame, get_necessary_equations
from pyteltools.slf.variable.variables_2d import STRICKLER_EQUATION
from pyteltools.slf.volume import VolumeCalculator
from pyteltools.utils.cli import logger, PyTelToolsArgParse


def slf_bottom_friction(args):
    # Read polygons to compute volume
    if not args.in_polygons.endswith('.shp'):
        logger.critical('File "%s" is not a shp file.' % args.in_polygons)
        sys.exit(2)
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
    logger.debug('The file contains {} polygon{}.'.format(len(polygons), 's' if len(polygons) > 1 else ''))

    names = ['Polygon %d' % (i + 1) for i in range(len(polygons))]

    varIDs = ['US', 'TAU']
    out_varIDs = ['W'] + varIDs
    pos_TAU = out_varIDs.index('TAU')
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        if not resin.header.is_2d:
            logger.critical('The file has to be a 2D Serafin!')
            sys.exit(3)

        in_varIDs = resin.header.var_IDs

        # Compute Strickler values if necessary
        ori_values = {}
        if args.in_strickler_zones is not None:
            if not args.in_strickler_zones.endswith('.shp'):
                logger.critical('File "%s" is not a shp file.' % args.in_strickler_zones)
                sys.exit(2)

            attributes = Shapefile.get_numeric_attribute_names(args.in_strickler_zones)
            try:
                index_attr = [attr for _, attr in attributes].index(args.in_strickler_attr)
            except ValueError:
                logger.critical('Attribute "%s" is not found.' % args.in_strickler_attr)
                sys.exit(2)

            strickler_zones = []
            try:
                for zone in Shapefile.get_polygons(args.in_strickler_zones):
                    strickler_zones.append(zone)
            except ShapefileException as e:
                logger.error(e)
                sys.exit(3)

            if not strickler_zones:
                logger.error('The file does not contain any friction zone.')
                sys.exit(1)

            logger.debug('Recomputing friction coefficient values from zones')
            friction_coeff = np.full(resin.header.nb_nodes_2d, 0.0)  # default value for nodes not included in any zone
            for i, (x, y) in enumerate(zip(tqdm(resin.header.x), tqdm(resin.header.y))):
                point = Point(x, y)
                for zone in strickler_zones:
                    if zone.contains(point):
                        friction_coeff[i] = zone.attributes()[index_attr]
                        exit
            in_varIDs.append('W')
            ori_values['W'] = friction_coeff
        else:
            if 'W' not in resin.header.varIDs:
                logger.critical('The variable W is missing.')
                sys.exit(1)

        resin.get_time()
        necessary_equations = get_necessary_equations(in_varIDs, out_varIDs, is_2d=True,
                                                      us_equation=STRICKLER_EQUATION)

        calculator = VolumeCalculator(VolumeCalculator.NET, 'TAU', None, resin, names, polygons, 1)
        calculator.construct_triangles(tqdm)
        calculator.construct_weights(tqdm)

        output_header = resin.header.copy()
        output_header.empty_variables()
        for var_ID in out_varIDs:
            output_header.add_variable_from_ID(var_ID)

        with Serafin.Write(args.out_slf, args.lang, args.force) as resout:
            resout.write_header(output_header)

            for time_index, time in enumerate(tqdm(resin.time)):
                values = do_calculations_in_frame(necessary_equations, resin, time_index, out_varIDs,
                                                  resin.header.np_float_type, is_2d=True,
                                                  us_equation=STRICKLER_EQUATION, ori_values=ori_values)

                resout.write_entire_frame(output_header, time, values)

                for j in range(len(calculator.polygons)):
                    weight = calculator.weights[j]
                    volume = calculator.volume_in_frame_in_polygon(weight, values[pos_TAU], calculator.polygons[j])
                    print('Polygon %d: %f N' % (j, volume))


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf'])
parser.add_argument('in_polygons', help='polygons file (*.shp)')
parser.add_argument('--in_strickler_zones', help='strickler zones file (*.shp)')
parser.add_argument('--in_strickler_attr', help='attribute to read strickler values `--in_stricker_zone`')
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_bottom_friction(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
    except FileNotFoundError as e:
        logger.critical('Input file %s not found.' % e.filename)
        sys.exit(3)
    except FileExistsError as e:
        logger.critical('Output file %s already exists. Remove it or add `--force` argument' % e.filename)
        sys.exit(3)
