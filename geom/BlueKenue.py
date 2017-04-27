from .Polyline import Polyline


class BKi2s:
    def __init__(self, filename, mode):
        self.filename = filename
        self.mode = mode
        self.file = None
        self.header = None

    def __enter__(self):
        self.file = open(self.filename, self.mode)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()


class Read(BKi2s):
    def __init__(self, filename):
        super().__init__(filename, 'r')

    def read_header(self):
        self.header = []
        while True:
            line = self.file.readline().rstrip()
            self.header.append(line)
            if line == ':EndHeader':
                break

    def __iter__(self):
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

            if not poly.is_closed():
                continue
            # return only closed polyline
            yield line_header, poly







