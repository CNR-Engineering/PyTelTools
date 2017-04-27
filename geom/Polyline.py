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

    def __str__(self):
        return ['Open', 'Closed'][self.is_closed()] + ' polyline with coordinates %s' % str(list(self.coords()))

    def contains(self, item):
        return self._polyline.contains(item)

    def polygon_intersection(self, other):
        # only Polygon-Polygon can have polygon intersection
        inter = self._polyline.intersection(other)
        if inter.is_empty:  # no intersection
            return False, None
        if inter.geom_type != 'Polygon':  # not polygon intersection
            return False, None
        return True, inter

