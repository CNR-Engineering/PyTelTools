"""!
Barycentric interpolation in triangles

"""

import numpy as np
from slf.mesh2D import Mesh2D


class Interpolator:
    VEC0 = np.array([1, 0, 0])

    def __init__(self, triangle):
        p1, p2, p3 = tuple(map(list, list(triangle.exterior.coords)[:-1]))
        self.x1, self.y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        self.vec_x = np.array([x2-x3, x3-self.x1, self.x1-x2])
        self.vec_y = np.array([y2-y3, y3-self.y1, self.y1-y2])
        self.norm_z = (x2-self.x1) * (y3-self.y1) - (y2-self.y1) * (x3-self.x1)
        self.inv_norm_z = 1 / self.norm_z

    def get_interpolator_at(self, x, y):
        return (Interpolator.VEC0 * self.norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) * self.inv_norm_z

    def is_in_triangle(self, x, y):
        coord = (Interpolator.VEC0 * self.norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) * self.inv_norm_z
        return np.all(coord >= 0) and np.all(coord <= 1), coord


class MeshInterpolator(Mesh2D):
    def __init__(self, input_header, construct_index):
        super().__init__(input_header, construct_index)

    def get_point_interpolators(self, points):
        nb_points = len(points)
        is_inside = [False] * nb_points
        point_interpolators = [None] * nb_points

        for index, (x, y) in enumerate(points):
            potential_element = self.get_intersecting_elements((x, y, x, y))
            if not potential_element:
                continue
            is_inside[index] = True
            i, j, k = potential_element[0]
            t = self.triangles[i, j, k]
            point_interpolators[index] = ((i, j, k), Interpolator(t).get_interpolator_at(x, y))

        return is_inside, point_interpolators


