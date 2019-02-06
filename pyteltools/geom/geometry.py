"""!
Geometrical objects
"""

import numpy as np
from shapely.geometry import Point, MultiPolygon, LineString as OpenPolyline, Polygon as ClosedPolyline


class Polyline:
    """!
    @brief Custom (open or closed) polyline class
    """
    def __init__(self, coordinates, attributes=None, z_array=None, m_array=None, id=None):
        self._nb_points = len(coordinates)
        self._is_2d = len(coordinates[0]) == 2
        if z_array is not None:
            self._is_2d = False

        self._is_closed = False
        if tuple(coordinates[0]) == tuple(coordinates[-1]):
            self._is_closed = len(coordinates) > 2  # line with 2 coordinates which are identical can not be a polygon
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
            self._attributes = attributes[:]

        if m_array is None:
            self.m = [None] * self._nb_points
        else:
            if m_array:
                self.m = m_array[:]
            else:
                self.m = [None] * self._nb_points
        self.id = id

    def set_id(self, id):
        self.id = id

    def to_3d(self, z_array):
        return Polyline(self.coords(), self.attributes(), z_array)

    def to_2d(self):
        if self.is_2d():
            return Polyline(self.coords(), self.attributes(), m_array=self.m)
        return Polyline(list(map(tuple, np.array(self.coords())[:, :2])), self.attributes(), m_array=self.m)

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

    def project(self, x, y):
        return self._polyline.project(Point(x, y))

    def segments(self):
        prev_x, prev_y = None, None
        for coord in self.coords():
            x, y = coord[:2]  # ignore elevation if 3D
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
        @param triangle <shapely.geometry.Polygon>: A triangle
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
        @param triangle <shapely.geometry.Polygon>: A triangle
        @param polygon <shapely.geometry.Polygon>: A polygon
        @return <bool, shapely.geometry.Polygon or shapely.geometry.Multipolygon>:
            The difference between triangle and polygon
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
        @brief (Used in flux calculation) Returns the LinearString intersection with the triangle
        @param triangle <shapely.geometry.Polygon>: A triangle
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
            new_coords = np.hstack((new_coords, np.zeros((self.nb_points(), 1))))

        for t in transformations:
            new_coords = np.apply_along_axis(t, 1, new_coords)
        if self.is_2d():
            new_coords = new_coords[:, :2]

        return Polyline(list(map(tuple, new_coords)), self.attributes(), m_array=self.m)

    def resample(self, max_len):
        new_coords = []
        new_m = []
        coords = list(self.coords())

        new_coords.append(coords[0])
        new_m.append(self.m[0])

        for i in range(self.nb_points()-1):
            first_point, second_point = coords[i], coords[i+1]
            segment = OpenPolyline([first_point, second_point])
            nb_segments = int(np.ceil(segment.length / max_len))
            inv_nb_segments = 1/nb_segments
            first_m, second_m = self.m[i], self.m[i+1]
            if first_m is None or second_m is None:
                interpolate_m = False
            else:
                interpolate_m = True

            for j in range(1, nb_segments):
                new_point = list(segment.interpolate(j*inv_nb_segments, normalized=True).coords)[0]
                new_coords.append(new_point)
                if interpolate_m:
                    m = ((1-j) * first_m + j * second_m) * inv_nb_segments
                    new_m.append(m)
                else:
                    new_m.append(None)
            new_coords.append(second_point)
            new_m.append(second_m)
        return Polyline(new_coords, self.attributes(), m_array=new_m)

    def __repr__(self):
        return "%sPolyline with %i vertices" % ('Closed ' if self.is_closed() else '', len(self.coords()))
