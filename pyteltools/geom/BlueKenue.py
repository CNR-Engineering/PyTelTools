"""!
Read and write BlueKenue files (.i2s/.i3s/.xyz)
"""

import numpy as np

from .geometry import Polyline


class BlueKenue:
    def __init__(self, filename, mode):
        """!
        @brief BlueKenue file object
        @param filename <str>: path to BlueKenue file
        @param mode <str>: `r` for read, `w` or `x` for write mode
        """
        self.filename = filename
        self.mode = mode
        self.file = None
        self.header = None

    def __enter__(self):
        self.file = open(self.filename, self.mode, encoding='ISO-8859-1')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()


class Read(BlueKenue):
    """"!
    BlueKenue file reader
    """
    def __init__(self, filename):
        super().__init__(filename, 'r')

    def read_header(self):
        self.header = []
        while True:
            line = self.file.readline()
            self.header.append(line)
            if line == ':EndHeader\n':
                break
            if not line:
                self.header = []
                self.file.seek(0)
                return False
        return True

    def get_lines(self):
        while True:
            line = self.file.readline()
            if not line:  # EOF
                break
            if line == '\n':  # there could be blank lines between line sets
                continue
            line_header = tuple(line.rstrip().split())
            try:
                nb_points = int(line_header[0])
            except ValueError:
                continue
            coordinates = []
            for i in range(nb_points):
                line = self.file.readline()
                coordinates.append(tuple(map(float, line.rstrip().split())))
            poly = Polyline(coordinates)
            poly.add_attribute(float(line_header[1]))
            yield poly

    def get_polygons(self):
        for poly in self.get_lines():
            if poly.is_closed():
                yield poly

    def get_open_polylines(self):
        for poly in self.get_lines():
            if not poly.is_closed():
                yield poly

    def get_points(self):
        for line in self.file.readlines():
            if line == '\n':
                continue
            try:
                x, y, z = tuple(map(float, line.rstrip().split()))
            except ValueError:
                continue
            yield np.array([x, y, z])


class Write(BlueKenue):
    """"!
    BlueKenue file writer
    """
    I2S_HEADER = ':FileType i2s  ASCII  EnSim 1.0\n'
    I3S_HEADER = ':FileType i3s  ASCII  EnSim 1.0\n'

    def __init__(self, filename):
        super().__init__(filename, 'w')

    def write_header(self, header=[]):
        if header:
            for line in header:
                self.file.write(line)
        else:
            if self.filename.endswith('i2s'):
                self.file.write(Write.I2S_HEADER)
            else:
                self.file.write(Write.I3S_HEADER)
            self.file.write(':EndHeader\n')

    def write_lines(self, lines, attributes):
        for poly, attribute in zip(lines, attributes):
            nb_points = len(list(poly.coords()))
            self.file.write('%d %s\n' % (nb_points, str(attribute)))
            for p in poly.coords():
                self.file.write(' '.join(map(str, p)))
                self.file.write('\n')

    def write_points(self, points):
        for p in points:
            self.file.write(' '.join(map(str, p)))
            self.file.write('\n')
