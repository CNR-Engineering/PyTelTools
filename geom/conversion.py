"""!
File format converter for geometrical objects
"""

import numpy as np

from geom import BlueKenue
import geom.Shapefile as shp
from geom.transformation import IDENTITY


class GeomFileConverter:
    def __init__(self, from_file):
        self.from_file = from_file
        self.fields = []
        self.transformations = [IDENTITY]
        self.shapes = []

    def set_transformations(self, transformations):
        self.transformations = transformations


class PointSetConverter(GeomFileConverter):
    def __init__(self, from_file):
        super().__init__(from_file)

        self.from_xyz = False
        self.attributes = []

        self.z_index = None
        self.transformations = [IDENTITY]
        self.header = []

    def set_z_index(self, index):
        self.z_index = index

    def transform(self):
        transformed_points = self.shapes[:]
        for t in self.transformations:
            transformed_points = [t(p) for p in transformed_points]
        self.shapes = transformed_points

    def read(self):
        if self.from_file[-4:] == '.xyz':
            self.from_xyz = True
            self.read_xyz()
            if not self.shapes:
                return False, 'empty'
        else:
            native_z, non_empty = self.try_shp()
            if not non_empty:
                return False, 'empty'
            return True, 'native'
        return True, ''

    def try_shp(self):
        self.fields = shp.get_all_fields(self.from_file)
        for (x, y, z), attributes in shp.get_points(self.from_file, with_z=True):
            self.shapes.append(np.array([x, y, z]))
            self.attributes.append(attributes)
        if not self.shapes:
            for (x, y), attributes in shp.get_points(self.from_file):
                self.shapes.append(np.array([x, y]))
                self.attributes.append(attributes)
            if not self.shapes:
                return False, False
            return False, True
        return True, True

    def convert(self, to_file, z_name):
        if self.z_index is not None:
            self.read_shp()

        self.transform()
        if to_file[-4:] == '.xyz':
            self.write_xyz(to_file)
        else:
            self.write_shp(to_file, z_name)

    def read_shp(self):
        for (x, y), attributes in shp.get_points(self.from_file):
            try:
                z = float(attributes[self.z_index])
            except ValueError:
                raise ValueError
            self.shapes.append(np.array([x, y, z]))

    def read_xyz(self):
        with BlueKenue.Read(self.from_file) as fin:
            fin.read_header()
            for p in fin.get_points():
                self.shapes.append(p)
            self.header = fin.header

    def write_shp(self, to_file, z_name):
        shp.write_xyz_points(to_file, z_name, self.shapes, self.fields, self.attributes)

    def write_xyz(self, to_file):
        with BlueKenue.Write(to_file) as fout:
            fout.write_header(self.header)
            fout.write_points(self.shapes)


class LineSetsConverter(GeomFileConverter):
    def __init__(self, from_file, is_closed):
        super().__init__(from_file)
        self.is_2d = False
        self.is_closed = is_closed
        self.from_shp = False
        self.transformations = [IDENTITY]
        self.z_name = None
        self.z_value = None
        self.header = [':FileType i2s  ASCII  EnSim 1.0\n', ':EndHeader\n']

    def read(self):
        if self.from_file[-4:] == '.shp':
            self.from_shp = True
            self.read_shp()
        else:
            self.read_bk()
        if not self.shapes:
            return False
        self.is_2d = self.shapes[0].is_2d()
        return True

    def read_shp(self):
        self.fields = shp.get_all_fields(self.from_file)
        for line in shp.get_lines(self.from_file, self.is_closed):
            self.shapes.append(line)

    def read_bk(self):
        with BlueKenue.Read(self.from_file) as fin:
            fin.read_header()
            for poly in fin.get_lines(self.is_closed):
                self.shapes.append(poly)
            self.header = fin.header

    def transform(self):
        for poly in self.shapes:
            poly.apply_transformations(self.transformations)

    def write_shp(self, to_file, z_name):
        shp.write_lines(to_file, self.shapes, self.fields, z_name)

    def write_bk(self, to_file, z_field):
        if z_field == '0':
            attributes = [0] * len(self.shapes)
        elif z_field == 'Iteration':
            attributes = [i+1 for i in range(len(self.shapes))]
        elif z_field == 'Attribute value':
            attributes = [poly.attributes()[0] for poly in self.shapes]
        else:
            index = int(z_field.split(' - ')[0].split()[1])
            attributes = []
            for poly in self.shapes:
                attributes.append(poly.attributes()[index])
        with BlueKenue.Write(to_file) as fout:
            fout.write_header(self.header)
            fout.write_lines(self.shapes, attributes)

    def convert(self, to_file, z_name, z_field):
        self.transform()

        if to_file[-4:] == '.shp':
            self.write_shp(to_file, z_name)
        else:
            self.write_bk(to_file, z_field)

