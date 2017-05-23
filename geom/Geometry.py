"""!
Geometrical objects
"""

from shapely.geometry import LineString as OpenPolyline, Polygon as ClosedPolyline, MultiPolygon


class Polyline:
    """!
    @brief Custom (open or closed) polyline class
    """
    def __init__(self, coordinates):
        self._nb_points = len(coordinates)
        if coordinates[0] == coordinates[-1]:
            self._polyline = ClosedPolyline(coordinates)
            self._is_closed = True
        else:
            self._polyline = OpenPolyline(coordinates)
            self._is_closed = False

    def is_closed(self):
        return self._is_closed

    def nb_points(self):
        return self._nb_points

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


