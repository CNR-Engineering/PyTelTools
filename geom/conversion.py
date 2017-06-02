import numpy as np

from geom import BlueKenue
import geom.Shapefile as shp


class PointSetConverter:
    def __init__(self, from_file, to_file, transformations, z_name, z_index):
        self.from_file = from_file
        self.to_file = to_file
        self.z_name = z_name
        self.z_index = z_index

        self.transformations = transformations
        self.from_points = []

    def transform(self):
        to_points = self.from_points[:]
        for t in self.transformations:
            to_points = [t(p) for p in to_points]
        return to_points

    def convert(self):
        if self.from_file[-4:] == '.xyz':
            header = self.read_xyz()
        else:
            header = []
            try:
                self.read_shp()
            except ValueError:
                return False, 'number'
        if not self.from_points:
            return False, 'empty'
        if self.to_file[-4:] == '.xyz':
            self.write_xyz(header)
        else:
            self.write_shp()
        return True, ''

    def read_shp(self):
        for (x, y), attributes in shp.get_points(self.from_file):
            try:
                z = float(attributes[self.z_index])
            except ValueError:
                raise ValueError
            self.from_points.append(np.array([x, y, z]))

    def read_xyz(self):
        with BlueKenue.Read(self.from_file) as fin:
            fin.read_header()
            for p in fin.get_points():
                self.from_points.append(p)
            header = fin.header
        return header

    def write_shp(self):
        to_points = self.transform()
        shp.write_points(self.to_file, self.z_name, to_points)

    def write_xyz(self, header):
        to_points = self.transform()
        with BlueKenue.Write(self.to_file) as fout:
            fout.write_header(header)
            fout.write_points(to_points)


class LineSet2DConverter:
    def __init__(self, from_file, to_file, transformations, is_closed, z_method):
        self.from_file = from_file
        self.to_file = to_file
        self.is_closed =is_closed

        self.z_method = z_method

        self.transformations = transformations
        self.from_lines = []

    def read_shp_open(self):
        for p in shp.get_open_polylines(self.from_file):
            points = []
            for x, y in p.coords():
                points.append(np.array([x, y, 0]))
            self.from_lines.append(points)

    def read_shp_closed(self):
        for p in shp.get_polygons(self.from_file):
            points = []
            for x, y in p.coords():
                points.append(np.array([x, y, 0]))
            self.from_lines.append(points)



