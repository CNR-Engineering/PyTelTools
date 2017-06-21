from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import numpy as np
from copy import deepcopy
import datetime
import os
import struct
from workflow.Node import Node, SingleOutputNode, SingleInputNode, OneInOneOutNode
from slf import Serafin
from slf.variables import do_calculations_in_frame
import slf.misc as operations
from geom import BlueKenue, Shapefile


class SerafinData:
    def __init__(self, filename, language):
        self.language = language
        self.filename = filename
        self.has_index = False
        self.index = None
        self.triangles = {}
        self.header = None
        self.time = []
        self.time_second = []
        self.start_time = None
        self.name_pattern = None

        self.selected_vars = []
        self.selected_vars_names = {}
        self.selected_time_indices = []
        self.equations = []
        self.us_equation = None
        self.to_single = False

        self.operator = None
        self.metadata = {}

    def read(self):
        with Serafin.Read(self.filename, self.language) as resin:
            resin.read_header()

            if not resin.header.is_2d:
                return False
            resin.get_time()

            self.header = resin.header.copy()
            self.time = resin.time[:]

        if self.header.date is not None:
            year, month, day, hour, minute, second = self.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.time_second = list(map(lambda x: datetime.timedelta(seconds=x), self.time))
        self.selected_vars = self.header.var_IDs[:]
        self.selected_vars_names = {var_id: (var_name, var_unit) for (var_id, var_name, var_unit)
                                    in zip(self.header.var_IDs, self.header.var_names, self.header.var_units)}
        self.selected_time_indices = list(range(len(self.time)))
        return True

    def copy(self):
        copy_data = SerafinData(self.filename, self.language)
        copy_data.has_index = self.has_index
        copy_data.index = self.index
        copy_data.triangles = self.triangles
        copy_data.header = self.header
        copy_data.time = self.time
        copy_data.start_time = self.start_time
        copy_data.time_second = self.time_second
        copy_data.metadata = self.metadata
        copy_data.name_pattern = self.name_pattern

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


class CSVData:
    def __init__(self, filename, header):
        self.filename = filename
        self.table = [header]
        self.name_pattern = None

    def add_row(self, row):
        self.table.append(row)

    def write(self, output_stream, separator):
        for line in self.table:
            output_stream.write(separator.join(line))
            output_stream.write('\n')


class LoadSerafinNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin'
        self.out_port.data_type = 'slf'
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton),
                                  'Load Serafin')
        open_button.setToolTip('<b>Open</b> a .slf file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        self.filename = options[0]
        if not self.filename:
            return
        try:
            with open(self.filename) as f:
                pass
        except FileNotFoundError:
            self.state = Node.NOT_CONFIGURED
            self.filename = ''
            return
        self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(self.filename) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        data = SerafinData(self.filename, self.scene().language)
        if not data.read():
            self.data = None
            self.fail('the input file is not 2D.')
            return
        self.data = data
        self.success(self.data.header.summary())


class WriteSerafinNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.in_port.data_type = 'slf'
        self.out_port.data_type = 'slf'
        self.category = 'Input/Output'
        self.label = 'Write\nSerafin'
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogSaveButton),
                                  'Write Serafin')
        open_button.setToolTip('<b>Write</b> a .slf file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def configure(self):
        if self.scene().name_pattern is None:
            super().configure()
        else:
            QMessageBox.information(None, 'OK', 'Successfully configured using naming pattern in the global options.',
                                    QMessageBox.Ok)
            self.filename = ''
            self.state = Node.READY
            self.update()

    def _open(self):
        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the output file name', '',
                                                  'Serafin Files (*.slf)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            if len(filename) < 5 or filename[-4:] != '.slf':
                filename += '.slf'
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def add_link(self, link):
        self.links.add(link)

    def load(self, options):
        self.filename = options[0]
        if self.filename:
            self.state = Node.READY

    def _run_simple(self, input_data):
        output_header = input_data.default_output_header()
        with Serafin.Read(input_data.filename, self.scene().language) as resin:
            resin.header = input_data.header
            resin.time = input_data.time
            with Serafin.Write(self.filename, input_data.language, True) as resout:
                resout.write_header(output_header)
                for i, time_index in enumerate(input_data.selected_time_indices):
                    values = do_calculations_in_frame(input_data.equations, input_data.us_equation,
                                                      resin, time_index, input_data.selected_vars,
                                                      output_header.np_float_type)
                    resout.write_entire_frame(output_header, input_data.time[time_index], values)

                    self.progress_bar.setValue(100 * (i+1) / len(input_data.selected_time_indices))
                    QApplication.processEvents()

    def _run_max_min_mean(self, input_data):
        selected = [(var, input_data.selected_vars_names[var][0],
                          input_data.selected_vars_names[var][1]) for var in input_data.selected_vars]
        scalars, vectors, additional_equations = operations.scalars_vectors(input_data.header.var_IDs,
                                                                            selected,
                                                                            input_data.us_equation)
        output_header = input_data.header.copy()
        output_header.nb_var = len(scalars) + len(vectors)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in scalars + vectors:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if input_data.to_single:
            output_header.to_single_precision()

        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            has_scalar, has_vector = False, False
            scalar_calculator, vector_calculator = None, None
            if scalars:
                has_scalar = True
                scalar_calculator = operations.ScalarMaxMinMeanCalculator(input_data.operator, input_stream,
                                                                          scalars, input_data.selected_time_indices,
                                                                          additional_equations)
            if vectors:
                has_vector = True
                vector_calculator = operations.VectorMaxMinMeanCalculator(input_data.operator, input_stream,
                                                                          vectors, input_data.selected_time_indices,
                                                                          additional_equations)
            for i, time_index in enumerate(input_data.selected_time_indices):

                if has_scalar:
                    scalar_calculator.max_min_mean_in_frame(time_index)
                if has_vector:
                    vector_calculator.max_min_mean_in_frame(time_index)

                self.progress_bar.setValue(100 * (i+1) / len(input_data.selected_time_indices))
                QApplication.processEvents()

            if has_scalar and not has_vector:
                values = scalar_calculator.finishing_up()
            elif not has_scalar and has_vector:
                values = vector_calculator.finishing_up()
            else:
                values = np.vstack((scalar_calculator.finishing_up(), vector_calculator.finishing_up()))

            with Serafin.Write(self.filename, input_data.language, True) as resout:
                resout.write_header(output_header)
                resout.write_entire_frame(output_header, input_data.time[0], values)

    def _run_arrival_duration(self, input_data):
        conditions, table, time_unit = input_data.metadata['conditions'], \
                                       input_data.metadata['table'], input_data.metadata['time unit']

        output_header = input_data.header.copy()
        output_header.nb_var = 2 * len(conditions)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for row in range(len(table)):
            a_name = table[row][1]
            d_name = table[row][2]
            for name in [a_name, d_name]:
                output_header.var_IDs.append('')
                output_header.var_names.append(bytes(name, 'utf-8').ljust(16))
                output_header.var_units.append(bytes(time_unit.upper(), 'utf-8').ljust(16))
        if input_data.to_single:
            output_header.to_single_precision()

        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            calculators = []

            for i, condition in enumerate(conditions):
                calculators.append(operations.ArrivalDurationCalculator(input_stream, input_data.selected_time_indices,
                                                                        condition))
            for i, index in enumerate(input_data.selected_time_indices[1:]):
                for calculator in calculators:
                    calculator.arrival_duration_in_frame(index)

                self.progress_bar.setValue(100 * (i+1) / len(input_data.selected_time_indices))
                QApplication.processEvents()

            values = np.empty((2*len(conditions), input_data.header.nb_nodes))
            for i, calculator in enumerate(calculators):
                values[2*i, :] = calculator.arrival
                values[2*i+1, :] = calculator.duration

            if time_unit == 'minute':
                values /= 60
            elif time_unit == 'hour':
                values /= 3600
            elif time_unit == 'day':
                values /= 86400
            elif time_unit == 'percentage':
                values *= 100 / (input_data.time[input_data.selected_time_indices[-1]]
                                 - input_data.time[input_data.selected_time_indices[0]])

            with Serafin.Write(self.filename, input_data.language, True) as resout:
                resout.write_header(output_header)
                resout.write_entire_frame(output_header, input_data.time[0], values)

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return

        input_data = self.in_port.mother.parentItem().data
        if input_data.filename == self.filename:
            self.fail('cannot overwrite to the input file.')
            return

        if not self.filename:
            name_pattern = self.scene().name_pattern
            head, tail = os.path.splitext(input_data.filename)
            self.filename = ''.join([head, name_pattern, '.slf'])

        try:
            with open(self.filename, 'w') as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return

        self.progress_bar.setVisible(True)

        if input_data.operator is None:
            self._run_simple(input_data)
        elif input_data.operator in (operations.MAX, operations.MIN, operations.MEAN):
            self._run_max_min_mean(input_data)
        else:
            self._run_arrival_duration(input_data)

        self.success()
        self.data = SerafinData(self.filename, input_data.language)
        self.data.read()


class LoadPolygon2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPolygons'
        self.out_port.data_type = 'polygon 2d'
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton),
                                  'Load Polygon')
        open_button.setToolTip('<b>Open</b> a .shp or .i2s file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a polygon file', '',
                                                  'Polygon file (*.i2s *.shp)',
                                                  QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        self.filename = options[0]
        if self.filename:
            try:
                with open(self.filename) as f:
                    pass
            except FileNotFoundError:
                self.state = Node.NOT_CONFIGURED
                self.filename = ''
                return
            self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(self.filename) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        self.data = []
        is_i2s = self.filename[-4:] == '.i2s'
        if is_i2s:
            with BlueKenue.Read(self.filename) as f:
                f.read_header()
                for poly in f.get_polygons():
                    self.data.append(poly)
        else:
            try:
                for polygon in Shapefile.get_polygons(self.filename):
                    self.data.append(polygon)
            except struct.error:
                self.fail('Inconsistent bytes.')
                return
        if not self.data:
            self.fail('the file does not contain any polygon.')
            return

        self.success('The file contains {} polygon{}.'.format(len(self.data),
                                                              's' if len(self.data) > 1 else ''))


class LoadOpenPolyline2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nOpen\nPolylines'
        self.out_port.data_type = 'polyline 2d'
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton),
                                  'Load 2D open polyline')
        open_button.setToolTip('<b>Open</b> a .shp or .i2s file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a 2D open polyline file', '',
                                                  'Polyline file (*.i2s *.shp)',
                                                  QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        self.filename = options[0]
        if self.filename:
            try:
                with open(self.filename) as f:
                    pass
            except FileNotFoundError:
                self.state = Node.NOT_CONFIGURED
                self.filename = ''
                return
            self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(self.filename) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        self.data = []
        is_i2s = self.filename[-4:] == '.i2s'
        if is_i2s:
            with BlueKenue.Read(self.filename) as f:
                f.read_header()
                for poly in f.get_open_polylines():
                    self.data.append(poly)
        else:
            try:
                for poly in Shapefile.get_open_polylines(self.filename):
                    self.data.append(poly)
            except struct.error:
                self.fail('Inconsistent bytes.')
                return
        if not self.data:
            self.fail('the file does not contain any 2D open polyline.')
            return

        self.success('The file contains {} open line{}.'.format(len(self.data),
                                                                's' if len(self.data) > 1 else ''))


class WriteCSVNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write\nCSV'
        self.in_port.data_type = 'csv'

        self.name_box = None
        self.filename = ''

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogSaveButton),
                                  'Write CSV')
        open_button.setToolTip('<b>Write</b> a .csv file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the output file name', '',
                                                  'CSV Files (*.csv)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            if len(filename) < 5 or filename[-4:] != '.csv':
                filename += '.csv'
            self.filename = filename
            self.name_box.setText(filename)

    def configure(self):
        if self.scene().name_pattern is None:
            super().configure()
        else:
            QMessageBox.information(None, 'OK', 'Successfully configured using naming pattern in the global options.',
                                    QMessageBox.Ok)
            self.filename = ''
            self.state = Node.READY
            self.update()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        self.filename = options[0]
        if self.filename:
            self.state = Node.READY

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        try:
            with open(self.filename, 'w') as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return

        csv = self.in_port.mother.parentItem().data
        if not self.filename:
            name_pattern = self.scene().name_pattern
            head, tail = os.path.splitext(csv.filename)
            self.filename = ''.join([head, name_pattern, '.csv'])

        with open(self.filename, 'w') as output_stream:
            csv.write(output_stream, self.scene().csv_separator)

        self.success()


class LoadPoint2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPoints'
        self.out_port.data_type = 'point 2d'
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton),
                                  'Load 2D points')
        open_button.setToolTip('<b>Open</b> a .shp file')
        open_button.setFixedHeight(30)

        option_panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(open_button)
        self.name_box = QLineEdit(self.filename)
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        layout.addWidget(self.name_box)
        option_panel.setLayout(layout)

        open_button.clicked.connect(self._open)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a point file', '',
                                                  'Shapefile (*.shp)',
                                                  QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        self.filename = options[0]
        if self.filename:
            try:
                with open(self.filename) as f:
                    pass
            except FileNotFoundError:
                self.state = Node.NOT_CONFIGURED
                self.filename = ''
                return
            self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(self.filename) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        self.data = []
        try:
            for point, attribute in Shapefile.get_points(self.filename):
                self.data.append(point)
        except struct.error:
            self.fail('Inconsistent bytes.')
            return
        if not self.data:
            self.fail('the file does not contain any points.')
            return
        self.success('The file contains {} point{}.'.format(len(self.data),
                                                            's' if len(self.data) > 1 else ''))



