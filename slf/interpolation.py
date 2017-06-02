"""!
Barycentric interpolation in triangles
"""

import numpy as np
from slf.mesh2D import Mesh2D


class Interpolator:
    """!
    Wrapper for calculating the barycentric coordinates of 2d points in a 2d triangle
    """
    def __init__(self, triangle):
        p1, p2, p3 = tuple(map(list, list(triangle.exterior.coords)[:-1]))
        self.x1, self.y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        self.vec_x = np.array([x2-x3, x3-self.x1, self.x1-x2])
        self.vec_y = np.array([y2-y3, y3-self.y1, self.y1-y2])
        norm_z = (x2-self.x1) * (y3-self.y1) - (y2-self.y1) * (x3-self.x1)
        self.vec_norm_z = np.array([norm_z, 0, 0])
        self.inv_norm_z = 1 / norm_z

    def get_interpolator_at(self, x, y):
        """!
        @brief Return the barycentric coordinates of the point (x, y)
        """
        return (self.vec_norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) * self.inv_norm_z

    def is_in_triangle(self, x, y):
        """!
        @brief Return a boolean indicating if the point (x, y) is in the triangle, and its barycentric coordinates
        """
        coord = (self.vec_norm_z + (x-self.x1) * self.vec_y - (y-self.y1) * self.vec_x) * self.inv_norm_z
        return np.all(coord >= 0) and np.all(coord <= 1), coord


class MeshInterpolator(Mesh2D):
    def __init__(self, input_header, construct_index):
        super().__init__(input_header, construct_index)

    def get_point_interpolators(self, points):
        nb_points = len(points)
        is_inside = [False] * nb_points
        point_interpolators = [None] * nb_points

        for index, (x, y) in enumerate(points):
            potential_elements = self.get_intersecting_elements((x, y, x, y))
            if not potential_elements:
                continue
            for i, j, k in potential_elements:
                t = self.triangles[i, j, k]
                is_in, point_interpolator = Interpolator(t).is_in_triangle(x, y)
                if is_in:
                    is_inside[index] = True
                    point_interpolators[index] = ((i, j, k), point_interpolator)
                    break

        return is_inside, point_interpolators

    def get_line_interpolators(self, line):
        intersections = []
        internal_points = []  # line interpolators without intersections

        # record the distance offset before the first intersection point
        offset = 0
        found_intersection = False

        for right, up, segment in line.segments():  # for every segment, sort intersection points
            segment_intersections = []
            potential_elements = self.get_intersecting_elements(segment.bounds())
            for i, j, k in potential_elements:
                t = self.triangles[i, j, k]
                is_intersected, t_intersections = segment.linestring_intersection(t)
                if is_intersected:
                    interpolator = Interpolator(t)
                    for intersection in t_intersections:
                        for x, y in intersection.coords:
                            segment_intersections.append((x, y, (i, j, k), interpolator.get_interpolator_at(x, y)))

            # first sort by y, then sort by x
            if up:
                segment_intersections.sort(key=lambda x: x[1])
            else:
                segment_intersections.sort(key=lambda x: x[1], reverse=True)
            if right:
                segment_intersections.sort()
            else:
                segment_intersections.sort(reverse=True)

            intersections.extend(segment_intersections)
            if not segment_intersections:
                continue

            internal_points.append(segment_intersections[0])
            internal_points.append(segment_intersections[-1])

            if not found_intersection:
                first_point, second_point = list(segment.coords())
                if not segment_intersections:
                    offset += np.linalg.norm(np.array(second_point) - np.array(first_point))
                else:
                    found_intersection = True
                    first_intersection = np.array(segment_intersections[0][:2])
                    offset += np.linalg.norm(first_intersection - np.array(first_point))

        # if the intersection is continuous, every internal point or turning point has at least two duplicates
        prev_x, prev_y = None, None
        duplicates = 0
        to_remove = [False] * len(intersections)
        for i, (x, y, _, __) in enumerate(intersections):
            if i == 0:  # the start and end points are not duplicated
                continue
            if prev_x is None:
                prev_x, prev_y = x, y
                continue
            if x == prev_x and y == prev_y:
                to_remove[i] = True
                duplicates += 1
            else:
                if duplicates == 0:  # no duplicate found, the intersection is discontinuous
                    return [], [], [], []
                duplicates = 0
                prev_x, prev_y = x, y

        intersections = [intersections[i] for i in range(len(intersections)) if not to_remove[i]]

        # trim internal points from 2n+2 to n+1
        if internal_points:
            internal_points = internal_points[0:-1:2] + [internal_points[-1]]

        # compute cumulative distance
        distance = offset
        distances = [offset]
        for i in range(len(intersections)-1):
            first, second = intersections[i+1], intersections[i]
            distance += np.linalg.norm([second[0] - first[0], second[1] - first[1]])
            distances.append(distance)

        distance = offset
        distances_internal = [offset]
        for i in range(len(internal_points)-1):
            first, second = internal_points[i+1], internal_points[i]
            distance += np.linalg.norm([second[0] - first[0], second[1] - first[1]])
            distances_internal.append(distance)

        return intersections, distances, internal_points, distances_internal

