import shapefile
from .Geometry import Polyline


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


def get_attribute_names(input_filename):
    sf = shapefile.Reader(input_filename)
    names = []
    indices = []
    for i, (field_name, field_type, _, _) in enumerate(sf.fields[1:]):
        if field_type == 'M':
            continue
        else:
            indices.append(i)
            if type(field_name) == bytes:
                names.append(field_name.decode('latin-1'))
            else:
                names.append(field_name)
    return names, indices


def get_points(input_filename, indices=None):
    sf = shapefile.Reader(input_filename)
    for record in sf.shapeRecords():
        if record.shape.shapeType in [1, 11, 21]:
            attributes = record.record
            decoded_attributes = []
            for attribute in attributes:
                if type(attribute) == bytes:
                    decoded_attributes.append(attribute.decode('latin-1'))
                else:
                    decoded_attributes.append(str(attribute))
            if indices is not None:
                decoded_attributes = [decoded_attributes[i] for i in indices]
            yield tuple(record.shape.points[0]), decoded_attributes

