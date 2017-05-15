"""!
Comparison between two .slf files
"""

import numpy as np
from slf.interpolation import  Interpolator
from slf.volume import TruncatedTriangularPrisms


class ReferenceMesh(TruncatedTriangularPrisms):
    """!
    Compute different error measures when comparing a test mesh to a reference mesh
    """
    def __init__(self, input_header):
        super().__init__(input_header)
        self.area = {}
        self.point_weight = None
        self.inverse_total_area = None

        self.inside_polygon = False
        self.triangle_polygon_intersection = {}

    def add_polygon(self, polygon):
        self.area = {}
        self.point_weight = np.zeros((self.nb_points,), dtype=np.float64)

        if polygon is None:  # entire mesh
            self.inside_polygon = False
            self.triangle_polygon_intersection = {}

            total_area = 0
            for i, j, k in self.triangles:
                area = self.triangles[i, j, k].area
                self.area[i, j, k] = area
                total_area += area
                self.point_weight[[i, j, k]] += area
            self.point_weight /= 3.0
            self.inverse_total_area = 1 / total_area
        else:
            self.inside_polygon = True

            self.point_weight = np.zeros((self.nb_points,), dtype=np.float64)
            self.triangle_polygon_intersection = {}
            total_area = 0
            for i, j, k in self.triangles:
                t = self.triangles[i, j, k]
                if polygon.contains(t):
                    area = t.area
                    total_area += area
                    self.point_weight[[i, j, k]] += area
                    self.area[i, j, k] = area
                else:
                    is_intersected, intersection = polygon.polygon_intersection(t)
                    if is_intersected:
                        area = intersection.area
                        total_area += area
                        centroid = intersection.centroid
                        interpolator = Interpolator(t).get_interpolator_at(centroid.x, centroid.y)
                        self.triangle_polygon_intersection[i, j, k] = (area, interpolator)
            self.point_weight /= 3.0
            self.inverse_total_area = 1 / total_area

    def mean_signed_deviation(self, values):
        if not self.inside_polygon:
            return self.point_weight.dot(values) * self.inverse_total_area
        else:
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   values)
            return (volume_boundary + self.point_weight.dot(values)) * self.inverse_total_area

    def mean_absolute_deviation(self, values):
        if not self.inside_polygon:
            return self.point_weight.dot(np.abs(values)) * self.inverse_total_area
        else:
            abs_values = np.abs(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   abs_values)
            return (volume_boundary + self.point_weight.dot(abs_values)) * self.inverse_total_area

    def root_mean_square_deviation(self, values):
        if not self.inside_polygon:
            return np.sqrt(self.point_weight.dot(np.square(values)) * self.inverse_total_area)
        else:
            squared_values = np.square(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   squared_values)
            return np.sqrt((volume_boundary + self.point_weight.dot(squared_values)) * self.inverse_total_area)

    def element_wise_signed_deviation(self, values):
        ewsd = {}
        for i, j, k in self.area:
            ewsd[i, j, k] = sum(values[[i, j, k]]) * self.area[i, j, k] / 3.0 * self.nb_triangles * self.inverse_total_area
        if self.inside_polygon:
            for i, j, k in self.triangle_polygon_intersection:
                area, interpolator = self.triangle_polygon_intersection[i, j, k]
                ewsd[i, j, k] = interpolator.dot(values[[i, j, k]]) * area * self.nb_triangles * self.inverse_total_area
        return ewsd

