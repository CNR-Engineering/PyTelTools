import numpy as np


def direction_ratio(point):
    return lambda other: [other[0] - point[0],
                          other[1] - point[1],
                          other[2] - point[2]]


class Plane3D:
    def __init__(self, p1, p2, p3):
        self.p1 = p1
        direction = direction_ratio(self.p1)
        self.x, self.y, self.z = self.p1
        self.a, self.b, self.c = np.cross(direction(p2), direction(p3))  # normal vector

    def projection_along_z(self, x, y):
        if self.c == 0:
            return self.z
        return self.z - (self.a * (x - self.x) + self.b * (y - self.y)) / self.c


def interpolate_on_triangle(triangle_2d, values, point_in_plane):
    p1, p2, p3 = tuple(map(list, list(triangle_2d.exterior.coords)[:-1]))
    p1.append(values[0])
    p2.append(values[1])
    p3.append(values[2])
    plane = Plane3D(p1, p2, p3)
    return plane.projection_along_z(point_in_plane.x, point_in_plane.y)




