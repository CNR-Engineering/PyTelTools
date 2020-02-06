"""!
File format converter for geometrical objects
"""

import numpy as np
import shapefile
import struct

from pyteltools.conf import settings

from . import BlueKenue as bk, Shapefile as shp
from .geometry import Polyline


class GeomFileConverter:
    def __init__(self, from_file):
        self.from_file = from_file
        self.fields = []
        self.transformations = []
        self.shapes = []
        self.csv_separator = settings.CSV_SEPARATOR

    def set_csv_separator(self, separator):
        self.csv_separator = separator

    def read(self):
        pass

    def write(self, out_type, to_file, options):
        pass

    def set_transformations(self, transformations):
        self.transformations = transformations


class PointFileConverter(GeomFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)

    def transform(self):
        return self.apply_transform(self.shapes[:])

    def apply_transform(self, shapes):
        """!
        @brief Apply successive transformations to points
        @param shape <[tuple(x, y, (z)]>: original points
        @return transformed_points <[tuple(x, y, (z)]>: transformed points
        """
        if not self.transformations:
            return shapes
        transformed_points = shapes[:]
        for t in self.transformations:
            transformed_points = [t(p) for p in transformed_points]
        return transformed_points


class LineFileConverter(GeomFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)

    def apply_transform(self, shapes):
        if not self.transformations:
            return shapes
        new_shapes = []
        for poly in shapes:
            new_shapes.append(poly.apply_transformations(self.transformations))
        return new_shapes

    def resample(self, values):
        if not values:
            return self.shapes
        new_shapes = []
        for poly, value in zip(self.shapes, values):
            new_shapes.append(poly.resample(value))
        return new_shapes


class XYZConverter(PointFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)
        self.header = []

    def read(self):
        try:
            with bk.Read(self.from_file) as fin:
                fin.read_header()
                for point in fin.get_points():
                    self.shapes.append(point)
                self.header = fin.header
        except PermissionError:
            raise PermissionError
        if not self.shapes:
            raise ValueError

    def write(self, out_type, to_file, options):
        new_shapes = self.transform()
        if out_type == 'xyz':
            self.to_xyz(new_shapes, to_file)
        elif out_type == 'csv':
            self.to_csv(new_shapes, to_file)
        else:
            self.to_shp(new_shapes, to_file, options[0])

    def to_xyz(self, new_shapes, to_file):
        with bk.Write(to_file) as f:
            if settings.WRITE_XYZ_HEADER:
                f.write_header(self.header)
            f.write_points(new_shapes)

    def to_csv(self, new_shapes, to_file):
        with open(to_file, 'w') as f:
            f.write(self.csv_separator.join(['id point', 'x', 'y', 'z']))
            f.write('\n')
            for i, p in enumerate(new_shapes):
                x, y, z = p
                f.write(self.csv_separator.join(map(str, [i+1, x, y, z])))
                f.write('\n')

    def to_shp(self, new_shapes, to_file, z_name):
        shp.write_shp_points_z(to_file, z_name, new_shapes)


class BKLineConverter(LineFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)
        self.header = []
        self.nb_closed = 0
        self.nb_open = 0
        self.is_2d = from_file.endswith('.i2s')
        self.default_header = [':FileType i2s  ASCII  EnSim 1.0\n', ':EndHeader\n']  # from i3s to i2s

    def read(self):
        try:
            with bk.Read(self.from_file) as fin:
                fin.read_header()
                for line in fin.get_lines():
                    self.shapes.append(line)
                    if line.is_closed():
                        self.nb_closed += 1
                    else:
                        self.nb_open += 1
                self.header = fin.header
        except PermissionError:
            raise PermissionError
        if not self.shapes:
            raise ValueError

    def write(self, out_type, to_file, options):
        resample_option = options[-1]
        if resample_option:
            method, val = resample_option.split('|')
            if method == 'v':
                val = float(val)
                values = [val] * len(self.shapes)
            else:
                values = []
                for poly in self.shapes:
                    values.append(poly.attributes()[0])
                    if values[-1] <= 0:
                        raise RuntimeError
        else:
            values = []
        new_shapes = self.resample(values)
        new_shapes = self.apply_transform(new_shapes)

        if out_type == 'i3s':
            self.to_i2s_i3s(new_shapes, to_file)
        elif out_type == 'i2s':
            if self.is_2d:
                self.to_i2s_i3s(new_shapes, to_file)
            else:
                self.from_i3s_to_i2s(new_shapes, to_file)
        elif out_type == 'csv':
            self.to_csv(new_shapes, to_file)
        elif out_type == 'shp Polyline':
            self.to_shp(new_shapes, to_file, shapefile.POLYLINE, options[0])
        elif out_type == 'shp Polygon':
            self.to_shp(new_shapes, to_file, shapefile.POLYGON, options[0])
        elif out_type == 'shp PolylineZ':
            self.to_shp(new_shapes, to_file, shapefile.POLYLINEZ, options[0])
        else:  # out_type == 'shp PolygonZ'
            self.to_shp(new_shapes, to_file, shapefile.POLYGONZ, options[0])

    def to_i2s_i3s(self, new_shapes, to_file):
        attributes = []
        for line in new_shapes:
            attributes.append(line.attributes()[0])
        with bk.Write(to_file) as f:
            f.write_header(self.header)
            f.write_lines(new_shapes, attributes)

    def from_i3s_to_i2s(self, new_shapes, to_file):
        attributes = []
        shapes = []
        for line in new_shapes:
            attributes.append(line.attributes()[0])
            coords = np.array(list(line.coords()))
            shapes.append(Polyline(coords[:, :2]))
        with bk.Write(to_file) as f:
            f.write_header(self.default_header)
            f.write_lines(shapes, attributes)

    def to_csv(self, new_shapes, to_file):
        with open(to_file, 'w') as f:
            if self.is_2d:
                f.write(self.csv_separator.join(['id line', 'is closed', 'x', 'y', 'attribute']))
            else:
                f.write(self.csv_separator.join(['id line', 'is closed', 'x', 'y', 'z', 'attribute']))
            f.write('\n')
            for i, poly in enumerate(new_shapes):
                for coord in poly.coords():
                    f.write(self.csv_separator.join(map(str, [i+1, poly.is_closed()] + list(coord) + [poly.attributes()[0]])))
                    f.write('\n')

    def to_shp(self, new_shapes, to_file, shape_type, attribute_name):
        open_lines, closed_lines = [], []
        for line in new_shapes:
            if line.is_closed():
                closed_lines.append(line)
            else:
                open_lines.append(line)
        if shape_type % 5 == 0:  # polygon
            shp.write_shp_lines(to_file, shape_type, closed_lines, attribute_name)
        else:  # polyline
            shp.write_shp_lines(to_file, shape_type, open_lines, attribute_name)


class ShpPointConverter(PointFileConverter):
    def __init__(self, filename):
        super().__init__(filename)
        self.shape_type = shp.get_shape_type(filename)
        self.fields = []
        self.attributes = []
        self.numeric_fields = []
        self.m = []

    def read(self):
        self.fields = shp.get_all_fields(self.from_file)
        self.numeric_fields = shp.get_numeric_attribute_names(self.from_file)
        if self.shape_type == shapefile.POINT:
            self.read_point()
        elif self.shape_type == shapefile.POINTZ:
            try:
                self.read_pointz()
            except RuntimeError:
                raise RuntimeError
        else:
            self.read_pointm()
        if not self.shapes:
            raise ValueError

    def read_point(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == shapefile.POINT:
                x, y = record.shape.points[0]
                self.shapes.append(np.array([x, y, 0]))
                self.attributes.append(record.record)
        self.m = [None for _ in range(len(self.shapes))]

    def read_pointz(self):
        sf = shapefile.Reader(self.from_file)
        try:
            for record in sf.shapeRecords():
                if record.shape.shapeType == shapefile.POINTZ:
                    x, y = record.shape.points[0]
                    z = record.shape.z[0]
                    try:
                        m = record.shape.m[0]
                    except AttributeError:
                        m = None
                    self.m.append(m)
                    self.shapes.append(np.array([x, y, z]))
                    self.attributes.append(record.record)
        except struct.error:
            raise RuntimeError

    def read_pointm(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == shapefile.POINTM:
                x, y = record.shape.points[0]
                m = record.shape.m[0]
                self.m.append(m)
                self.shapes.append(np.array([x, y, 0]))
                self.attributes.append(record.record)

    def write(self, out_type, to_file, options):
        if out_type == 'shp Point':
            new_shapes = self.transform()
            self.to_point(new_shapes, to_file)

        elif out_type == 'shp PointZ':
            zfield, mfield = options
            if zfield != 'Z':
                # construct z
                attribute_index = int(zfield.split(' - ')[0])
                new_shapes = []
                for (x, y, _), attribute in zip(self.shapes, self.attributes):
                    new_z = attribute[attribute_index]
                    new_shapes.append((x, y, new_z))
            else:
                new_shapes = self.shapes
            transformed_shapes = self.apply_transform(new_shapes)
            if mfield == 'M':
                self.to_pointz(transformed_shapes, to_file, self.m)
            elif mfield == '0':
                self.to_pointz(transformed_shapes, to_file, [0 for _ in range(len(self.shapes))])
            else:
                attribute_index = int(mfield.split(' - ')[0])
                new_m = []
                for attribute in self.attributes:
                    new_m.append(attribute[attribute_index])
                self.to_pointz(transformed_shapes, to_file, new_m)

        elif out_type == 'shp PointM':
            new_shapes = self.transform()
            mfield = options[0]
            if mfield == 'M':  # use original M
                self.to_pointm(new_shapes, to_file, self.m)
            else:
                # construct M
                attribute_index = int(mfield.split(' - ')[0])
                new_m = []
                for attribute in self.attributes:
                    new_m.append(attribute[attribute_index])
                self.to_pointm(new_shapes, to_file, new_m)
        elif out_type == 'xyz':
            zfield = options[0]
            if zfield != 'Z':
                # construct z
                attribute_index = int(zfield.split(' - ')[0])
                new_shapes = []
                for (x, y, _), attribute in zip(self.shapes, self.attributes):
                    new_z = attribute[attribute_index]
                    new_shapes.append((x, y, new_z))
            else:
                new_shapes = self.shapes
            transformed_shapes = self.apply_transform(new_shapes)
            self.to_xyz(transformed_shapes, to_file)
        else:
            new_shapes = self.transform()
            self.to_csv(new_shapes, to_file)

    def to_xyz(self, new_shapes, to_file):
        with bk.Write(to_file) as f:
            if settings.WRITE_XYZ_HEADER:
                f.write_header()
            f.write_points(new_shapes)

    def to_point(self, new_shapes, to_file):
        w = shapefile.Writer(to_file, shapefile.POINT)
        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, _), attribute in zip(new_shapes, self.attributes):
            w.point(x, y)
            w.record(*attribute)

    def to_pointz(self, new_shapes, to_file, m_array):
        w = shapefile.Writer(to_file, shapefile.POINTZ)
        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, z), m, attribute in zip(new_shapes, m_array, self.attributes):
            w.pointz(x, y, z, m)
            w.record(*attribute)

    def to_pointm(self, new_shapes, to_file, m_array):
        w = shapefile.Writer(to_file, shapefile.POINTM)
        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, _), m, attribute in zip(new_shapes, m_array, self.attributes):
            w.pointm(x, y, m=m)
            w.record(*attribute)

    def to_csv(self, new_shapes, to_file):
        header = ['id point', 'x', 'y']
        if self.shape_type == shapefile.POINTZ:
            header.append('z')
            header.append('m')
        elif self.shape_type == shapefile.POINTM:
            header.append('m')
        for field in self.fields:
            field_name = field[0]
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            header.append(field_name)

        with open(to_file, 'w') as f:
            f.write(self.csv_separator.join(header))
            f.write('\n')
            for i, (point, m, attribute) in enumerate(zip(new_shapes, self.m, self.attributes)):
                x, y, z = point
                line = [i+1, x, y]
                if self.shape_type == shapefile.POINTZ:
                    line.append(z)
                    line.append(m)
                elif self.shape_type == shapefile.POINTM:
                    line.append(m)
                for a in attribute:
                    if type(a) == bytes:
                        a = a.decode('latin-1')
                    line.append(a)

                f.write(self.csv_separator.join(map(str, line)))
                f.write('\n')


class ShpLineConverter(LineFileConverter):
    def __init__(self, filename):
        super().__init__(filename)
        self.shape_type = shp.get_shape_type(filename)
        self.OUT_TYPE = {'shp Polyline': shapefile.POLYLINE, 'shp Polygon': shapefile.POLYGON,
                         'shp PolylineZ': shapefile.POLYLINEZ, 'shp PolygonZ': shapefile.POLYGONZ,
                         'shp PolylineM': shapefile.POLYLINEM, 'shp PolygonM': shapefile.POLYGONM,
                         'csv': 0, 'i2s': 1, 'i3s': 2}
        self.fields = []
        self.numeric_fields = []

    def apply_resample(self, shapes, values):
        if not values:
            return shapes
        new_shapes = []
        for poly, value in zip(shapes, values):
            new_shapes.append(poly.resample(value))
        return new_shapes

    def read(self):
        self.fields = shp.get_all_fields(self.from_file)
        for index, name in shp.get_numeric_attribute_names(self.from_file):
            self.numeric_fields.append((index, name))
        if self.shape_type in (shapefile.POLYLINE, shapefile.POLYGON):
            self.read_line()
        elif self.shape_type in (shapefile.POLYLINEZ, shapefile.POLYGONZ):
            self.read_linez()
        else:
            self.read_linem()

    def read_line(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == self.shape_type:
                attributes = record.record
                poly = Polyline(record.shape.points, attributes)
                self.shapes.append(poly)

    def read_linez(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == self.shape_type:
                attributes = record.record
                if hasattr(record.shape, 'm'):
                    m_array = record.shape.m
                else:
                    m_array = None
                poly = Polyline(record.shape.points, attributes, z_array=record.shape.z, m_array=m_array)
                self.shapes.append(poly)

    def read_linem(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == self.shape_type:
                attributes = record.record
                poly = Polyline(record.shape.points, attributes, m_array=record.shape.m)
                self.shapes.append(poly)

    def write(self, out_type, to_file, options):
        resample_option = options[-1]
        if resample_option:
            method, val = resample_option.split('|')
            if method == 'v':
                val = float(val)
                values = [val] * len(self.shapes)
            else:
                index = int(val.split(' - ')[0])
                values = []
                for poly in self.shapes:
                    values.append(poly.attributes()[index])
                    if values[-1] <= 0:
                        raise RuntimeError
        else:
            values = []

        new_shapes = self.resample(values)
        new_shapes = self.apply_transform(new_shapes)

        if out_type == 'i2s':  # i2s
            attribute_method = options[0]
            self.to_i2s(new_shapes, to_file, attribute_method)

        elif out_type == 'i3s':  # i3s
            zfield, attribute_method = options[0], options[1]
            if zfield != 'Z':
                # construct z
                attribute_index = int(zfield.split(' - ')[0])
                new_shapes = []
                for poly in self.shapes:
                    new_z = poly.attributes()[attribute_index]
                    new_poly = poly.to_2d()
                    new_shapes.append(new_poly.to_3d(z_array=[new_z for _ in range(poly.nb_points())]))
                new_shapes = self.apply_resample(new_shapes, values)
                new_shapes = self.apply_transform(new_shapes)
            self.to_i3s(new_shapes, to_file, attribute_method)

        elif out_type == 'csv':
            self.to_csv(new_shapes, to_file)

        else:
            shape_type = self.OUT_TYPE[out_type]
            self.to_shp(new_shapes, to_file, shape_type, options[0])

    def to_shp(self, new_shapes, to_file, shape_type, attribute_name):
        open_lines, closed_lines = [], []
        for line in new_shapes:
            if line.is_closed():
                closed_lines.append(line)
            else:
                open_lines.append(line)
        if shape_type % 5 == 0:  # polygon
            shp.write_shp_lines(to_file, shape_type, closed_lines, attribute_name)
        else:  # polyline
            shp.write_shp_lines(to_file, shape_type, open_lines, attribute_name)

    def to_i2s(self, new_shapes, to_file, attribute_method):
        attributes = []
        lines = []
        for i, poly in enumerate(new_shapes):
            lines.append(poly.to_2d())
            if attribute_method == '0':
                attributes.append(0)
            elif attribute_method == 'Iteration':
                attributes.append(i+1)
            else:
                attribute_index = int(attribute_method.split(' - ')[0])
                attributes.append(poly.attributes()[attribute_index])

        with bk.Write(to_file) as f:
            f.write_header()
            f.write_lines(lines, attributes)

    def to_i3s(self, new_shapes, to_file, attribute_method):
        attributes = []
        for i, poly in enumerate(new_shapes):
            if attribute_method == '0':
                attributes.append(0)
            elif attribute_method == 'Iteration':
                attributes.append(i+1)
            else:
                attribute_index = int(attribute_method.split(' - ')[0])
                attributes.append(poly.attributes()[attribute_index])

        with bk.Write(to_file) as f:
            f.write_header()
            f.write_lines(new_shapes, attributes)

    def to_csv(self, new_shapes, to_file):
        header = ['id line', 'x', 'y']
        if self.shape_type > 20:
            header.append('m')
        elif self.shape_type > 10:
            header.append('z')
            header.append('m')

        for field in self.fields:
            field_name = field[0]
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            header.append(field_name)

        with open(to_file, 'w') as f:
            f.write(self.csv_separator.join(header))
            f.write('\n')
            for i, poly in enumerate(new_shapes):
                attributes = []
                for a in poly.attributes():
                    if type(a) == bytes:
                        a = a.decode('latin-1')
                    attributes.append(str(a))

                for coord, m in zip(poly.coords(), poly.m):
                    x, y = coord[0], coord[1]
                    line = [i+1, x, y]
                    if self.shape_type > 20:
                        line.append(m)
                    elif self.shape_type > 10:
                        line.append(coord[2])
                        line.append(m)
                    line.extend(attributes)
                    f.write(self.csv_separator.join(map(str, line)))
                    f.write('\n')


class ShpMultiPointConverter(GeomFileConverter):
    def __init__(self, filename):
        super().__init__(filename)
        self.shape_type = shp.get_shape_type(filename)
        self.fields = []
        self.attributes = []
        self.numeric_fields = []
        self.m = []

    def transform(self):
        return self.apply_transform(self.shapes[:])

    def apply_transform(self, shapes):
        """!
        @brief Apply successive transformations to shapes
        @param shape <[numpy 2D-array]>: original shapes
        @return transformed_points <[numpy 2D-array]>: transformed shapes
        """
        if not self.transformations:
            return shapes
        transformed_points = shapes[:]
        for t in self.transformations:
            transformed_points = [np.reshape([t(p) for p in points], points.shape) for points in transformed_points]
        return transformed_points

    def read(self):
        self.fields = shp.get_all_fields(self.from_file)
        self.numeric_fields = shp.get_numeric_attribute_names(self.from_file)
        if self.shape_type == shapefile.MULTIPOINT:
            self.read_point()
        elif self.shape_type == shapefile.MULTIPOINTZ:
            try:
                self.read_pointz()
            except RuntimeError:
                raise RuntimeError
        else:
            self.read_pointm()
        if not self.shapes:
            raise ValueError

    def read_point(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == shapefile.MULTIPOINT:
                points = np.array(record.shape.points)
                points = np.hstack((points, np.zeros((points.shape[0], 1))))
                self.shapes.append(points)
                self.attributes.append(record.record)

    def read_pointz(self):
        sf = shapefile.Reader(self.from_file)
        try:
            for record in sf.shapeRecords():
                if record.shape.shapeType == shapefile.MULTIPOINTZ:
                    points = np.array(record.shape.points)
                    z = record.shape.z
                    if hasattr(record.shape, 'm'):
                        m = record.shape.m
                    else:
                        m = [0] * points.shape[0]  # FIXME: default value : 0
                    self.m.append(np.array(m))
                    points = np.hstack((points, np.array(z).reshape((points.shape[0], 1))))
                    self.shapes.append(points)
                    self.attributes.append(record.record)
        except struct.error:
            raise RuntimeError

    def read_pointm(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == shapefile.MULTIPOINTM:
                points = np.array(record.shape.points)
                points = np.hstack((points, np.zeros((points.shape[0], 1))))
                m = record.shape.m
                self.m.append(np.array(m))
                self.shapes.append(points)
                self.attributes.append(record.record)

    def write(self, out_type, to_file, options):
        """!
        brief Write output file
        @param out_type <str>: output file type
        @param to_file <str>: output file path
        @param options <[str]>: values of options
        """
        if out_type == 'xyz':
            transformed_shapes = self.transform()
            self.to_xyz(transformed_shapes, to_file)

        elif out_type == 'csv':
            transformed_shapes = self.transform()
            self.to_csv(transformed_shapes, to_file)

        elif out_type == 'shp Point':
            transformed_shapes = self.transform()
            self.to_point(transformed_shapes, to_file)

        elif out_type == 'shp PointZ':
            zfield, mfield = options
            new_m = self._construct_m(mfield)
            new_shapes = self._construct_z(zfield)
            transformed_shapes = self.apply_transform(new_shapes)
            self.to_pointz(transformed_shapes, to_file, new_m)

        elif out_type == 'shp PointM':
            mfield = options[0]
            transformed_shapes = self.transform()
            new_m = self._construct_m(mfield)
            self.to_pointm(transformed_shapes, to_file, new_m)

        else:
            if out_type == 'shp MultiPointZ':
                zfield, mfield = options
                shape_type = shapefile.MULTIPOINTZ
                new_m = self._construct_m(mfield)
                new_shapes = self._construct_z(zfield)
                transformed_shapes = self.apply_transform(new_shapes)
                self.to_multiz(transformed_shapes, new_m, to_file, shape_type)
            elif out_type == 'shp MultiPointM':
                mfield = options[0]
                shape_type = shapefile.MULTIPOINTM
                new_m = self._construct_m(mfield)
                transformed_shapes = self.transform()
                self.to_multim(transformed_shapes, new_m, to_file, shape_type)
            elif out_type == 'shp MultiPoint':
                shape_type = shapefile.MULTIPOINT
                transformed_shapes = self.transform()
                self.to_multi(transformed_shapes, to_file, shape_type)

    def _construct_z(self, zfield):
        """!
        @brief Builds modified shapes with new Z coordinates
        @param zfield <str>: field or identifier ('0' or 'Z') to build Z
        @return new_shape <[numpy 2D-array]>: list of coordinates arrays
        """
        if zfield != 'Z':
            # construct z
            attribute_index = int(zfield.split(' - ')[0])
            new_shapes = []
            for points, attributes in zip(self.shapes, self.attributes):
                new_z = attributes[attribute_index]
                new_list = [(x, y, new_z) for x, y, _ in points]
                new_shapes.append(np.array(new_list))
        elif zfield == '0':
            new_shapes = []
            for points, attributes in zip(self.shapes, self.attributes):
                new_list = [(x, y, 0) for x, y, _ in points]
                new_shapes.append(np.array(new_list))
        else:
            new_shapes = self.shapes
        return new_shapes

    def _construct_m(self, mfield):
        """!
        @brief Builds new M values
        @param mfield <str>: field or identifier ('0' or 'M') to build M
        @return new_shape <[numpy 1D-array]>: list of arrays of M values
        """
        if mfield == 'M':
            return self.m
        elif mfield == '0':
            new_m = []
            for points in self.shapes:
                new_m.append(np.array([0] * len(points)))
            return new_m
        else:
            attribute_index = int(mfield.split(' - ')[0])
            new_m = []
            for points, attributes in zip(self.shapes, self.attributes):
                m = attributes[attribute_index]
                new_m.append(np.array([m] * len(points)))
            return new_m

    def _to_multi_init(self, to_file, shape_type):
        """!
        @brief Prepare Writer for MultiPoints* Shapefile
        @param to_file <str>: output file path
        @param shape_type <int>: shape type identifier
        """
        w = shapefile.Writer(to_file, shapeType=shape_type)
        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)
        return w

    def to_multi(self, new_shapes, to_file, shape_type):
        w = self._to_multi_init(to_file, shape_type)
        for points, attributes in zip(new_shapes, self.attributes):
            if points.shape[1] == 3:
                points = np.delete(points, 2, 1)  # remove Z array
            w.multipoint(list(map(tuple, points)))
            w.record(*attributes)

    def to_multim(self, new_shapes, new_m, to_file, shape_type):
        w = self._to_multi_init(to_file, shape_type)
        for points, points_m, attributes in zip(new_shapes, new_m, self.attributes):
            m = np.array(points_m, dtype=np.float).reshape(points.shape[0], 1)
            if points.shape[1] == 3:
                points = np.delete(points, 2, 1)  # remove Z array
            coords = np.hstack((points, m))
            w.multipointm(list(map(tuple, coords)))
            w.record(*attributes)

    def to_multiz(self, new_shapes, new_m, to_file, shape_type):
        w = self._to_multi_init(to_file, shape_type)
        for points, points_m, attributes in zip(new_shapes, new_m, self.attributes):
            m = np.array(points_m, dtype=np.float).reshape(points.shape[0], 1)
            coords = np.hstack((points, m))
            w.multipointz(list(map(tuple, coords)))
            w.record(*attributes)

    def to_point(self, new_shapes, to_file):
        with shapefile.Writer(to_file, shapefile.POINT) as w:
            w.field('ID_MultiPoint', 'N', decimal=0)
            for field_name, field_type, field_length, decimal_length in self.fields:
                w.field(field_name, field_type, str(field_length), decimal_length)

            for i, (points, attributes) in enumerate(zip(new_shapes, self.attributes)):
                new_attributes = [i+1] + attributes
                for x, y, _ in points:
                    w.point(x, y)
                    w.record(*new_attributes)

    def to_pointz(self, new_shapes, to_file, m_array):
        with shapefile.Writer(to_file, shapefile.POINTZ) as w:
            w.field('ID_MultiPointZ', 'N', decimal=0)
            for field_name, field_type, field_length, decimal_length in self.fields:
                w.field(field_name, field_type, str(field_length), decimal_length)

            for i, (points, points_m, attributes) in enumerate(zip(new_shapes, m_array, self.attributes)):
                new_attributes = [i+1] + attributes
                for (x, y, z), m in zip(points, points_m):
                    w.pointz(x, y, z, m=m)
                    w.record(*new_attributes)

    def to_pointm(self, new_shapes, to_file, m_array):
        with shapefile.Writer(to_file, shapefile.POINTM) as w:
            w.field('ID_MultiPointM', 'N', decimal=0)
            for field_name, field_type, field_length, decimal_length in self.fields:
                w.field(field_name, field_type, str(field_length), decimal_length)

            for i, (points, points_m, attributes) in enumerate(zip(new_shapes, m_array, self.attributes)):
                new_attributes = [i+1] + attributes
                for (x, y, _), m in zip(points, points_m):
                    w.pointm(x, y, m=m)
                    w.record(*new_attributes)

    def to_csv(self, new_shapes, to_file):
        header = ['id_point', 'x', 'y']
        if self.shape_type > 20:
            header.append('m')
        elif self.shape_type > 10:
            header.append('z')
            header.append('m')

        for field in self.fields:
            field_name = field[0]
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            header.append(field_name)

        with open(to_file, 'w') as f:
            f.write(self.csv_separator.join(header))
            f.write('\n')
            for i, (points, points_m, attributes) in enumerate(zip(new_shapes, self.m, self.attributes)):
                decoded_attributes = []
                for a in attributes:
                    if type(a) == bytes:
                        a = a.decode('latin-1')
                    decoded_attributes.append(a)

                for (x, y, z), m in zip(points, points_m):
                    line = [i+1, x, y]
                    if self.shape_type > 20:
                        line.append(m)
                    elif self.shape_type > 10:
                        line.append(z)
                        line.append(m)
                    line.extend(decoded_attributes)
                    f.write(self.csv_separator.join(map(str, line)))
                    f.write('\n')

    def to_xyz(self, new_shapes, to_file):
        with bk.Write(to_file) as f:
            if settings.WRITE_XYZ_HEADER:
                f.write_header()
            for point in new_shapes:
                f.write_points(point)
