import shapefile
from .Polyline import Polyline


def get_open_polylines(input_filename):
    sf = shapefile.Reader(input_filename)
    for shape in sf.iterShapes():
        poly = Polyline(shape.points)
        if poly.is_closed():
            yield poly


def get_polygons(input_filename):
    sf = shapefile.Reader(input_filename)
    for shape in sf.iterShapes():
        poly = Polyline(shape.points)
        if not poly.is_closed():
            yield poly


