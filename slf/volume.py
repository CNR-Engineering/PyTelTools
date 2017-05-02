"""!
Volume calculations in polygons
"""


import numpy as np
import shapely.geometry as geom
from slf.interpolation import Interpolator
from slf.mesh2D import Mesh2D
from geom import Polyline


class TruncatedTriangularPrisms(Mesh2D):
    """!
    @brief The representation of Mesh2D in Serafin file when the calculating the volume over mesh of some variables

    A truncated triangular prism is a triangular prism with non-parallel bases.
    Its geometrical properties are entirely determined by the base triangles.

    A prism is constructed, on the top of the base triangle,
    by giving the height of the nodes in the upper triangle, called the values of the triangle.

    A prism can be intersected with a 2D polygon. In this case, only the base triangle is considered.

    The volume of the prism is always equal to the surface area of the base triangle times
    the interpolated value of the centroid of the upper triangle.
    When intersected with a 2D polygon, the volume of the intersection is equal to
    the surface area of the intersection (polygon or multipolygon) times
    the interpolated value of the centroid of the intersection.
    """
    def __init__(self, input_stream):
        super().__init__(input_stream)

    def polygon_intersection_strict(self, polygon):
        """!
        @brief Return the weight carried by the triangle nodes entirely contained in polygon
        @param <geom.Polyline> polygon: A polygon
        @return <numpy.1D-array>: The weight carried by the triangle nodes
        """
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                weight[[i, j, k]] += t.area
        return weight / 3.0

    def polygon_intersection(self, polygon):
        """!
        @brief Return the weight carried by the triangle nodes entirely contained in polygon and info about boundary triangles
        @param <geom.Polyline> polygon: A polygon
        @return <numpy.1D-array, dict>: The weight carried by the triangle nodes, and the dictionary of tuple (area, centroid value) for boundary triangles
        """
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        triangle_polygon_intersection = {}
        for i, j, k in self.triangles:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                weight[[i, j, k]] += t.area
            else:
                is_intersected, intersection = polygon.polygon_intersection(t)
                if is_intersected:
                    centroid = intersection.centroid
                    interpolator = Interpolator(t).get_interpolator_at(centroid.x, centroid.y)
                    triangle_polygon_intersection[i, j, k] = (intersection.area, interpolator)
        return weight / 3.0, triangle_polygon_intersection

    def polygon_intersection_all(self, polygon):
        """!
        @brief Return all triangles entirely contained in polygon and all boundary triangle-polygon intersections
        @param <geom.Polyline> polygon: A polygon
        @return <dict, dict>: The dictionaries of all triangles contained in polygon, and of tuples (base triangle, intersection) for boundary triangles
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

    @staticmethod
    def extra_volume_in_polygon(triangle_polygon_intersection, variable):
        """!
        @brief Return the total volume in all triangle-polygon intersections
        @param <dict> triangle_polygon_intersection: All triangle-polygon intersections defined by boundary triangles
        @param <numpy.1D-array> variable: The values of the variable on all nodes
        @return <numpy.float>: The total volume in all triangle-polygon intersections
        """
        volume = 0
        for i, j, k in triangle_polygon_intersection:
            area, interpolator = triangle_polygon_intersection[i, j, k]
            volume += area * interpolator.dot(variable[[i, j, k]])
        return volume

    @staticmethod
    def superior_prism_volume(triangle, values):
        """!
        @brief Return the volume in the half-space z > 0 of the prism with the given base triangle and values
        @param <shapely.geometry.Polygon> triangle: A triangle entirely contained in the polygon
        @param <numpy.1D-array> values: The values of the variable on the three nodes of the triangle
        @return <numpy.float>: The volume of the prism in the half-space z > 0
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

    @staticmethod
    def superior_prism_volume_in_intersection(triangle, polygon, intersection, values):
        """!
        @brief Return the volume of the prism in the half-space z > 0 and inside the polygon
        @param <shapely.geometry.Polygon> triangle: The base triangle
        @param <shapely.geometry.Polygon> polygon: The volume-defining polygon
        @param <shapely.geometry.Polygon or shapely.geometry.Multipolygon> intersection: The intersection between triangle and polygon
        @param <numpy.1D-array> values: The values of the variable on the three nodes of the triangle
        @return <numpy.float>: The volume of the prism in the half-space z > 0 and inside the polygon
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
                centroid = intersection.centroid
                height = Interpolator(new_triangle).get_interpolator_at(centroid.x, centroid.y).dot(np.array([z_top, 0, 0]))
                return intersection.area * height
        else:  # negative trahedron
            (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
            bottom_middle_intersect = (z_middle * bottom - z_bottom * middle) / (z_middle - z_bottom)
            bottom_top_intersect = (z_top * bottom - z_bottom * top) / (z_top - z_bottom)
            new_triangle = geom.Polygon([bottom, bottom_middle_intersect, bottom_top_intersect])
            volume_negative = new_triangle.area * z_bottom / 3.0
            centroid = intersection.centroid
            interpolator = Interpolator(new_triangle)
            new_values = np.array([z_bottom, 0, 0])
            height = interpolator.get_interpolator_at(centroid.x, centroid.y).dot(new_values)
            intersected_volume = intersection.area * height  # volume net intersected

            if polygon.contains(new_triangle):
                # volume sup = (volume net intersected) - (volume negative tetrahedron)
                return intersected_volume - volume_negative
            else:
                # volume sup = (volume net intersected)
                #              - (volume negative tetrahedron - volume in tetrahedron but not in polygon)
                is_intersected, new_difference = Polyline.Polyline.triangle_difference(new_triangle, polygon)
                if not is_intersected:
                    return 0
                centroid = new_difference.centroid
                height = interpolator.get_interpolator_at(centroid.x, centroid.y).dot(new_values)
                volume_tetrahedron_not_in_polygon = new_difference.area * height
                return intersected_volume - (volume_negative - volume_tetrahedron_not_in_polygon)


def volume_net_strict(var_ID, input_stream, output_stream, polynames, polygons, time_sampling_frequency=1):
    base = TruncatedTriangularPrisms(input_stream)
    weights = []
    for poly in polygons:
        weights.append(base.polygon_intersection_strict(poly))

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
    base_triangles = TruncatedTriangularPrisms(input_stream)
    weights = []

    for poly in polygons:
        weight, triangle_polygon_intersection = base_triangles.polygon_intersection(poly)
        weights.append((weight, triangle_polygon_intersection))

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
            weight, triangle_polygon_intersection = weights[j]
            volume_inside = weight.dot(variable)
            volume_extra = TruncatedTriangularPrisms.extra_volume_in_polygon(triangle_polygon_intersection, variable)
            output_stream.write(';')
            output_stream.write(str(volume_inside + volume_extra))
        output_stream.write('\n')


def volume_superior(var_ID, input_stream, output_stream, polynames, polygons, time_sampling_frequency=1):
    base_triangles = TruncatedTriangularPrisms(input_stream)
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
                volume_total += TruncatedTriangularPrisms.superior_prism_volume(t, variable[[a, b, c]])
            for a, b, c in extra:
                triangle, intersection = extra[a, b, c]
                volume_total += TruncatedTriangularPrisms.superior_prism_volume_in_intersection(triangle, polygons[j],
                                                                                                intersection,
                                                                                                variable[[a, b, c]])
            output_stream.write(';')
            output_stream.write(str(volume_total))

        output_stream.write('\n')



