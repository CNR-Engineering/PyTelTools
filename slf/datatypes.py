from copy import deepcopy
import datetime
import logging

from slf import Serafin

module_logger = logging.getLogger(__name__)


class SerafinData:
    def __init__(self, job_id, filename, language):
        self.job_id = job_id
        self.language = language
        self.filename = filename
        self.index = None
        self.triangles = {}
        self.header = None
        self.time = []
        self.time_second = []
        self.start_time = None

        self.selected_vars = []
        self.selected_vars_names = {}
        self.selected_time_indices = []
        self.equations = []
        self.us_equation = None
        self.to_single = False

        self.operator = None
        self.metadata = {}

    def read(self):
        with Serafin.Read(self.filename, self.language) as input_stream:
            input_stream.read_header()
            input_stream.get_time()

            self.header = input_stream.header.copy()
            self.time = input_stream.time[:]

        if self.header.date is not None:
            try:
                year, month, day, hour, minute, second = self.header.date
                self.start_time = datetime.datetime(year, month, day, hour, minute, second)
            except ValueError:
                module_logger.warning('Date seems invalid, replaced by default date.')
        if self.start_time is None:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.time_second = list(map(lambda x: datetime.timedelta(seconds=x), self.time))
        self.selected_vars = self.header.var_IDs[:]
        self.selected_vars_names = {var_id: (var_name, var_unit) for (var_id, var_name, var_unit)
                                    in zip(self.header.var_IDs, self.header.var_names, self.header.var_units)}
        self.selected_time_indices = list(range(len(self.time)))
        return self.header.is_2d

    def copy(self):
        copy_data = SerafinData(self.job_id, self.filename, self.language)
        copy_data.index = self.index
        copy_data.triangles = self.triangles
        copy_data.header = self.header
        copy_data.time = self.time
        copy_data.start_time = self.start_time
        copy_data.time_second = self.time_second
        copy_data.metadata = self.metadata

        copy_data.selected_vars = self.selected_vars[:]
        copy_data.selected_vars_names = deepcopy(self.selected_vars_names)
        copy_data.selected_time_indices = self.selected_time_indices[:]
        copy_data.equations = self.equations[:]
        copy_data.us_equation = self.us_equation
        copy_data.to_single = self.to_single
        copy_data.operator = self.operator
        return copy_data

    def default_output_header(self):
        output_header = self.header.copy()
        output_header.nb_var = len(self.selected_vars)
        output_header.var_IDs, output_header.var_names, \
                               output_header.var_units = [], [], []
        for var_ID in self.selected_vars:
            var_name, var_unit = self.selected_vars_names[var_ID]
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.to_single:
            output_header.to_single_precision()
        return output_header

    def transform(self, trans):
        transformed_points = [(x, y, 0) for x, y in zip(self.header.x, self.header.y)]
        for t in trans:
            transformed_points = [t(p) for p in transformed_points]
        self.header.x = [p[0] for p in transformed_points]
        self.header.y = [p[1] for p in transformed_points]
        self.index = None
        self.triangles = {}


class CSVData:
    def __init__(self, filename, header=None, out_name='', separator=''):
        self.filename = filename
        self.out_name = ''
        self.metadata = {}
        self.separator = ''

        if header is None:  # read existing file
            self.separator = separator
            self.table = []
            self.out_name = out_name
            with open(out_name, 'r') as f:
                for line in f.readlines():
                    self.table.append(line.rstrip().split(self.separator))
        else:
            self.table = [header]

    def add_row(self, row):
        self.table.append(row)

    def write(self, filename, separator):
        with open(filename, 'w') as output_stream:
            for line in self.table:
                output_stream.write(separator.join(line))
                output_stream.write('\n')
        self.out_name = filename
        self.separator = separator


class PolylineData:
    def __init__(self):
        self.lines = []
        self.fields = []

    def __len__(self):
        return len(self.lines)

    def add_line(self, line):
        self.lines.append(line)

    def set_fields(self, fields):
        self.fields = fields[:]

    def is_empty(self):
        return len(self.lines) == 0


class PointData:
    def __init__(self):
        self.points = []
        self.attributes = []
        self.fields = []
        self.fields_name = []
        self.attributes_decoded = []

    def __len__(self):
        return len(self.points)

    def add_point(self, point):
        self.points.append(point)

    def add_attribute(self, attribute):
        self.attributes.append(attribute)
        decoded = []
        for a in attribute:
            if type(a) == bytes:
                decoded.append(a.decode('latin-1'))
            decoded.append(str(a))
        self.attributes_decoded.append(decoded)

    def set_fields(self, fields):
        self.fields = fields[:]
        for f in fields:
            name = f[0]
            if type(name) == bytes:
                self.fields_name.append(name.decode('latin-1'))
            else:
                self.fields_name.append(name)

    def is_empty(self):
        return len(self.points) == 0

