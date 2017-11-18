#!/usr/bin/env python
"""
Compute (liquid or solid) 2D fluxes over time across sections
"""

from tqdm import tqdm
from shapefile import ShapefileException
import sys

from pyteltools.conf import settings
from pyteltools.geom import BlueKenue, Shapefile
from pyteltools.slf import Serafin
from pyteltools.slf.flux import FluxCalculator, PossibleFluxComputation
from pyteltools.utils.cli import logger, PyTelToolsArgParse



def slf_flux2d(args):
    # Read set of lines from input file
    polylines = []
    if args.in_sections.endswith('.i2s'):
        with BlueKenue.Read(args.in_sections) as f:
            f.read_header()
            for polyline in f.get_open_polylines():
                polylines.append(polyline)
    elif args.in_sections.endswith('.shp'):
        for polyline in Shapefile.get_open_polylines(args.in_sections):
            polylines.append(polyline)
    else:
        logger.error('File "%s" is not a i2s or shp file.' % args.in_sections)
        sys.exit(2)

    if not polylines:
        logger.error('The file does not contain any open polyline.')
        sys.exit(1)
    logger.debug('The file contains {} open polyline{}.'.format(len(polylines), 's' if len(polylines) > 1 else ''))

    # Read Serafin file
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        logger.info(resin.header.summary())
        resin.get_time()

        if not resin.header.is_2d:
            logger.error('The file has to be a 2D Serafin!')
            sys.exit(3)

        # Determine flux computations properties
        var_IDs = args.vectors + args.scalars
        variables_missing = [var_ID for var_ID in var_IDs if var_ID not in resin.header.var_IDs]
        if variables_missing:
            if len(variables_missing) > 1:
                logger.error('Variables {} are not present in the Serafin file'.format(variables_missing))
            else:
                logger.error('Variable {} is not present in the Serafin file'.format(variables_missing[0]))
            logger.error('Check also `--lang` argument for variable detection.')
            sys.exit(1)
        if var_IDs not in PossibleFluxComputation.common_fluxes():
            logger.warn('Flux computations is not common. Check what you are doing (or the language).')

        flux_type = PossibleFluxComputation.get_flux_type(var_IDs)

        section_names = ['Section %i' % (i + 1) for i in range(len(polylines))]
        calculator = FluxCalculator(flux_type, var_IDs, resin, section_names, polylines, args.ech)
        calculator.construct_triangles(tqdm)
        calculator.construct_intersections()
        result = []
        for time_index, time in enumerate(tqdm(resin.time, unit='frame')):
            i_result = [str(time)]
            values = []

            for var_ID in calculator.var_IDs:
                values.append(resin.read_var_in_frame(time_index, var_ID))

            for j in range(len(polylines)):
                intersections = calculator.intersections[j]
                flux = calculator.flux_in_frame(intersections, values)
                i_result.append(settings.FMT_FLOAT.format(flux))

            result.append(i_result)

        # Write CSV
        mode = 'w' if args.force else 'x'
        with open(args.out_csv, mode) as out_csv:
            calculator.write_csv(result, out_csv, settings.CSV_SEPARATOR)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf'])
parser.add_argument('in_sections', help='set of lines file (*.shp, *.i2s)')
parser.add_argument('--ech', type=int, help='frequency sampling of input', default=1)
parser.add_argument('--scalars', nargs='*', help='scalars to integrate (up to 2)', default=[], metavar=('VA', 'VB'))
parser.add_argument('--vectors', nargs=2, help='couple of vectors to integrate (X and Y vectors)', default=[],
                    metavar=('VX', 'VY'))

parser.add_known_argument('out_csv')
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_flux2d(args)
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
