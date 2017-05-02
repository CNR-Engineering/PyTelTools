"""!
Volume calculations in polygons

"""


import numpy as np
import shapely.geometry as geom
from slf.interpolation import Interpolator
from geom import Polyline



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
                weight[[i, j, k]] += t.area
        return weight / 3.0

    def polygon_intersection(self, polygon):
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        extra = {}
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                weight[[i, j, k]] += t.area
            else:
                is_intersected, intersection = polygon.polygon_intersection(t)
                if is_intersected:
                    extra[i, j, k] = []
                    for poly in intersection:
                        centroid = poly.centroid
                        interpolator = Interpolator(t).get_interpolator_at(centroid.x, centroid.y)
                        extra[i, j, k].append((poly.area, interpolator))
        return weight / 3.0, extra

    def extra_volume(self, extra, variable):
        volume = 0
        for i, j, k in extra:
            for area, interpolator in extra[i, j, k]:
                volume += area * interpolator.dot(variable[[i, j, k]])
        return volume

    def polygon_intersection_all(self, polygon):
        """!
        should be used when computing positive volume
        """
        triangles = {}
        extra = {}
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                triangles[i, j, k] = t
            else:
                is_intersected, intersection = polygon.polygon_intersection(t)
                if is_intersected:
                    extra[i, j, k] = (t, intersection)
        return triangles, extra


def triangle_superior_volume(triangle, values):
    """
    return the volume in the half-space z > 0
    """
    p1, p2, p3 = tuple(map(np.array, list(triangle.exterior.coords)[:-1]))

    # eliminate special cases
    if min(values) >= 0:
        return triangle.area * sum(values) / 3.0
    elif max(values) <= 0:
        return 0
    # remaining cases: triangle crosses the plane z = 0
    nb_points_superior = sum(values > 0)
    if nb_points_superior == 1:  # positive tetrahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        top_middle_intersect = (z_top * middle - z_middle * top) / (z_top - z_middle)
        top_bottom_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        return geom.Polygon([top, top_middle_intersect, top_bottom_intersect]).area * z_top / 3.0
    else:  # negative tetrahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        bottom_middle_intersect = (z_middle * bottom - z_bottom * middle) / (z_middle - z_bottom)
        bottom_top_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        volume_total = triangle.area * sum(values) / 3.0
        volume_negative = geom.Polygon([bottom, bottom_middle_intersect, bottom_top_intersect]).area * z_bottom / 3.0
        return volume_total - volume_negative


def triangle_superior_extra_volume(triangle, polygon, intersection, values):
    """
    return the volume in the half-space z > 0
    """
    p1, p2, p3 = tuple(map(np.array, list(triangle.exterior.coords)[:-1]))

    # eliminate special cases
    if min(values) >= 0:
        return triangle.area * sum(values) / 3.0
    elif max(values) <= 0:
        return 0
    # remaining cases: triangle crosses the plane z = 0
    nb_points_superior = sum(values > 0)
    if nb_points_superior == 1:  # positive tetrahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        top_middle_intersect = (z_top * middle - z_middle * top) / (z_top - z_middle)
        top_bottom_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        new_triangle = geom.Polygon([top, top_middle_intersect, top_bottom_intersect])
        if polygon.contains(new_triangle):
            return new_triangle.area * z_top / 3.0
        else:
            is_intersected, intersection = polygon.polygon_intersection(new_triangle)
            if not is_intersected:
                return 0
            intersected_volume = 0
            for poly in intersection:
                centroid = poly.centroid
                interpolator = Interpolator(new_triangle).get_interpolator_at(centroid.x, centroid.y)
                intersected_volume += poly.area * interpolator.dot(np.array([z_top, 0, 0]))
            return intersected_volume
    else:  # negative trahedron
        (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
        bottom_middle_intersect = (z_middle * bottom - z_bottom * middle) / (z_middle - z_bottom)
        bottom_top_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
        new_triangle = geom.Polygon([bottom, bottom_middle_intersect, bottom_top_intersect])
        volume_negative = new_triangle.area * z_bottom / 3.0
        intersected_volume = 0  # volume net intersected
        for poly in intersection:
            centroid = poly.centroid
            interpolator = Interpolator(new_triangle).get_interpolator_at(centroid.x, centroid.y)
            intersected_volume += poly.area * interpolator.dot(np.array([z_bottom, 0, 0]))

        if polygon.contains(new_triangle):
            # volume sup = (volume net intersected) - (volume negative tetrahedron)
            return intersected_volume - volume_negative
        else:
            # volume sup = (volume net intersected)
            #              - (volume negative tetrahedron - volume in tetrahedron but not in polygon)
            is_intersected, new_difference = Polyline.Polyline.triangle_difference(new_triangle, polygon)
            if not is_intersected:
                return 0
            volume_tetrahedron_not_in_polygon = 0
            for diff_polygon in new_difference:
                centroid = diff_polygon.centroid
                interpolator = Interpolator(new_triangle).get_interpolator_at(centroid.x, centroid.y)
                volume_tetrahedron_not_in_polygon += diff_polygon.area * interpolator.dot(np.array([z_bottom, 0, 0]))
            return intersected_volume - (volume_negative - volume_tetrahedron_not_in_polygon)


def volume_net_strict(var_ID, input_stream, output_stream, polynames, polygons, time_sampling_frequency=1):
    x = input_stream.header.x
    y = input_stream.header.y
    ikle = input_stream.header.ikle_2d - 1  # back to 0-based indexing

    weights = []
    for poly in polygons:
        base = Triangles2D(x, y, ikle)
        weights.append(base.polygon_intersection_net(poly))

    # write the first line
    output_stream.write('time')
    for name in polynames:
        output_stream.write(';')
        output_stream.write(name)
    output_stream.write('\n')

    # write the volumes, one frame per line
    for i in range(0, len(input_stream.time), time_sampling_frequency):
        i_time = input_stream.time[i]
        output_stream.write(str(i_time))

        variable = input_stream.read_var_in_frame(i, var_ID)
        for j in range(len(polygons)):
            output_stream.write(';')
            weight = weights[j]
            output_stream.write(str(weight.dot(variable)))
        output_stream.write('\n')



def volume_net(var_ID, input_stream, output_stream, polynames, polygons, time_sampling_frequency=1):
    x = input_stream.header.x
    y = input_stream.header.y
    ikle = input_stream.header.ikle_2d - 1  # back to 0-based indexing
    base_triangles = Triangles2D(x, y, ikle)
    weights = []

    for poly in polygons:
        weight, extra = base_triangles.polygon_intersection(poly)
        weights.append((weight, extra))

    # write the first line
    output_stream.write('time')
    for name in polynames:
        output_stream.write(';')
        output_stream.write(name)
    output_stream.write('\n')

    # write the volumes, one frame per line
    for i in range(0, len(input_stream.time), time_sampling_frequency):
        i_time = input_stream.time[i]
        output_stream.write(str(i_time))

        variable = input_stream.read_var_in_frame(i, var_ID)
        for j in range(len(polygons)):
            weight, extra = weights[j]
            volume_inside = weight.dot(variable)
            volume_extra = base_triangles.extra_volume(extra, variable)
            output_stream.write(';')
            output_stream.write(str(volume_inside + volume_extra))
        output_stream.write('\n')


def volume_superior(var_ID, input_stream, output_stream, polynames, polygons, time_sampling_frequency=1):
    x = input_stream.header.x
    y = input_stream.header.y
    ikle = input_stream.header.ikle_2d - 1  # back to 0-based indexing
    base_triangles = Triangles2D(x, y, ikle)
    triangles_in_polygon = []

    for poly in polygons:
        triangles_in_polygon.append(base_triangles.polygon_intersection_all(poly))

    # write the first line
    output_stream.write('time')
    for name in polynames:
        output_stream.write(';')
        output_stream.write(name)
    output_stream.write('\n')

    # write the volumes, one frame per line
    for i in range(0, len(input_stream.time), time_sampling_frequency):
        i_time = input_stream.time[i]
        output_stream.write(str(i_time))

        variable = input_stream.read_var_in_frame(i, var_ID)
        for j in range(len(polygons)):
            triangles, extra = triangles_in_polygon[j]
            volume_total = 0
            for a, b, c in triangles:
                t = triangles[a, b, c]
                volume_total += triangle_superior_volume(t, variable[[a, b, c]])
            for a, b, c in extra:
                triangle, intersection = extra[a, b, c]
                volume_total += triangle_superior_extra_volume(triangle, polygons[j],
                                                               intersection, variable[[a, b, c]])
            output_stream.write(';')
            output_stream.write(str(volume_total))
        output_stream.write('\n')



