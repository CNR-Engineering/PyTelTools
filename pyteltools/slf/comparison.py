"""!
Comparison between two Serafin files with identical meshes
"""

import numpy as np

from pyteltools.slf.interpolation import Interpolator
from pyteltools.slf.volume import TruncatedTriangularPrisms


class ReferenceMesh(TruncatedTriangularPrisms):
    """!
    @brief Wrapper for computing error measures when comparing a test mesh to a reference mesh

    The test mesh should have identical geometry to the reference mesh. Only the values are different.
    The comparison region can be the whole mesh or the interior of a polygon.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.area = {}
        self.point_weight = []
        self.inverse_total_area = 1

        self.nb_triangles_inside = 0
        self.inside_polygon = False
        self.polygon = None
        self.triangle_polygon_intersection = {}

    def add_polygon(self, polygon):
        """!
        @brief Initialize the weight on all points of the mesh depending on the comparison region
        @param polygon <geom.geometry.Polygon>: A polygon defining the comparison region or None if it is the whole mesh
        """
        self.area = {}
        self.point_weight = np.zeros((self.nb_points,), dtype=np.float64)

        if polygon is None:  # entire mesh
            self.inside_polygon = False
            self.triangle_polygon_intersection = {}
            self.nb_triangles_inside = self.nb_triangles
            total_area = 0
            for (i, j, k), t in self.triangles.items():
                area = t.area
                self.area[i, j, k] = area
                total_area += area
                self.point_weight[[i, j, k]] += area
        else:
            self.inside_polygon = True
            self.polygon = polygon
            self.nb_triangles_inside = 0

            potential_elements = self.get_intersecting_elements(polygon.bounds())
            self.point_weight = np.zeros((self.nb_points,), dtype=np.float64)
            self.triangle_polygon_intersection = {}
            total_area = 0
            for i, j, k in potential_elements:
                t = self.triangles[i, j, k]
                if polygon.contains(t):
                    self.nb_triangles_inside += 1
                    area = t.area
                    total_area += area
                    self.point_weight[[i, j, k]] += area
                    self.area[i, j, k] = area
                else:
                    is_intersected, intersection = polygon.polygon_intersection(t)
                    if is_intersected:
                        self.nb_triangles_inside += 1
                        area = intersection.area
                        total_area += area
                        centroid = intersection.centroid
                        interpolator = Interpolator(t).get_interpolator_at(centroid.x, centroid.y)
                        self.triangle_polygon_intersection[i, j, k] = (area, interpolator)
        self.point_weight /= 3.0
        self.inverse_total_area = 1 / total_area

    def mean_signed_deviation(self, values):
        """!
        @brief Compute the mean signed deviation between two meshes
        @param values <numpy.1D-array>: The difference between the test mesh and the reference mesh
        @return <float>: The value of the mean signed deviation
        """
        if not self.inside_polygon:
            return self.point_weight.dot(values) * self.inverse_total_area
        else:
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   values)
            return (volume_boundary + self.point_weight.dot(values)) * self.inverse_total_area

    def mean_absolute_deviation(self, values):
        """!
        @brief Compute the mean absolute deviation between two meshes
        @param values <numpy.1D-array>: The difference between the test mesh and the reference mesh
        @return <float>: The value of the mean absolute deviation
        """
        if not self.inside_polygon:
            return self.point_weight.dot(np.abs(values)) * self.inverse_total_area
        else:
            abs_values = np.abs(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   abs_values)
            return (volume_boundary + self.point_weight.dot(abs_values)) * self.inverse_total_area

    def root_mean_square_deviation(self, values):
        """!
        @brief Compute the root mean square deviation between two meshes
        @param values <numpy.1D-array>: The difference between the test mesh and the reference mesh
        @return <float>: The value of the root mean square deviation
        """
        if not self.inside_polygon:
            return np.sqrt(self.point_weight.dot(np.square(values)) * self.inverse_total_area)
        else:
            squared_values = np.square(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   squared_values)
            return np.sqrt((volume_boundary + self.point_weight.dot(squared_values)) * self.inverse_total_area)

    def element_wise_signed_deviation(self, values):
        """!
        @brief Compute the element wise signed deviation (signed deviation distribution) between two meshes
        @param values <numpy.1D-array>: The difference between the test mesh and the reference mesh
        @return <dict>: The value of the signed deviation for every triangles in the comparison area
        """
        ewsd = {}
        for i, j, k in self.area:
            ewsd[i, j, k] = sum(values[[i, j, k]]) * self.area[i, j, k] / 3.0 * self.nb_triangles_inside \
                            * self.inverse_total_area
        if self.inside_polygon:
            for i, j, k in self.triangle_polygon_intersection:
                area, interpolator = self.triangle_polygon_intersection[i, j, k]
                ewsd[i, j, k] = interpolator.dot(values[[i, j, k]]) * area * self.nb_triangles_inside \
                                * self.inverse_total_area
        return ewsd

    def quadratic_volume(self, values):
        """!
        @brief (Used in BSS calculations) Compute the quadratic volume between two meshes
        @param values <numpy.1D-array>: The difference between the test mesh and the reference mesh
        @return <float>: The value of the quadratic volume
        """
        if not self.inside_polygon:
            return self.point_weight.dot(np.square(values))
        else:
            squared_values = np.square(values)
            volume_boundary = TruncatedTriangularPrisms.boundary_volume_in_polygon(self.triangle_polygon_intersection,
                                                                                   squared_values)
            return self.point_weight.dot(squared_values) + volume_boundary
