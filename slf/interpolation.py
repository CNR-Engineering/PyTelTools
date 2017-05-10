"""!
Barycentric interpolation in triangles

"""

import numpy as np


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

    def get_interpolator_at(self, x, y):
        return (Interpolator.VEC0 * self.norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) / self.norm_z

    def is_in_triangle(self, x, y):
        coord = (Interpolator.VEC0 * self.norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) / self.norm_z
        return np.all(coord >= 0) and np.all(coord <= 1)


