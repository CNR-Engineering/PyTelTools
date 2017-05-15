"""!
Comparison between two .slf files
"""

import numpy as np
from slf.volume import TruncatedTriangularPrisms


class ReferenceMesh(TruncatedTriangularPrisms):
    """!
    Compute different error measures when comparing a test mesh to a reference mesh
    """
    def __init__(self, input_header):
        super().__init__(input_header)
        self.area = {}
        self.point_weight = np.zeros((self.nb_points,), dtype=np.float64)

        total_area = 0
        for i, j, k in self.triangles:
            area = self.triangles[i, j, k].area
            self.area[i, j, k] = area
            total_area += area
            self.point_weight[[i, j, k]] += area
        self.point_weight /= 3.0

        self.inverse_total_area = 1 / total_area

    def mean_signed_deviation(self, values):
        return self.point_weight.dot(values) * self.inverse_total_area

    def mean_absolute_deviation(self, values):
        return self.point_weight.dot(np.abs(values)) * self.inverse_total_area

    def root_mean_square_deviation(self, values):
        return np.sqrt(self.point_weight.dot(np.square(values)) * self.inverse_total_area)