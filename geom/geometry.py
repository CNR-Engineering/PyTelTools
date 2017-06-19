"""!
Geometrical objects
"""

import numpy as np
from shapely.geometry import LineString as OpenPolyline, Polygon as ClosedPolyline, MultiPolygon


class Polyline:
    """!
    @brief Custom (open or closed) polyline class
    """
    def __init__(self, coordinates, attributes=None, z_array=None):
        self._nb_points = len(coordinates)
        self._is_2d = len(coordinates[0]) == 2
        if z is not None:
            self._is_2d = False

        self._is_closed = False
        if coordinates[0] == coordinates[-1]:
            self._is_closed = True
            if z_array is not None:
                self._is_closed = z_array[-1] == z_array[0]
        if z_array is None:
            coord = coordinates
        else:
            coord = [(x, y, z) for (x, y), z in zip(coordinates, z_array)]
        if self._is_closed:
            self._polyline = ClosedPolyline(coord)
        else:
            self._polyline = OpenPolyline(coord)
        if attributes is None:
            self._attributes = []
        else:
            self._attributes = attributes

    def to_3d(self, z_array):
        return Polyline(self.coords(), self.attributes()[:], z_array)

    def is_2d(self):
        return self._is_2d

    def is_closed(self):
        return self._is_closed

    def nb_points(self):
        return self._nb_points

    def attributes(self):
        return self._attributes

    def add_attribute(self, attribute):
        self._attributes.append(attribute)

    def coords(self):
        if self.is_closed():
            return self._polyline.exterior.coords
        return self._polyline.coords

    def polyline(self):
        return self._polyline

    def project(self, point):
        return self._polyline.project(point)

    def segments(self):
        prev_x, prev_y = None, None
        for x, y in self.coords():
            if prev_x is None:
                prev_x, prev_y = x, y
            else:
                yield x > prev_x, y > prev_y, Polyline([(prev_x, prev_y), (x, y)])
                prev_x, prev_y = x, y

    def __str__(self):
        return ['Open', 'Closed'][self.is_closed()] + ' polyline with coordinates %s' % str(list(self.coords()))

    def contains(self, item):
        return self._polyline.contains(item)

    def bounds(self):
        return self._polyline.bounds

    def length(self):
        return self._polyline.length

    def polygon_intersection(self, triangle):
        """!
        @brief (Used in volume calculation) Return the polygon or multipolygon intersection with the triangle
        @param <shapely.geometry.Polygon> triangle: A triangle
        @return <bool, shapely.geometry.Polygon or shapely.geometry.Multipolygon>: The intersection with the triangle
        """
        inter = self._polyline.intersection(triangle)
        if inter.geom_type == 'Polygon' or inter.geom_type == 'MultiPolygon':
            return True, inter
        elif inter.geom_type == 'GeometryCollection':
            poly = list(filter(lambda x: x.geom_type == 'Polygon', inter.geoms))
            if not poly:
                return False, None
            return True, MultiPolygon(poly)
        return False, None

    @staticmethod
    def triangle_difference(triangle, polygon):
        """!
        @brief (Used in volume calculation) Return the polygon or multipolygon in triangle but not in polygon
        @param <shapely.geometry.Polygon> triangle: A triangle
        @param <Polyline> polygon: A polygon
        @return <bool, shapely.geometry.Polygon or shapely.geometry.Multipolygon>: The difference between triangle and polygon
        """
        diff = triangle.difference(polygon.polyline())
        if diff.geom_type == 'Polygon' or diff.geom_type == 'MultiPolygon':
            return True, diff
        elif diff.geom_type == 'GeometryCollection':
            poly = list(filter(lambda x: x.geom_type == 'Polygon', diff.geoms))
            if not poly:
                return False, None
            return True, MultiPolygon(poly)
        return False, None

    def linestring_intersection(self, triangle):
        """!
        @brief (Used in flux calculation) Return the linearString intersection with the triangle
        @param <shapely.geometry.Polygon> triangle: A triangle
        @return <bool, [shapely.geometry.LinearString]>: The intersection with the triangle
        """
        inter = triangle.intersection(self._polyline)
        if inter.geom_type == 'LineString':
            return True, [inter]
        elif inter.geom_type == 'MultiLineString':
            return True, list(inter.geoms)
        elif inter.geom_type == 'GeometryCollection':
            return True, list(filter(lambda x: x.geom_type == 'LineString', inter.geoms))
        return False, None

    def apply_transformations(self, transformations):
        new_coords = np.array(list(self.coords()))
        if self.is_2d():
            new_coords = np.hstack((new_coords, np.zeros((new_coords.shape[0], 1))))

        for t in transformations:
            new_coords = np.apply_along_axis(t, 1, new_coords)
        if self.is_2d():
            new_coords = new_coords[:, :2]

        return Polyline(new_coords, self.attributes()[:])
