"""!
The general representation of mesh in serafin 2D
basis for interpolation, volume calculations etc.
"""

import numpy as np
import shapely.geometry as geom


class Mesh2D:
    def __init__(self, input_stream):
        x, y = input_stream.header.x, input_stream.header.y
        ikle = input_stream.header.ikle_2d - 1  # back to 0-based indexing
        self.triangles = {}
        self.nb_points = x.shape[0]
        self.points = np.stack([x, y], axis=1)

        for i, j, k in ikle:
            self.triangles[i, j, k] = geom.Polygon([self.points[i], self.points[j], self.points[k]])



