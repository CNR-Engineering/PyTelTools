import numpy as np
import shapely.geometry as geom
from slf import Serafin
from slf.Interpolation import interpolate_on_triangle
from geom import BlueKenue
import time


class Triangles2D:
    def __init__(self, x, y, ikle):
        self.triangles = {}
        self.nb_points = x.shape[0]
        self.points = np.stack([x, y], axis=1)

        for i, j, k in ikle:
            self.triangles[i, j, k] = geom.Polygon([self.points[i], self.points[j], self.points[k]])

    def polygon_intersection_net(self, polygon):
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                weight[[i, j, k]] += t.area / 3.0
        return weight

    def polygon_intersection(self, polygon):
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        extra = {}
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                weight[[i, j, k]] += t.area / 3.0
            else:
                is_intersected, intersection = polygon.polygon_intersection(t)
                if is_intersected:
                    extra[i, j, k] = intersection
        return weight, extra

    def extra_volume(self, extra, variable):
        volume = 0
        for i, j, k in extra:
            intersection = extra[i, j, k]
            area = intersection.area
            centroid = intersection.centroid
            volume += area * interpolate_on_triangle(self.triangles[i, j, k],
                                                     variable[[i, j, k]], centroid)
        return volume

    def polygon_intersection_all(self, polygon):
        triangles = {}
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                triangles[i, j, k] = t
        return triangles


def triangle_superior_volume(triangle, values):
    """
    return the volume in the half-space z > 0
    """
    p1, p2, p3 = tuple(map(np.array, list(triangle.exterior.coords)[:-1]))

    # eliminate special cases
    nb_points_on_plane = sum(values == 0)
    nb_points_superior = sum(values > 0)
    if nb_points_on_plane == 3:  # triangle lies on the plane
        return 0
    elif nb_points_on_plane == 2:
        if nb_points_superior == 1:  # positive tetrahedron
            return triangle.area * sum(values) / 3.0
        else:  # negative tetrahedron
            return 0
    # remaining cases: 0 or 1 points on the plane
    if nb_points_superior == 3:  # positive prism
        return triangle.area * sum(values) / 3.0
    elif nb_points_superior == 0:  # negative prism
        return 0
    elif nb_points_superior == 1:  # positive tetrahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        top_middle_intersect = (z_top * middle - z_middle * top) / (z_top - z_middle)
        top_bottom_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        return geom.Polygon([top, top_middle_intersect, top_bottom_intersect]).area * z_top / 3.0
    else:  # negative tetrahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        bottom_middle_intersect = (z_middle * bottom - z_bottom * middle) / (z_middle - z_bottom)
        bottom_top_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        volume_total = triangle.area * sum(values) / 3.0
        volume_negative = geom.Polygon([bottom, bottom_middle_intersect, bottom_top_intersect]).area * (-z_bottom) / 3.0
        return volume_total - volume_negative



def volume():
    # with BlueKenue.Read('testdata/mypoly.i2s') as f:
    # with BlueKenue.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\polygones_test_helio.i2s') as f:
    with BlueKenue.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\grosPolygone.i2s') as f:

        f.read_header()
        polygons = []
        names = []
        for poly_name, poly in f:
            names.append(str(poly_name[1]))
            polygons.append(poly)

    # with Serafin.Read('testdata\\test.slf', 'fr') as f:
    with Serafin.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\sis_res_onlyB.slf', 'fr') as f:
        f.read_header()
        f.get_time()

        x = f.header.x
        y = f.header.y
        ikle = f.header.ikle_2d - 1  # back to 0-based indexing

        # ===============  VOLUME NET ==========================
        # weights = []
        # for poly in polygons:
        #     base = Triangles2D(x, y, ikle)
        #     weights.append(base.polygon_intersection_net(poly))
        # with open('testdata/sisVolumeBgros.csv', 'w') as f2:
        #     f2.write('time')
        #     for name in names:
        #             f2.write(';')
        #             f2.write(name)
        #     f2.write('\n')
        #
        #     for i, i_time in enumerate(f.time):
        #         f2.write(str(i_time))
        #
        #         variable = f.read_var_in_frame(i, 'B')
        #         for j in range(len(polygons)):
        #             weight = weights[j]
        #             volume_inside = weight.dot(variable)
        #             f2.write(';')
        #             f2.write(str(volume_inside))
        #         f2.write('\n')


        # ===============  VOLUME WITH EXTRA ==========================
        # weights = []
        # for poly in polygons:
        #     print(poly)
        #     base = Triangles2D(x, y, ikle)
        #     weight, extra = base.polygon_intersection(poly)
        #     weights.append((base, weight, extra))
        # with open('testdata/sisVolumeBextra.csv', 'w') as f2:
        #     f2.write('time')
        #     for name in names:
        #             f2.write(';')
        #             f2.write(name)
        #     f2.write('\n')
        #
        #     for i, i_time in enumerate(f.time):
        #         if i % 100 == 0:
        #             print(i)
        #         f2.write(str(i_time))
        #
        #         variable = f.read_var_in_frame(i, 'B')
        #         for j in range(len(polygons)):
        #             base, weight, extra = weights[j]
        #             volume_inside = weight.dot(variable)
        #             volume_extra = base.extra_volume(extra, variable)
        #             f2.write(';')
        #             f2.write(str(volume_inside + volume_extra))
        #         f2.write('\n')


        # ===============  VOLUME POSITIVE ONLY (SLOW) ==========================
        # tinit = time.time()
        # weights = []
        # polygons = polygons[:1]  # do the first one
        # for poly in polygons:
        #     print(poly)
        #     base = Triangles2D(x, y, ikle)
        #     weights.append(base.polygon_intersection_all(poly))
        #
        # with open('testdata/sisVolumeBsup.csv', 'w') as f2:
        #     f2.write('time')
        #     for name in names:
        #             f2.write(';')
        #             f2.write(name)
        #     f2.write('\n')
        #
        #     for i, i_time in enumerate(f.time):
        #         if i % 100 == 0:
        #             print(i, time.time() - tinit)
        #         f2.write(str(i_time))
        #
        #         variable = -f.read_var_in_frame(i, 'B')
        #         for j in range(len(polygons)):
        #             triangles = weights[j]
        #             volume_total = 0
        #             for a, b, c in triangles:
        #                 t = triangles[a, b, c]
        #                 volume_total += triangle_superior_volume(t, variable[[a, b, c]])
        #             if i % 100 == 0:
        #                 print(volume_total)
        #             f2.write(';')
        #             f2.write(str(volume_total))
        #         f2.write('\n')


# t0 = time.time()
# volume()
# print(time.time() - t0)

