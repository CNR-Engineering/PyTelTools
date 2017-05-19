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
    def __init__(self, input_header):
        super().__init__(input_header)
        self._construct_triangles()

    def get_point_interpolators(self, points):
        nb_points = len(points)
        is_inside = [False] * nb_points
        point_interpolators = [None] * nb_points
        nb_inside = 0
        for (i, j, k), t in self.triangles.items():
            t_interpolator = Interpolator(t)
            for p_index, (x, y) in enumerate(points):
                if is_inside[p_index]:
                    continue
                p_is_inside, p_interpolator = t_interpolator.is_in_triangle(x, y)
                if p_is_inside:
                    is_inside[p_index] = True
                    nb_inside += 1
                    point_interpolators[p_index] = ((i, j, k), p_interpolator)
            if nb_inside == nb_points:
                break
        return is_inside, point_interpolators


