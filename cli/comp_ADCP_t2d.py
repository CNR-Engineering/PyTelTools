#!/usr/bin/env python
"""
Read ADCP file and TELEMAC file to make a comparison
"""

from pyproj import Proj, transform
import csv
import fiona
from fiona.crs import from_epsg
import os
from shapely.geometry import mapping, LineString

from adcploader import *
import averaging

from pyteltools.slf import Serafin
from pyteltools.geom import Shapefile
from pyteltools.slf.interpolation import MeshInterpolator
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse
from pyteltools.geom.transformation import Transformation


NODATA = '-32768'


def ADCP_comp(args):
    x_mes = []
    y_mes = []
    cord_mes = open(args.inADCP_GPS).read().splitlines()
    for x_l in cord_mes:
        y, x = x_l.split(',')
        if x == NODATA or y == NODATA:
            print("Warning: one point is missing")
        else:
            x_mes.append(x)
            y_mes.append(y)
    x_mes = [float(a) for a in x_mes]
    y_mes = [float(a) for a in y_mes]
    inProj = Proj("+init=EPSG:%i" % args.inEPSG)
    outProj = Proj("+init=EPSG:%i" % args.outEPSG)
    x_mes, y_mes = transform(inProj, outProj, x_mes, y_mes)

    SCHEMA = {'geometry': 'LineString',
              'properties': {'nom': 'str'}}
    with fiona.open(args.outADCP_GPS, 'w', 'ESRI Shapefile', SCHEMA, crs=from_epsg(args.outEPSG)) as out_shp:
        Ltest = LineString([(x_2, y_2) for x_2, y_2 in zip(x_mes, y_mes)])
        elem = {}
        elem['geometry'] = mapping(Ltest)
        elem['properties'] = {
            'nom': 'ADCP line'}
        out_shp.write(elem)

    p_raw = RawProfileObj(args.inADCP)
    processing_settings = {'proj_method': 2}
    startingpoint = dict(start=Vector(0, 0))
    p0 = ProcessedProfileObj(p_raw, processing_settings, startingpoint)
    profile_averaged = averaging.get_averaged_profile(p0, cfg={'order': 15})
    header = 'X;Y;Uadcp;Vadcp;MagnitudeXY;Hadcp\n'
    writeAscii2D(profile_averaged, '{x};{y};{vx};{vy};{vmag};{depth}', args.outADCP, header=header)

    if args.inTELEMAC:
        with open(args.outT2DCSV, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=';')
            HEADER = ['folder', 'time_id', 'time', 'point_x', 'point_y', 'distance', 'value']
            csvwriter.writerow(HEADER)

            for slf_path in args.inTELEMAC:
                folder = os.path.basename(os.path.split(slf_path)[0])
                with Serafin.Read(slf_path, 'fr') as resin:
                    resin.read_header()
                    logger.info(resin.header.summary())
                    resin.get_time()
                    output_header = resin.header.copy()
                    if args.shift:
                        output_header.transform_mesh([Transformation(0, 1, 1, args.shift[0], args.shift[1], 0)])
                    mesh = MeshInterpolator(output_header, True)
                    lines = []
                    for poly in Shapefile.get_lines(args.outADCP_GPS, shape_type=3):
                        lines.append(poly)
                    nb_nonempty, indices_nonempty, line_interpolators, line_interpolators_internal = \
                        mesh.get_line_interpolators(lines)
                    res = mesh.interpolate_along_lines(resin, 'M', list(range(len(resin.time))), indices_nonempty,
                                                       line_interpolators, '{:.6e}')
                    csvwriter.writerows([[folder] + x[2] for x in res])


parser = PyTelToolsArgParse(description=__doc__, add_args=['shift'])
parser.add_argument("inADCP_GPS", help="GPS ADCP (_gps_ASC.txt) input filename")
parser.add_argument("inADCP", help="ADCP (_ASC.txt) input filename")
parser.add_argument("--inTELEMAC", help="Telemac-2D result files with M (r2d_last.slf)", nargs='*')
parser.add_argument("outADCP_GPS", help="GPS ADCP (.shp) output filename")
parser.add_argument("outADCP", help="ADCP (.csv) output filename")
parser.add_argument("outT2DCSV", help="CSV output filename")
parser.add_argument("--inEPSG", help="input EPSG", type=int, default=4326)  # WGS-84
parser.add_argument("--outEPSG", help="output EPSG", type=int, default=2154)  # Lambert 93 (France)


if __name__ == "__main__":
    args = parser.parse_args()
    ADCP_comp(args)
