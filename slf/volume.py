"""!
Volume calculations in polygons
"""


import numpy as np
import shapely.geometry as geom
from slf.interpolation import Interpolator
from slf.mesh2D import Mesh2D
from geom import Geometry


class TruncatedTriangularPrisms(Mesh2D):
    """!
    @brief The representation of Mesh2D in Serafin file when one computes the volume inside polygons of some variables

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
    def __init__(self, input_header, construct_index):
        super().__init__(input_header, construct_index)

    def polygon_intersection_strict(self, polygon):
        """!
        @brief Return the weight carried by the triangle nodes entirely contained in polygon
        @param <geom.Polyline> polygon: A polygon
        @return <numpy.1D-array>: The weight carried by the triangle nodes
        """
        potential_elements = self.get_intersecting_elements(polygon.bounds())
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        for i, j, k in potential_elements:
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
        potential_elements = self.get_intersecting_elements(polygon.bounds())
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        triangle_polygon_intersection = {}
        for i, j, k in potential_elements:
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
        potential_elements = self.get_intersecting_elements(polygon.bounds())
        weight = np.zeros((self.nb_points,), dtype=np.float64)
        triangles = {}
        triangle_polygon_net_intersection = {}
        triangle_polygon_intersection = {}
        for i, j, k in potential_elements:
            t = self.triangles[i, j, k]
            if polygon.contains(t):
                area = t.area
                vertices = tuple(map(np.array, list(t.exterior.coords)[:-1]))
                triangles[i, j, k] = (vertices, area)
                weight[[i, j, k]] += area
            else:
                is_intersected, intersection = polygon.polygon_intersection(t)
                if is_intersected:
                    vertices = tuple(map(np.array, list(t.exterior.coords)[:-1]))
                    area = t.area
                    centroid = intersection.centroid
                    interpolator = Interpolator(t).get_interpolator_at(centroid.x, centroid.y)
                    triangle_polygon_net_intersection[i, j, k] = (intersection.area, interpolator)
                    triangle_polygon_intersection[i, j, k] = (vertices, area, intersection)
        return weight / 3.0, triangle_polygon_net_intersection, triangles, triangle_polygon_intersection

    @staticmethod
    def boundary_volume_in_polygon(triangle_polygon_intersection, variable):
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
    def superior_prism_volume(vertices, area, values):
        """!
        @brief Return the volume in the half-space z > 0 of the prism with the given base triangle and values
        @param <list> vertices: The coordinates of the three vertices defining the base triangle
        @param <float> area: The area of the base triangle
        @param <numpy.1D-array> values: The values of the variable on the three nodes of the triangle
        @return <float>: The volume of the prism in the half-space z > 0
        """
        # eliminate special cases
        if min(values) >= 0:
            return area * sum(values) / 3.0
        elif max(values) <= 0:
            return 0

        p1, p2, p3 = vertices
        # remaining cases: triangle crosses the plane z = 0
        nb_points_superior = sum(values > 0)
        if nb_points_superior == 1:  # positive tetrahedron
            (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
            return area * z_top ** 3 / 3 / (z_top - z_middle) / (z_top - z_bottom)
        else:  # negative tetrahedron
            (z_bottom, _, bottom), (z_middle, _, middle), (z_top, _, top) = sorted(zip(values, [1, 2, 3], [p1, p2, p3]))
            volume_total = area * sum(values) / 3.0
            volume_negative = area * z_bottom ** 3 / 3 / (z_top - z_bottom) / (z_middle - z_bottom)
            return volume_total - volume_negative

    @staticmethod
    def superior_prism_volume_in_intersection(polygon, vertices, area, intersection, values):
        """!
        @brief Return the volume of the prism in the half-space z > 0 and inside the polygon
        @param <shapely.geometry.Polygon> polygon: The volume-defining polygon
        @param <list> vertices: The coordinates of the three vertices defining the base triangle
        @param <float> area: The area of the base triangle
        @param <numpy.1D-array> values: The values of the variable on the three nodes of the triangle
        @return <float>: The volume of the prism in the half-space z > 0 and inside the polygon
        """
        # eliminate special cases
        if min(values) >= 0:
            return area * sum(values) / 3.0
        elif max(values) <= 0:
            return 0
        p1, p2, p3 = vertices
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
        else:  # negative tetrahedron
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
                is_intersected, new_difference = Geometry.Polyline.triangle_difference(new_triangle, polygon)
                if not is_intersected:
                    return 0
                centroid = new_difference.centroid
                height = interpolator.get_interpolator_at(centroid.x, centroid.y).dot(new_values)
                volume_tetrahedron_not_in_polygon = new_difference.area * height
                return intersected_volume - (volume_negative - volume_tetrahedron_not_in_polygon)


class VolumeCalculator:
    NET_STRICT, NET, POSITIVE = 0, 1, 2
    INIT_VALUE = '+'

    def __init__(self, volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                 time_sampling_frequency):
        self.volume_type = volume_type
        self.input_stream = input_stream
        self.polynames = polynames
        self.polygons = polygons

        self.var_ID = var_ID
        self.second_var_ID = second_var_ID

        self.time_indices = range(0, len(input_stream.time), time_sampling_frequency)

        self.mesh = None
        self.weights = []

    def construct_triangles(self):
        self.mesh = TruncatedTriangularPrisms(self.input_stream.header, True)

    def construct_weights(self):
        if self.volume_type == VolumeCalculator.NET_STRICT:
            for poly in self.polygons:
                self.weights.append(self.mesh.polygon_intersection_strict(poly))
        elif self.volume_type == VolumeCalculator.NET:
            for poly in self.polygons:
                weight, triangle_polygon_intersection = self.mesh.polygon_intersection(poly)
                self.weights.append((weight, triangle_polygon_intersection))
        elif self.volume_type == VolumeCalculator.POSITIVE:
            for poly in self.polygons:
                self.weights.append(self.mesh.polygon_intersection_all(poly))

    def volume_in_frame_in_polygon(self, weight, values, polygon):
        if self.volume_type == VolumeCalculator.NET_STRICT:
            return weight.dot(values)
        elif self.volume_type == VolumeCalculator.NET:
            strict_weight, triangle_polygon_intersection = weight
            volume_inside = strict_weight.dot(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(triangle_polygon_intersection, values)
            return volume_inside + volume_boundary
        else:
            strict_weight, triangle_polygon_net_intersection, triangles, triangle_polygon_intersection = weight
            volume_net = strict_weight.dot(values)
            volume_net += TruncatedTriangularPrisms.boundary_volume_in_polygon(triangle_polygon_net_intersection, values)

            volume_positive = 0
            for a, b, c in triangles:
                vertices, area = triangles[a, b, c]
                volume_positive += TruncatedTriangularPrisms.superior_prism_volume(vertices, area, values[[a, b, c]])
            for a, b, c in triangle_polygon_intersection:
                vertices, area, intersection = triangle_polygon_intersection[a, b, c]
                volume_positive += TruncatedTriangularPrisms.superior_prism_volume_in_intersection(polygon, vertices,
                                                                                                   area, intersection,
                                                                                                   values[[a, b, c]])
            return volume_net, volume_positive, volume_net - volume_positive

    def run(self):
        self.construct_triangles()
        self.construct_weights()
        result = []

        init_values = None
        if self.second_var_ID == VolumeCalculator.INIT_VALUE:
            init_values = self.input_stream.read_var_in_frame(0, self.var_ID)

        for time_index in self.time_indices:
            i_result = [str(self.input_stream.time[time_index])]

            values = self.input_stream.read_var_in_frame(time_index, self.var_ID)
            if self.second_var_ID is not None:
                if self.second_var_ID == VolumeCalculator.INIT_VALUE:
                    values -= init_values
                else:
                    second_values = self.input_stream.read_var_in_frame(time_index, self.second_var_ID)
                    values -= second_values

            for j in range(len(self.polygons)):
                weight = self.weights[j]
                volume = self.volume_in_frame_in_polygon(weight, values, self.polygons[j])
                if self.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append('%.6f' % v)
                else:
                    i_result.append('%.6f' % volume)
            result.append(i_result)
        return result

    def write_csv(self, result, output_stream):
        output_stream.write('time')
        for name in self.polynames:
            output_stream.write(';')
            output_stream.write(name)
            if self.volume_type == VolumeCalculator.POSITIVE:
                output_stream.write(';')
                output_stream.write(name + ' POSITIVE')
                output_stream.write(';')
                output_stream.write(name + ' NEGATIVE')

        output_stream.write('\n')

        for line in result:
            output_stream.write(';'.join(line))
            output_stream.write('\n')






