"""!
File format converter for geometrical objects
"""

import numpy as np
import struct
import geom.BlueKenue as bk
import geom.Shapefile as shp
from geom.geometry import Polyline
import shapefile


class GeomFileConverter:
    def __init__(self, from_file):
        self.from_file = from_file
        self.fields = []
        self.transformations = []
        self.shapes = []

    def set_transformations(self, transformations):
        self.transformations = transformations


class PointFileConverter(GeomFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)

    def transform(self):
        if not self.transformations:
            return self.shapes
        transformed_points = self.shapes[:]
        for t in self.transformations:
            transformed_points = [t(p) for p in transformed_points]
        return transformed_points

    def apply_transform(self, shapes):
        if not self.transformations:
            return shapes
        transformed_points = shapes[:]
        for t in self.transformations:
            transformed_points = [t(p) for p in transformed_points]
        return transformed_points


class LineFileConverter(GeomFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)

    def transform(self):
        if not self.transformations:
            return self.shapes
        new_shapes = []
        for poly in self.shapes:
            new_shapes.append(poly.apply_transformations(self.transformations))
        return new_shapes

    def apply_transform(self, shapes):
        if not self.transformations:
            return shapes
        new_shapes = []
        for poly in shapes:
            new_shapes.append(poly.apply_transformations(self.transformations))
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
            f.write_header(self.header)
            f.write_points(new_shapes)

    def to_csv(self, new_shapes, to_file):
        with open(to_file, 'w') as f:
            f.write(';'.join(['id point', 'x', 'y', 'z']))
            f.write('\n')
            for i, p in enumerate(new_shapes):
                x, y, z = p
                f.write(';'.join(map(str, [i+1, x, y, z])))
                f.write('\n')

    def to_shp(self, new_shapes, to_file, z_name):
        shp.write_xyz_points(to_file, z_name, new_shapes, [], [])


class BKLineConverter(LineFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)
        self.header = []
        self.nb_closed = 0
        self.nb_open = 0
        self.is_2d = from_file[-4:] == '.i2s'
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
        new_shapes = self.transform()
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
            self.to_shp(new_shapes, to_file, 3, options[0])
        elif out_type == 'shp Polygon':
            self.to_shp(new_shapes, to_file, 5, options[0])
        elif out_type == 'shp PolylineZ':
            self.to_shp(new_shapes, to_file, 13, options[0])
        else:
            self.to_shp(new_shapes, to_file, 15, options[0])

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
                f.write(';'.join(['id line', 'is closed', 'x', 'y', 'attribute']))
            else:
                f.write(';'.join(['id line', 'is closed', 'x', 'y', 'z', 'attribute']))
            f.write('\n')
            for i, poly in enumerate(new_shapes):
                for coord in poly.coords():
                    f.write(';'.join(map(str, [i+1, poly.is_closed()] + list(coord) + [poly.attributes()[0]])))
                    f.write('\n')

    def to_shp(self, new_shapes, to_file, shape_type, attribute_name):
        open_lines, closed_lines = [], []
        for line in new_shapes:
            if line.is_closed():
                closed_lines.append(line)
            else:
                open_lines.append(line)
        if shape_type % 5 == 0:
            shp.write_lines(to_file, shape_type, closed_lines, [], attribute_name)
        else:
            shp.write_lines(to_file, shape_type, open_lines, [], attribute_name)


class ShpPointConverter(PointFileConverter):
    def __init__(self, filename, shape_type):
        super().__init__(filename)
        self.shape_type = shape_type
        self.fields = []
        self.attributes = []
        self.numeric_fields = []
        self.m = []

    def read(self):
        self.fields = shp.get_all_fields(self.from_file)
        for index, name in shp.get_numeric_attribute_names(self.from_file):
            self.numeric_fields.append((index, name))
        if self.shape_type == 1:
            self.read_point()
        elif self.shape_type == 11:
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
            if record.shape.shapeType == 1:
                x, y = record.shape.points[0]
                self.shapes.append(np.array([x, y, 0]))
                self.attributes.append(record.record)
        self.m = [0 for _ in range(len(self.shapes))]

    def read_pointz(self):
        sf = shapefile.Reader(self.from_file)
        try:
            for record in sf.shapeRecords():
                if record.shape.shapeType == 11:
                    x, y = record.shape.points[0]
                    z = record.shape.z[0]
                    m = record.shape.m[0]
                    if m is None:
                        m = 0
                    self.m.append(m)
                    self.shapes.append(np.array([x, y, z]))
                    self.attributes.append(record.record)
        except struct.error:
            raise RuntimeError

    def read_pointm(self):
        sf = shapefile.Reader(self.from_file)
        for record in sf.shapeRecords():
            if record.shape.shapeType == 21:
                x, y = record.shape.points[0]
                m = record.shape.m[0]
                if m is None:
                    m = 0
                self.m.append(m)
                self.shapes.append(np.array([x, y, 0]))
                self.attributes.append(record.record)

    def write(self, out_type, to_file, options):
        if out_type == 'shp Point':
            new_shapes = self.transform()
            self.to_point(new_shapes, to_file)
        elif out_type == 'shp PointZ':
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
            if len(options) > 1:
                mfield = options[1]
                if mfield == 'M':
                    self.to_pointz(transformed_shapes, to_file, self.m)
                elif mfield == '0':
                    self.to_pointz(transformed_shapes, to_file, [0 for _ in range(len(self.shapes))])
                else:
                    attribute_index = int(mfield.split(' - ')[0])
                    new_m = []
                    for attribute in self.attributes:
                        m = attribute[attribute_index]
                        new_m.append(m)
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
                    m = attribute[attribute_index]
                    new_m.append(m)
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
            f.write_points(new_shapes)

    def to_point(self, new_shapes, to_file):
        w = shapefile.Writer(shapefile.POINT)

        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, z), attribute in zip(new_shapes, self.attributes):
            w.point(x, y, shapeType=shapefile.POINT)
            w.record(*attribute)
        w.save(to_file)

    def to_pointz(self, new_shapes, to_file, m_array):
        w = shapefile.Writer(shapefile.POINTZ)

        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, z), m, attribute in zip(new_shapes, m_array, self.attributes):
            w.point(x, y, z, m, shapeType=shapefile.POINTZ)
            w.record(*attribute)
        w.save(to_file)

    def to_pointm(self, new_shapes, to_file, m_array):
        w = shapefile.Writer(shapefile.POINTM)

        for field_name, field_type, field_length, decimal_length in self.fields:
            w.field(field_name, field_type, str(field_length), decimal_length)

        for (x, y, _), m, attribute in zip(new_shapes, m_array, self.attributes):
            w.point(x, y, m=m, shapeType=shapefile.POINTM)
            w.record(*attribute)
        w.save(to_file)

    def to_csv(self, new_shapes, to_file):
        header = ['id point', 'x', 'y']
        if self.shape_type == 11:
            header.append('z')
            header.append('m')
        elif self.shape_type == 21:
            header.append('m')
        for field in self.fields:
            field_name = field[0]
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            header.append(field_name)

        with open(to_file, 'w') as f:
            f.write(';'.join(header))
            f.write('\n')
            for i, (point, m, attribute) in enumerate(zip(new_shapes, self.m, self.attributes)):
                x, y, z = point
                line = [i+1, x, y]
                if self.shape_type == 11:
                    line.append(z)
                    line.append(m)
                elif self.shape_type == 21:
                    line.append(m)
                for a in attribute:
                    if type(a) == bytes:
                        a = a.decode('latin-1')
                    line.append(a)

                f.write(';'.join(map(str, line)))
                f.write('\n')


class ShpLineConverter(LineFileConverter):
    def __init__(self, filename, shape_type):
        super().__init__(filename)
        self.shape_type = shape_type
        self.i2s_header = [':FileType i2s  ASCII  EnSim 1.0\n', ':EndHeader\n']
        self.i3s_header = [':FileType i3s  ASCII  EnSim 1.0\n', ':EndHeader\n']
        self.fields = []
        self.attributes = []
        self.numeric_fields = []
        self.m = []

    def read(self):
        self.fields = shp.get_all_fields(self.from_file)
        for index, name in shp.get_numeric_attribute_names(self.from_file):
            self.numeric_fields.append((index, name))

    def write(self, out_type, to_file, options):
        pass