import os
import struct

import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import slf.misc as operations
from geom import BlueKenue, Shapefile
from slf import Serafin
from slf.datatypes import SerafinData, PointData, PolylineData
from slf.interpolation import MeshInterpolator
from slf.variables_2d import do_2d_calculations_in_frame
from slf.variables_3d import do_3d_calculations_in_frame
from workflow.Node import Node, SingleInputNode, SingleOutputNode, OneInOneOutNode
from workflow.util import LoadSerafinDialog, logger, OutputOptionPanel, GeomOutputOptionPanel, VtkOutputOptionPanel, \
                          process_output_options, process_geom_output_options, process_vtk_output_options, \
                          validate_input_options, validate_output_options


class LoadSerafin2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin 2D'
        self.out_port.data_type = ('slf', 'slf geom')

        self.dir_path = ''
        self.slf_name = ''
        self.job_id = ''
        self.data = None

    def configure(self, check=None):
        old_options = (self.dir_path, self.slf_name, self.job_id)
        dlg = LoadSerafinDialog(old_options)
        if dlg.exec_() == QDialog.Accepted:
            self.state = Node.READY
            self.dir_path, self.slf_name, self.job_id = dlg.dir_path, dlg.slf_name, dlg.job_id
            self.update()
            self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.dir_path, self.slf_name, self.job_id])

    def load(self, options):
        self.dir_path, self.slf_name, self.job_id = options
        if not self.dir_path:
            return
        try:
            with open(os.path.join(self.dir_path, self.slf_name)) as f:
                pass
        except FileNotFoundError:
            self.state = Node.NOT_CONFIGURED
            self.dir_path = ''
            self.slf_name = ''
            self.job_id = ''
            return
        self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(os.path.join(self.dir_path, self.slf_name)) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        data = SerafinData(self.job_id, os.path.join(self.dir_path, self.slf_name), self.scene().language)
        is_2d = data.read()
        if not is_2d:
            self.data = None
            self.fail('the input file is not 2D.')
            return
        self.data = data
        self.success()


class WriteSerafinNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.in_port.data_type = ('slf out', 'slf', 'slf 3d')
        self.out_port.data_type = ('slf', 'slf 3d')
        self.category = 'Input/Output'
        self.label = 'Write\nSerafin'
        self.filename = ''

        self.panel = None
        self.suffix = '_result'
        self.in_source_folder = True
        self.dir_path = ''
        self.double_name = False
        self.overwrite = False

    def get_option_panel(self):
        return self.panel

    def configure(self, check=None):
        old_options = (self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite)
        self.panel = OutputOptionPanel(old_options)
        if super().configure(self.panel.check):
            self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = self.panel.get_options()
            self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.suffix,
                         str(int(self.in_source_folder)), self.dir_path,
                         str(int(self.double_name)), str(int(self.overwrite))])

    def reconfigure(self):
        super().reconfigure()
        self.reconfigure_downward()

    def load(self, options):
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options)
        if success:
            self.state = Node.READY
            self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = \
                suffix, in_source_folder, dir_path, double_name, overwrite

    def _run_simple(self, input_data):
        output_header = input_data.default_output_header()
        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            with Serafin.Write(self.filename, input_data.language) as output_stream:
                output_stream.write_header(output_header)
                for i, time_index in enumerate(input_data.selected_time_indices):
                    if output_header.is_2d:
                        values = do_2d_calculations_in_frame(input_data.equations, input_data.us_equation,
                                                             input_stream, time_index, input_data.selected_vars,
                                                             output_header.np_float_type)
                    else:
                        values = do_3d_calculations_in_frame(input_data.equations,
                                                             input_stream, time_index, input_data.selected_vars,
                                                             output_header.np_float_type)
                    output_stream.write_entire_frame(output_header, input_data.time[time_index], values)

                    self.progress_bar.setValue(100 * (i+1) / len(input_data.selected_time_indices))
                    QApplication.processEvents()
        self.success('Output saved to {}.'.format(self.filename))
        return True

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

            with Serafin.Write(self.filename, input_data.language) as output_stream:
                output_stream.write_header(output_header)
                output_stream.write_entire_frame(output_header, input_data.time[0], values)
        self.success('Output saved to {}.'.format(self.filename))
        return True

    def _run_synch_max(self, input_data):
        selected_vars = [var for var in input_data.selected_vars if var in input_data.header.var_IDs]
        output_header = input_data.header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID in selected_vars:
            var_name, var_unit = input_data.selected_vars_names[var_ID]
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if input_data.to_single:
            output_header.to_single_precision()

        nb_frames = len(input_data.selected_time_indicies)
        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time

            calculator = operations.SynchMaxCalculator(input_stream, selected_vars, input_data.selected_time_indicies,
                                                       input_data.metadata['var'])

            for i, time_index in enumerate(input_data.selected_time_indicies[1:]):
                calculator.synch_max_in_frame(time_index)

                self.progress_bar.setValue(100 * (i+1) / nb_frames)
                QApplication.processEvents()

            values = calculator.finishing_up()
            with Serafin.Write(self.filename, input_data.language) as output_stream:
                output_stream.write_header(output_header)
                output_stream.write_entire_frame(output_header, input_data.time[0], values)
        self.success('Output saved to {}.'.format(self.filename))
        return True

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

            with Serafin.Write(self.filename, input_data.language) as output_stream:
                output_stream.write_header(output_header)
                output_stream.write_entire_frame(output_header, input_data.time[0], values)
        self.success('Output saved to {}.'.format(self.filename))
        return True

    def _run_project_mesh(self, first_input):
        operation_type = first_input.operator
        second_input = first_input.metadata['operand']

        if second_input.filename == self.filename:
            self.fail('cannot overwrite to the input file.')
            return

        # common vars
        first_vars = [var for var in first_input.header.var_IDs if var in first_input.selected_vars]
        second_vars = [var for var in second_input.header.var_IDs if var in second_input.selected_vars]
        common_vars = []
        for var in first_vars:
            if var in second_vars:
                common_vars.append(var)
        if not common_vars:
            self.fail('the two input files do not share common variables.')
            return False

        # common frames
        first_frames = [first_input.start_time + first_input.time_second[i]
                        for i in first_input.selected_time_indices]
        second_frames = [second_input.start_time + second_input.time_second[i]
                         for i in second_input.selected_time_indices]
        common_frames = []
        for first_index, first_frame in zip(first_input.selected_time_indices, first_frames):
            for second_index, second_frame in zip(second_input.selected_time_indices, second_frames):
                if first_frame == second_frame:
                    common_frames.append((first_index, second_index))
        if not common_frames:
            self.fail('the two input files do not share common time frames.')
            return False

        # construct output header
        output_header = first_input.header.copy()
        output_header.nb_var = len(common_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var in common_vars:
            name, unit = first_input.selected_vars_names[var]
            output_header.var_IDs.append(var)
            output_header.var_names.append(name)
            output_header.var_units.append(unit)
        if first_input.to_single:
            output_header.to_single_precision()

        # map points of A onto mesh B
        mesh = MeshInterpolator(second_input.header, False)

        if second_input.triangles:
            mesh.index = second_input.index
            mesh.triangles = second_input.triangles
        else:
            self.construct_mesh(mesh)
            second_input.index = mesh.index
            second_input.triangles = mesh.triangles

        is_inside, point_interpolators = mesh.get_point_interpolators(list(zip(first_input.header.x,
                                                                               first_input.header.y)))

        # run the calculator
        with Serafin.Read(first_input.filename, first_input.language) as first_in:
            first_in.header = first_input.header
            first_in.time = first_input.time

            with Serafin.Read(second_input.filename, second_input.language) as second_in:
                second_in.header = second_input.header
                second_in.time = second_input.time

                calculator = operations.ProjectMeshCalculator(first_in, second_in, common_vars, is_inside,
                                                              point_interpolators, common_frames, operation_type)

                with Serafin.Write(self.filename, first_input.language) as out_stream:
                    out_stream.write_header(output_header)

                    for i, (first_time_index, second_time_index) in enumerate(calculator.time_indices):
                        values = calculator.operation_in_frame(first_time_index, second_time_index)
                        out_stream.write_entire_frame(output_header,
                                                      calculator.first_in.time[first_time_index], values)

                        self.progress_bar.setValue(100 * (i+1) / len(common_frames))
                        QApplication.processEvents()

        self.success('Output saved to {}.\nThe two files has {} common variables and {} common frames.\n'
                     'The mesh A has {} / {} nodes inside the mesh B.'.format(self.filename,
                                                                              len(common_vars), len(common_frames),
                                                                              sum(is_inside),
                                                                              first_input.header.nb_nodes))
        return True

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return

        input_data = self.in_port.mother.parentItem().data
        self.filename = process_output_options(input_data.filename, input_data.job_id, '.slf',
                                               self.suffix, self.in_source_folder, self.dir_path, self.double_name)
        if not self.overwrite:
            if os.path.exists(self.filename):
                try:
                    with open(self.filename, 'r') as f:
                        pass
                except PermissionError:
                    self.fail('Access denied when reloading existing file.')

                self.data = SerafinData(input_data.job_id, self.filename, input_data.language)
                self.data.read()
                self.success('Reload existing file.')
                return

        try:
            with open(self.filename, 'w') as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return

        self.progress_bar.setVisible(True)

        # do the actual calculation
        if input_data.operator is None:
            success = self._run_simple(input_data)
        elif input_data.operator in (operations.MAX, operations.MIN, operations.MEAN):
            success = self._run_max_min_mean(input_data)
        elif input_data.operator in (operations.PROJECT, operations.DIFF, operations.REV_DIFF,
                                     operations.MAX_BETWEEN, operations.MIN_BETWEEN):
            success = self._run_project_mesh(input_data)
        elif input_data.operator == operations.SYNCH_MAX:
            success = self._run_synch_max(input_data)
        else:
            success = self._run_arrival_duration(input_data)

        if success:  # reload the output file
            self.data = SerafinData(input_data.job_id, self.filename, input_data.language)
            self.data.read()


class LoadPolygon2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPolygons'
        self.out_port.data_type = ('polygon 2d',)
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

    def configure(self, check=None):
        if super().configure():
            if not self.filename:
                self.state = Node.NOT_CONFIGURED
                self.update()
            else:
                self.reconfigure_downward()

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a polygon file', '',
                                                  'Polygon file (*.i2s *.shp)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        success, filename = validate_input_options(options)
        if success:
            self.filename = filename
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
        self.data = PolylineData()
        is_i2s = self.filename[-4:] == '.i2s'
        if is_i2s:
            with BlueKenue.Read(self.filename) as f:
                f.read_header()
                for poly in f.get_polygons():
                    self.data.add_line(poly)
            self.data.set_fields(['Value'])
        else:
            try:
                for polygon in Shapefile.get_polygons(self.filename):
                    self.data.add_line(polygon)
            except struct.error:
                self.fail('Inconsistent bytes.')
                return
            self.data.set_fields(Shapefile.get_all_fields(self.filename))

        if self.data.is_empty():
            self.fail('the file does not contain any polygon.')
            return

        self.success('The file contains {} polygon{}.'.format(len(self.data),
                                                              's' if len(self.data) > 1 else ''))


class LoadOpenPolyline2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nOpen\nPolylines'
        self.out_port.data_type = ('polyline 2d',)
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
                                                  'Polyline file (*.i2s *.shp)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def configure(self, check=None):
        if super().configure():
            if not self.filename:
                self.state = Node.NOT_CONFIGURED
                self.update()
            else:
                self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        success, filename = validate_input_options(options)
        if success:
            self.filename = filename
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
        self.data = PolylineData()
        is_i2s = self.filename[-4:] == '.i2s'
        if is_i2s:
            with BlueKenue.Read(self.filename) as f:
                f.read_header()
                for poly in f.get_open_polylines():
                    self.data.add_line(poly)
            self.data.set_fields(['Value'])
        else:
            try:
                for poly in Shapefile.get_open_polylines(self.filename):
                    self.data.add_line(poly)
            except struct.error:
                self.fail('Inconsistent bytes.')
                return
            self.data.set_fields(Shapefile.get_all_fields(self.filename))

        if self.data.is_empty():
            self.fail('the file does not contain any 2D open polyline.')
            return

        self.success('The file contains {} open line{}.'.format(len(self.data),
                                                                's' if len(self.data) > 1 else ''))


class LoadPoint2DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPoints'
        self.out_port.data_type = ('point 2d',)
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
                                                  'Shapefile (*.shp)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def configure(self, check=None):
        if super().configure():
            if not self.filename:
                self.state = Node.NOT_CONFIGURED
                self.update()
            else:
                self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        success, filename = validate_input_options(options)
        if success:
            self.filename = filename
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
        self.data = PointData()
        try:
            for point, attribute in Shapefile.get_points(self.filename):
                self.data.add_point(point)
                self.data.add_attribute(attribute)
        except struct.error:
            self.fail('Inconsistent bytes.')
            return
        self.data.set_fields(Shapefile.get_all_fields(self.filename))
        if self.data.is_empty():
            self.fail('the file does not contain any point.')
            return
        self.success('The file contains {} point{}.'.format(len(self.data),
                                                            's' if len(self.data) > 1 else ''))


class LoadReferenceSerafinNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nReference\nSerafin'
        self.out_port.data_type = ('slf reference',)
        self.name_box = None
        self.filename = ''
        self.data = None

    def get_option_panel(self):
        open_button = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton),
                                  'Load Single Frame Serafin')
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
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a .slf ile', '',
                                                  'Serafin file (*.slf)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            self.filename = filename
            self.name_box.setText(filename)

    def configure(self, check=None):
        if super().configure():
            if not self.filename:
                self.state = Node.NOT_CONFIGURED
                self.update()
            else:
                self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename])

    def load(self, options):
        success, filename = validate_input_options(options)
        if success:
            self.filename = filename
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
        data = SerafinData('', self.filename, self.scene().language)
        is_2d = data.read()
        if not is_2d:
            self.fail('the input file is not 2D.')
            return
        if len(data.time) != 1:
            self.fail('the input file has more than one frame.')
            return
        self.data = data
        self.success()


class LoadSerafin3DNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin 3D'
        self.out_port.data_type = ('slf 3d',)

        self.dir_path = ''
        self.slf_name = ''
        self.job_id = ''
        self.data = None

    def configure(self, check=None):
        old_options = (self.dir_path, self.slf_name, self.job_id)
        dlg = LoadSerafinDialog(old_options)
        if dlg.exec_() == QDialog.Accepted:
            self.state = Node.READY
            self.dir_path, self.slf_name, self.job_id = dlg.dir_path, dlg.slf_name, dlg.job_id
            self.update()
            self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.dir_path, self.slf_name, self.job_id])

    def load(self, options):
        self.dir_path, self.slf_name, self.job_id = options
        if not self.dir_path:
            return
        try:
            with open(os.path.join(self.dir_path, self.slf_name)) as f:
                pass
        except FileNotFoundError:
            self.state = Node.NOT_CONFIGURED
            self.dir_path = ''
            self.slf_name = ''
            self.job_id = ''
            return
        self.state = Node.READY

    def run(self):
        if self.state == Node.SUCCESS:
            return
        try:
            with open(os.path.join(self.dir_path, self.slf_name)) as f:
                pass
        except PermissionError:
            self.fail('Access denied.')
            return
        data = SerafinData(self.job_id, os.path.join(self.dir_path, self.slf_name), self.scene().language)
        is_2d = data.read()
        if is_2d:
            self.data = None
            self.fail('the input file is not 3D.')
            return
        self.data = data
        self.success()


class WriteLandXMLNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.in_port.data_type = ('slf geom',)
        self.category = 'Input/Output'
        self.label = 'Write\nLandXML'
        self.state = Node.READY

        self.panel = None
        self.suffix = '_scalar_layer'
        self.double_name = False
        self.overwrite = False
        self.in_source_folder = True
        self.dir_path = ''

    def get_option_panel(self):
        return self.panel

    def configure(self, check=None):
        old_options = (self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite)
        self.panel = GeomOutputOptionPanel(old_options)
        if super().configure(self.panel.check):
            self.suffix, self.in_source_folder, self.dir_path, \
                         self.double_name, self.overwrite = self.panel.get_options()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.suffix,
                         str(int(self.in_source_folder)), self.dir_path,
                         str(int(self.double_name)), str(int(self.overwrite))])

    def load(self, options):
        logger.debug('Calling WriteLandXMLNode.load with options:')
        logger.debug(options)
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options)
        if success:
            self.state = Node.READY
            self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = \
                suffix, in_source_folder, dir_path, double_name, overwrite

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return

        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if len(input_data.selected_time_indices) != 1:
            self.fail('the input data has more than one frame')
            return
        available_var = [var for var in input_data.selected_vars if var in input_data.header.var_IDs]
        if len(available_var) == 0:
            self.fail('no variable available')
            return
        elif len(available_var) > 1:
            self.fail('the input data has more than one variable')
            return
        selected_frame = input_data.selected_time_indices[0]
        selected_var = available_var[0]

        filename = process_geom_output_options(input_data.filename, input_data.job_id, '.xml',
                                               self.suffix, self.in_source_folder, self.dir_path, self.double_name)

        if not self.overwrite:
            if os.path.exists(filename):
                self.success('File already exists.')
                return
        try:
            with open(filename, 'w') as f:
                pass
        except PermissionError:
            try:
                os.remove(filename)
            except PermissionError:
                pass
            self.fail('Access denied.')
            return

        operations.slf_to_xml(input_data.filename, input_data.header, filename, selected_var, selected_frame)

        self.success()


class WriteShpNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.in_port.data_type = ('slf geom',)
        self.category = 'Input/Output'
        self.label = 'Write shp'
        self.state = Node.READY

        self.panel = None
        self.suffix = '_layer'
        self.double_name = False
        self.overwrite = False
        self.in_source_folder = True
        self.dir_path = ''

    def get_option_panel(self):
        return self.panel

    def configure(self, check=None):
        old_options = (self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite)
        self.panel = GeomOutputOptionPanel(old_options)
        if super().configure(self.panel.check):
            self.suffix, self.in_source_folder, self.dir_path, \
                         self.double_name, self.overwrite = self.panel.get_options()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.suffix,
                         str(int(self.in_source_folder)), self.dir_path,
                         str(int(self.double_name)), str(int(self.overwrite))])

    def load(self, options):
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options)
        if success:
            self.state = Node.READY
            self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = \
                suffix, in_source_folder, dir_path, double_name, overwrite

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return

        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if len(input_data.selected_time_indices) != 1:
            self.fail('the input data has more than one frame')
            return
        available_vars = [var for var in input_data.selected_vars if var in input_data.header.var_IDs]
        if len(available_vars) == 0:
            self.fail('no variable available')
            return
        selected_frame = input_data.selected_time_indices[0]

        filename = process_geom_output_options(input_data.filename, input_data.job_id, '.shp',
                                               self.suffix, self.in_source_folder, self.dir_path, self.double_name)

        if not self.overwrite:
            if os.path.exists(filename):
                self.success('File already exists.')
                return
        try:
            with open(filename, 'w') as f:
                pass
        except PermissionError:
            try:
                os.remove(filename)
            except PermissionError:
                pass
            self.fail('Access denied.')
            return

        operations.slf_to_shp(input_data.filename, input_data.header, filename, available_vars, selected_frame)

        self.success()


class WriteVtkNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.in_port.data_type = ('slf 3d',)
        self.category = 'Input/Output'
        self.label = 'Write vtk'
        self.state = Node.READY

        self.panel = None
        self.suffix = '_vtk'
        self.double_name = False
        self.overwrite = False
        self.in_source_folder = True
        self.dir_path = ''

    def get_option_panel(self):
        return self.panel

    def configure(self, check=None):
        old_options = (self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite)
        self.panel = VtkOutputOptionPanel(old_options)
        if super().configure(self.panel.check):
            self.suffix, self.in_source_folder, self.dir_path, \
                         self.double_name, self.overwrite = self.panel.get_options()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.suffix,
                         str(int(self.in_source_folder)), self.dir_path,
                         str(int(self.double_name)), str(int(self.overwrite))])

    def load(self, options):
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options)
        if success:
            self.state = Node.READY
            self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = \
                suffix, in_source_folder, dir_path, double_name, overwrite

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return

        input_data = self.in_port.mother.parentItem().data
        if input_data.header.is_2d:
            self.fail('the input file is not 3D')
            return
        if 'Z' not in input_data.header.var_IDs:
            self.fail('the variable Z is not found')
            return

        available_vars = [var for var in input_data.selected_vars if var in input_data.header.var_IDs and var != 'Z']
        if len(available_vars) == 0:
            self.fail('no variable available')
            return

        # construct vtk filenames
        filenames = []
        skip = []
        for time_index in input_data.selected_time_indices:
            filename = process_vtk_output_options(input_data.filename, input_data.job_id, time_index,
                                                   self.suffix, self.in_source_folder, self.dir_path, self.double_name)
            filenames.append(filename)
            if not self.overwrite:
                if os.path.exists(filename):
                    skip.append(True)
                else:
                    skip.append(False)
            else:
                try:
                    with open(filename, 'w') as f:
                        pass
                except PermissionError:
                    try:
                        os.remove(filename)
                    except PermissionError:
                        pass
                    self.fail('Access denied.')
                    return
                skip.append(False)
        if all(skip):
            self.success('File already exists.')
            return

        # separate vectors from scalars
        scalars, vectors, vtk_var_names = operations.detect_vector_triples(available_vars,
                                                                           input_data.selected_vars_names,
                                                                           input_data.language)

        # write vtk
        for to_skip, filename, time_index in zip(skip, filenames, input_data.selected_time_indices):
            if to_skip:
                continue
            operations.slf_to_vtk(input_data.filename, input_data.header, filename,
                                  scalars, vectors, vtk_var_names, time_index)

        self.success()

