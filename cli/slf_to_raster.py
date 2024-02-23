#!/usr/bin/env python
"""
Convert all variables of a single frame (from a Serafin file) to a tif raster (one band per variable)
Beware: Output file is overwritten if already present
"""
from osgeo import gdal, osr
import matplotlib.tri as mtri
import numpy as np
import sys

from pyteltools.geom.transformation import Transformation
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


WATER_DEPTH_ID = 'H'


def arrays2raster(raster_filename, xy_raster_origin, dx, dy, array_list, epsg=None):
    nb_var = len(array_list)
    nb_rows, nb_cols = array_list[0][1].shape
    logger.info("Regular grid size : %i rows x %i columns" % (nb_rows, nb_cols))

    origin_x = xy_raster_origin[0]
    origin_y = xy_raster_origin[1]

    driver = gdal.GetDriverByName('GTiff')
    out_raster = driver.Create(raster_filename, nb_cols, nb_rows, nb_var, gdal.GDT_Float64)

    # Set grid and EPSG if necessary
    out_raster.SetGeoTransform((origin_x, dx, 0, origin_y, 0, dy))
    if epsg is not None:  # EPSG attribution seems buggy
        out_raster_srs = osr.SpatialReference()
        out_raster_srs.ImportFromEPSG(epsg)
        out_raster.SetProjection(out_raster_srs.ExportToWkt())

    # Add one band per variable
    for i_var, (var_ID, array) in enumerate(array_list):
        if array.shape != (nb_rows, nb_cols):
            raise RuntimeError
        outband = out_raster.GetRasterBand(i_var + 1)
        outband.SetDescription(var_ID)
        outband.WriteArray(array)
        outband.FlushCache()


def slf_to_raster(args):
    with Serafin.Read(args.in_slf, args.lang) as resin:
        resin.read_header()
        header = resin.header
        logger.info(header.summary())
        resin.get_time()

        if args.vars is None:
            var_names = [var_name.decode('utf-8') for var_name in header.var_names]
            var_IDs = header.var_IDs
        else:
            var_names = []
            var_IDs = []
            for var_ID, var_name in zip(header.var_IDs, header.var_names):
                if var_ID in args.vars:
                    var_names.append(var_name.decode('utf-8'))
                    var_IDs.append(var_ID)

        # Shift mesh coordinates if necessary
        if args.shift:
            header.transform_mesh([Transformation(0, 1, 1, args.shift[0], args.shift[1], 0)])

        # Build output regular grid and matplotlib triangulation of the mesh
        m_xi, m_yi = np.meshgrid(np.arange(header.x.min(), header.x.max(), args.resolution),
                                 np.arange(header.y.min(), header.y.max(), args.resolution))
        triang = mtri.Triangulation(header.x, header.y, triangles=header.ikle_2d - 1)

        # Build mask to clip values where water depth is below Hmin_to_clip
        if args.Hmin_to_clip is not None:
            values = resin.read_var_in_frame(args.frame_index, WATER_DEPTH_ID)
            interp = mtri.LinearTriInterpolator(triang, values)
            data = interp(m_xi, m_yi)[::-1]  # reverse array so the tif looks like the array
            with np.errstate(invalid='ignore'):
                mask = data <= args.Hmin_to_clip
        else:
            mask = None

        # Build list containing all interpolated variables on the regular grid
        array_list = []
        for i, (var_ID, var_name) in enumerate(zip(var_IDs, var_names)):
            values = resin.read_var_in_frame(args.frame_index, var_ID)
            interp = mtri.LinearTriInterpolator(triang, values)
            data = interp(m_xi, m_yi)[::-1]  # reverse array so the tif looks like the array

            if mask is not None:
                data = np.where(mask, np.nan, data)

            array_list.append((var_name, data))
            logger.info("Min and max values for interpolated %s variable: [%f, %f]"
                        % (var_name, np.nanmin(data), np.nanmax(data)))

        # Write data in the raster output file
        arrays2raster(args.out_tif, (header.x.min(), header.y.max()),
                      args.resolution, -args.resolution, array_list, epsg=args.epsg)


parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'shift'])
parser.add_argument('out_tif', help='output GeoTIFF raster file (with .tif extension)')
parser.add_argument('resolution', type=float, help='sampling space step (in meters)')
parser.add_argument('--vars', nargs='+', help='variable(s) to extract (by default: every variables)', default=None,
                    metavar=('VA', 'VB'))
parser.add_argument('--frame_index', type=int, help='index of the target temporal frame (0-indexed integer)', default=0)
parser.add_argument('--epsg', type=int, help='EPSG code for output file', default=None)
parser.add_argument('--Hmin_to_clip', type=float,
                    help='set to NaN all values where water depth (H) is below this threshold', default=None)
parser.add_group_general(['verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        slf_to_raster(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
