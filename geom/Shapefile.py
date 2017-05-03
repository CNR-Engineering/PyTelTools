import shapefile
from .Polyline import Polyline


def read_shp(input_filename):
    sf = shapefile.Reader(input_filename)
    for shape in sf.iterShapes():
        poly = Polyline(shape.points)
        if poly.is_closed():
            yield poly


