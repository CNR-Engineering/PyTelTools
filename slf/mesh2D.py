"""!
Representation of the 2D mesh in a 2D Serafin file.
"""

import numpy as np
import shapely.geometry as geom


class Mesh2D:
    """!
    The general representation of mesh in serafin 2D. The basis for interpolation, volume calculations etc.
    """
    def __init__(self, input_header):
        self.x, self.y = input_header.x, input_header.y
        self.ikle = input_header.ikle_2d - 1  # back to 0-based indexing
        self.triangles = {}
        self.nb_points = self.x.shape[0]
        self.nb_triangles = self.ikle.shape[0]
        self.points = np.stack([self.x, self.y], axis=1)

        for i, j, k in self.ikle:
            self.triangles[i, j, k] = geom.Polygon([self.points[i], self.points[j], self.points[k]])






