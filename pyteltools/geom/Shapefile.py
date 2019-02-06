# pylint: disable=C0326
"""!
Read and write .shp files
"""
import numpy as np
import shapefile
from shapefile import ShapefileException as ShpException
from struct import error

from .geometry import Polyline


def get_shape_type(input_filename):
    sf = shapefile.Reader(input_filename)
    return sf.shapeType


def get_lines(input_filename, shape_type):
    sf = shapefile.Reader(input_filename)
    for record in sf.shapeRecords():
        if record.shape.shapeType == shape_type:
            attributes = record.record
            if shape_type == shapefile.POLYLINEZ:
                poly = Polyline(record.shape.points, attributes, record.shape.z)
            else:
                poly = Polyline(record.shape.points, attributes)
            yield poly


def get_open_polylines(input_filename):
    try:
        shape_type = get_shape_type(input_filename)
        if shape_type in (shapefile.POLYLINE, shapefile.POLYLINEZ, shapefile.POLYLINEM):
            for poly in get_lines(input_filename, shape_type):
                yield poly
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def get_polygons(input_filename):
    try:
        shape_type = get_shape_type(input_filename)
        if shape_type in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
            for poly in get_lines(input_filename, shape_type):
                yield poly
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def get_all_fields(input_filename):
    """!
    Get all fields characteristics of a shapefile
    @param input_filename <str>: path to shapefile
    @return <list([str, str, int, int])>: list composed of a tuple (attribute name, attribute type, length and
        precision) for each field
    """
    sf = shapefile.Reader(input_filename)
    return sf.fields[1:]


def get_attribute_names(input_filename):
    """!
    Get attributes (except the M value) of a shapefile
    @param input_filename <str>: path to shapefile
    @return <[str], [int]>: list of field names and indices
    """
    names, indices = [], []
    for i, (field_name, field_type, _, _) in enumerate(get_all_fields(input_filename)):
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
    """!
    Get all numeric attributes of a shapefile
    @param input_filename <str>: path to shapefile
    @return <[(int, str)>: list of field names and indices
    """
    for i, (field_name, field_type, _, _) in enumerate(get_all_fields(input_filename)):
        if field_type == 'N' or field_type == 'F':
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            yield i, field_name


def get_points(input_filename, indices=None, with_z=False):
    """!
    Get specific points (coordinates and attributes) from a shapefile
    @param input_filename <str>: path to shapefile
    @param indices <[int]>: indices of points
    @param with_z <bool>: extract z coordinate
    @return <tuple([(x, y, (z)), list(float)])>: tuple of coordinates and list of corresponding field values
    """
    try:
        sf = shapefile.Reader(input_filename)
        for record in sf.shapeRecords():
            if record.shape.shapeType in [shapefile.POINT, shapefile.POINTZ, shapefile.POINTM]:
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
                    if record.shape.shapeType == shapefile.POINTZ:
                        x, y = record.shape.points[0]
                        z = record.shape.z[0]
                        yield (x, y, z), decoded_attributes
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def write_shp_points_z(output_filename, z_name, points):
    w = shapefile.Writer(output_filename, shapefile.POINTZ)
    w.field(z_name, 'N', decimal=6)

    for (x, y, z) in points:
        w.pointz(x, y, z)
        w.record(z)


def write_shp_lines(output_filename, shape_type, lines, attribute_name):
    w = shapefile.Writer(output_filename, shapeType=shape_type)
    w.field(attribute_name, 'N', decimal=6)

    for poly in lines:
        coords = np.array(poly.coords())
        if shape_type < 10 and not poly.is_2d():
            coords = np.delete(coords, 2, 1)  # remove Z array
        if 10 < shape_type < 20 and poly.is_2d():
            coords = np.hstack((coords, np.zeros((poly.nb_points(), 1))))
        if shape_type > 10:
            m = np.array(poly.m, dtype=np.float).reshape(coords.shape[0], 1)
            coords = np.hstack((coords, m))
        if shape_type == shapefile.POLYLINE:
            w.line([list(map(tuple, coords))])
        elif shape_type == shapefile.POLYGON:
            w.poly([list(map(tuple, coords))])
        elif shape_type == shapefile.POLYLINEZ:
            w.linez([list(map(tuple, coords))])
        elif shape_type == shapefile.POLYGONZ:
            w.polyz([list(map(tuple, coords))])
        elif shape_type == shapefile.POLYLINEM:
            w.linem([list(map(tuple, coords))])
        else:
            w.polym([list(map(tuple, coords))])
        w.record(poly.attributes()[0])
