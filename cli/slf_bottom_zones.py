#!/usr/bin/python3
"""
@brief:
Modify BOTTOM elevation from zones defined by a set of polylines.
Order of files is relevant and determines the priority in case of overlapping: first has the highest priority.

@features:
* interpolate intermediate point if bottom is below a threshold

@prerequisites:
* file is a mesh 2D
* variable 'B' (BOTTOM) is required
"""
import numpy as np
import sys
import shapely.geometry as geo

import pyteltools.geom.BlueKenue as bk
import pyteltools.geom.Shapefile as shp
from pyteltools.geom.geometry import Polyline
from pyteltools.geom.transformation import Transformation
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import logger, PyTelToolsArgParse


def set(value, _):
    return value


class Zone:
    def __init__(self, polyline_1, polyline_2, operator_str):
        self.polyline_1 = polyline_1.polyline()
        self.polyline_2 = polyline_2.polyline()
        if operator_str == 'min':
            self.operator = min
        elif operator_str == 'max':
            self.operator = max
        elif operator_str == 'set':
            self.operator = set
        else:
            raise NotImplementedError
        self.polygon = None
        self._build_polygon()

    def _build_polygon(self):
        outline_pts = list(self.polyline_1.coords) + list(reversed(self.polyline_2.coords))
        self.polygon = geo.Polygon(outline_pts)
        if not self.polygon.is_simple:  # FIXME: it should be "if not self.polygon.is_valid"
            print("Distance ligne = %s" % self.polyline_1.distance(self.polyline_2))
            print("Distance début = %s" % self.polyline_1.interpolate(0, normalized=True).distance(
                self.polyline_2.interpolate(0, normalized=True)))
            print("Distance fin = %s" % self.polyline_1.interpolate(1, normalized=True).distance(
                self.polyline_2.interpolate(1, normalized=True)))
            with bk.Write('debug.i3s') as out_i3s:
                out_i3s.write_header()
                out_i3s.write_lines([Polyline(self.polygon.exterior.coords)], [0.0])
            sys.exit("ERROR: Zone is invalid. Check polyline direction consistancy!")

    def contains(self, point):
        return self.polygon.contains(point)

    def interpolate(self, point):
        a = self.polyline_1
        b = self.polyline_2
        za = a.interpolate(a.project(point)).z
        zb = b.interpolate(b.project(point)).z
        da = point.distance(a)
        db = point.distance(b)
        return (db*za + da*zb)/(da + db)

    def get_closest_point(self, point):
        outline = self.polygon.exterior
        return outline.interpolate(outline.project(point))

    @staticmethod
    def get_zones_from_i3s_file(shp_name, threshold, operator_str):
        polylines = []

        attributes = shp.get_numeric_attribute_names(shp_name)
        if args.attr_to_shift_z is not None:
            try:
                index_attr = [attr for _, attr in attributes].index(args.attr_to_shift_z)
            except ValueError:
                logger.critical('Attribute "%s" is not found.' % args.attr_to_shift_z)
                sys.exit(1)

        for polyline in shp.get_open_polylines(shp_name):
            if not polyline.polyline().is_valid:
                sys.exit("ERROR: polyline is not valid (probably because it intersects itself)!")

            # Shift z (if requested)
            if args.attr_to_shift_z is not None:
                dz = polyline.attributes()[index_attr]
                print(dz)

                polyline = polyline.apply_transformations([Transformation(0.0, 1.0, 1.0, 0.0, 0.0, dz)])

            # Linear interpolation along the line for values below the threshold
            if threshold is not None:
                np_coord = np.array(polyline.coords())
                Xt = np.sqrt(np.power(np.ediff1d(np_coord[:, 0], to_begin=0.), 2) +
                             np.power(np.ediff1d(np_coord[:, 1], to_begin=0.), 2))
                Xt = Xt.cumsum()
                ref_rows = np_coord[:, 2] > args.threshold
                np_coord[:, 2] = np.interp(Xt, Xt[ref_rows], np_coord[ref_rows, 2])
                polyline = geo.LineString(np_coord)
            polylines.append(polyline)

        zones = []
        for prev_line, next_line in zip(polylines[:-1], polylines[1:]):
            zones.append(Zone(prev_line, next_line, operator_str))
        return zones


def bottom(args):
    if args.operations is None:
        args.operations = ['set'] * len(args.in_i3s_paths)
    if len(args.in_i3s_paths) != len(args.operations):
        raise RuntimeError

    # global prev_line, zones, np_coord, Xt, Z, ref_rows, polyline
    with Serafin.Read(args.in_slf, 'fr') as resin:
        resin.read_header()

        if not resin.header.is_2d:
            sys.exit("The current script is working only with 2D meshes !")

        resin.get_time()

        # Define zones from polylines
        zones = []
        for i3s_path, operator_str in zip(args.in_i3s_paths, args.operations):
            zones += Zone.get_zones_from_i3s_file(i3s_path, args.threshold, operator_str)

        with Serafin.Write(args.out_slf, 'fr', args.force) as resout:
            output_header = resin.header
            resout.write_header(output_header)
            pos_B = output_header.var_IDs.index('B')

            for time_index, time in enumerate(resin.time):
                var = np.empty((output_header.nb_var, output_header.nb_nodes), dtype=output_header.np_float_type)
                for i, var_ID in enumerate(output_header.var_IDs):
                    var[i, :] = resin.read_var_in_frame(time_index, var_ID)

                # Replace bottom locally
                nmodif = 0
                for i in range(output_header.nb_nodes):  # iterate over all nodes
                    x, y = output_header.x[i], output_header.y[i]
                    pt = geo.Point(x, y)
                    old_z = var[pos_B, i]

                    found = False
                    # Check if it is inside a zone
                    for j, zone in enumerate(zones):
                        if zone.contains(pt):
                            # Current point is inside zone number j and is between polylines a and b
                            z_int = zone.interpolate(pt)
                            new_z = zone.operator(z_int, old_z)
                            var[pos_B, i] = new_z

                            print("BOTTOM at node {} (zone n°{}) {} to {} (dz={})".format(
                                i + 1, j, operator_str, new_z, new_z - old_z
                            ))

                            nmodif += 1
                            found = True
                            break

                    if not found and args.rescue_distance > 0.0:
                        # Try to rescue some very close nodes
                        for j, zone in enumerate(zones):
                            if zone.polygon.distance(pt) < args.rescue_distance:
                                pt_projected = zone.get_closest_point(pt)

                                # Replace value by a linear interpolation
                                z_int = zone.interpolate(pt_projected)
                                new_z = zone.operator(z_int, old_z)
                                var[pos_B, i] = new_z

                                print("BOTTOM at node {} (zone n°{}, rescued) {} to {} (dz={})".format(
                                    i + 1, j, operator_str, new_z, new_z - old_z
                                ))

                                nmodif += 1
                                break

                resout.write_entire_frame(output_header, time, var)
                print("{} nodes were overwritten".format(nmodif))


if __name__ == '__main__':
    parser = PyTelToolsArgParse(description=__doc__, add_args=['in_slf', 'out_slf'])
    parser.add_argument("in_i3s_paths", help="i3s BlueKenue 3D polyline file", nargs='+')
    parser.add_argument("--operations", help="list of operations (set is used by default)", nargs='+',
                        choices=('set', 'max', 'min'))
    parser.add_argument("--threshold", type=float, help="value from which to interpolate")
    parser.add_argument('--attr_to_shift_z', help='attribute to shift z')
    parser.add_argument('--rescue_distance', default=0.1,
                        help='distance buffer (in m) to match nodes close to a zone nut not inside')

    parser.add_group_general(['force', 'verbose'])
    args = parser.parse_args()

    bottom(args)
