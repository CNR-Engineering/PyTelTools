"""!
Read and write .shp files
"""

import shapefile
from .geometry import Polyline


def get_lines(input_filename, closed):
    sf = shapefile.Reader(input_filename)
    for record in sf.shapeRecords():
        if record.shape.shapeType in [3, 5, 13, 15]:
            attributes = record.record
            if record.shape.shapeType > 10:
                poly = Polyline(record.shape.points, attributes, record.shape.z)
            else:
                poly = Polyline(record.shape.points, attributes)
            if poly.is_closed() == closed:
                yield poly


def get_open_polylines(input_filename):
    for poly in get_lines(input_filename, False):
        yield poly


def get_polygons(input_filename):
    for poly in get_lines(input_filename, True):
        yield poly


def get_all_fields(input_filename):
    sf = shapefile.Reader(input_filename)
    return sf.fields[1:]


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


def get_numeric_attribute_names(input_filename):
    sf = shapefile.Reader(input_filename)
    for i, (field_name, field_type, _, _) in enumerate(sf.fields[1:]):
        if field_type == 'N':
            yield i, field_name


def get_points(input_filename, indices=None, with_z=False):
    sf = shapefile.Reader(input_filename)
    for record in sf.shapeRecords():
        if record.shape.shapeType in [1, 11, 21]:
            attributes = record.record
            decoded_attributes = []
            for attribute in attributes:
                if type(attribute) == bytes:
                    decoded_attributes.append(attribute.decode('latin-1'))
                else:
                    decoded_attributes.append(attribute)
            if indices is not None:
                decoded_attributes = [decoded_attributes[i] for i in indices]
            if not with_z:
                yield tuple(record.shape.points[0]), decoded_attributes
            else:
                if record.shape.shapeType == 11:
                    x, y = record.shape.points[0]
                    z = record.shape.z[0]
                    yield (x, y, z), decoded_attributes


def write_xyz_points(output_filename, z_name, points, fields, attributes):
    w = shapefile.Writer(shapefile.POINTZ)

    # add fields
    for field_name, field_type, field_length, decimal_length in fields:
        w.field(field_name, field_type, str(field_length), decimal_length)
    w.field(z_name, 'N', decimal=6)

    # add records
    for (x, y, z), attribute in zip(points, attributes):
        w.point(x, y, z, shapeType=shapefile.POINTZ)
        w.record(*(attribute + [z]))
    w.save(output_filename)


def write_lines(output_filename, lines, fields, z_name):
    if lines[0].is_closed():
        shape_type = 5    # closed
    else:
        shape_type = 3    # open
    if not lines[0].is_2d():
        shape_type += 10  # 3d lines

    w = shapefile.Writer(shapeType=shape_type)

    # add fields
    for field_name, field_type, field_length, decimal_length in fields:
        w.field(field_name, field_type, str(field_length), decimal_length)
    if z_name is not None:
        w.field(z_name, 'N', decimal=6)

    # add records
    for poly in lines:
        w.poly(parts=[poly.coords()], shapeType=shape_type)
        w.record(*poly.attributes())
    w.save(output_filename)

