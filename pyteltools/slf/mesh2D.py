"""!
Representation of the 2D mesh in a 2D Serafin file.
"""

import numpy as np
from rtree.index import Index
from shapely.geometry import Polygon


class Mesh2D:
    """!
    The general representation of mesh in Serafin 2D.
    The basis for interpolation, volume calculations etc.
    """
    def __init__(self, input_header, construct_index=False, iter_pbar=lambda x: x):
        """!
        @param input_header <slf.Serafin.SerafinHeader>: input Serafin header
        @param construct_index <bool>: perform the index construction
        @param iter_pbar: iterable progress bar
        """
        self.x, self.y = input_header.x[:input_header.nb_nodes_2d], input_header.y[:input_header.nb_nodes_2d]
        self.ikle = input_header.ikle_2d - 1  # back to 0-based indexing
        self.triangles = {}
        self.nb_points = self.x.shape[0]
        self.nb_triangles = self.ikle.shape[0]
        self.points = np.stack([self.x, self.y], axis=1)
        if not construct_index:
            self.index = Index()
        else:
            self._construct_index(iter_pbar)

    def _construct_index(self, iter_pbar):
        """!
        Separate the index construction from the constructor, allowing a GUI override
        @param iter_pbar: iterable progress bar
        """
        self.index = Index()
        for i, j, k in iter_pbar(self.ikle, unit='elements'):
            t = Polygon([self.points[i], self.points[j], self.points[k]])
            self.triangles[i, j, k] = t
            self.index.insert(i, t.bounds, obj=(i, j, k))

    def get_intersecting_elements(self, bounding_box):
        """!
        @brief Return the triangles in the mesh intersecting the bounding box
        @param bounding_box <tuple>: (left, bottom, right, top) of a 2d geometrical object
        @return <[tuple]>: The list of triangles (i,j,k) intersecting the bounding box
           Beware: The returned list is not sorted
        """
        return list(self.index.intersection(bounding_box, objects='raw'))



