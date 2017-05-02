from shapely.geometry import LineString as OpenPolyline, Polygon as ClosedPolyline


class Polyline:
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

    def __str__(self):
        return ['Open', 'Closed'][self.is_closed()] + ' polyline with coordinates %s' % str(list(self.coords()))

    def contains(self, item):
        return self._polyline.contains(item)

    def polygon_intersection(self, other):
        # Polygon-Polygon can have polygon or multipolygon intersection
        inter = self._polyline.intersection(other)
        if inter.geom_type == 'Polygon':
            return True, [inter]
        elif inter.geom_type == 'MultiPolygon':
            return True, list(inter.geoms)
        return False, None

    @staticmethod
    def triangle_difference(triangle, polygon):
        """!
        returned the part in triangle but not in polygon, used in volume calculation
        """
        # Polygon-Polygon can have polygon or multipolygon difference
        diff = triangle.difference(polygon.polyline())
        if diff.geom_type == 'Polygon':
            return True, [diff]
        elif diff.geom_type == 'MultiPolygon':
            return True, list(diff.geoms)
        return False, None

