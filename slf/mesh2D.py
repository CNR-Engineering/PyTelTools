"""!
Representation of the 2D mesh in a 2D Serafin file.
"""

import numpy as np
import shapely.geometry as geom
from rtree.index import Index


class Mesh2D:
    """!
    The general representation of mesh in Serafin 2D.
    The basis for interpolation, volume calculations etc.
    """
    def __init__(self, input_header, construct_index=False):
        self.x, self.y = input_header.x[:input_header.nb_nodes_2d], input_header.y[:input_header.nb_nodes_2d]
        self.ikle = input_header.ikle_2d - 1  # back to 0-based indexing
        self.triangles = {}
        self.nb_points = self.x.shape[0]
        self.nb_triangles = self.ikle.shape[0]
        self.points = np.stack([self.x, self.y], axis=1)
        if not construct_index:
            self.index = Index()
        else:
            self._construct_index()

    def _construct_index(self):
        """!
        Separate the index construction from the constructor, allowing a GUI override
        """
        self.index = Index()
        for i, j, k in self.ikle:
            t = geom.Polygon([self.points[i], self.points[j], self.points[k]])
            self.triangles[i, j, k] = t
            self.index.insert(i, t.bounds, obj=(i, j, k))

    def get_intersecting_elements(self, bounding_box):
        """!
        @brief Return the triangles in the mesh intersecting the bounding box
        @param <tuple> bounding_box: (left, bottom, right, top) of a 2d geometrical object
        @return <list of tuple>: The list of triangles (i,j,k) intersecting the bounding box
        """
        return list(self.index.intersection(bounding_box, objects='raw'))



