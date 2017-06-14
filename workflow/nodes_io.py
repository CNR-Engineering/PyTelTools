from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import numpy as np
from copy import deepcopy
import datetime

from workflow.Node import Node, SingleOutputNode, SingleInputNode
from slf import Serafin
from slf.variables import do_calculations_in_frame


class LoadSerafinNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index, 'Load Serafin')
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

    def configure(self):
        if super().configure():
            self.name_box = None

    def run(self):
        if self.state == Node.SUCCESS:
            return
        data = SerafinData(self.filename, self.scene().language)
        if not data.read():
            self.data = None
            self.message = 'Failed: Input file is not Telemac 2D.'
            self.state = Node.FAIL
        else:
            self.data = data
            self.message = 'Successful.'
            self.state = Node.SUCCESS
        self.update()


class WriteSerafinNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index, 'Write Serafin')
        self.in_port.data_type = 'slf'

        self.name_box = None
        self.filename = ''

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

    def _open(self):
        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the output file name', '',
                                                  'Serafin Files (*.slf)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if filename:
            if len(filename) < 5 or filename[-4:] != '.slf':
                filename += '.slf'
            self.filename = filename
            self.name_box.setText(filename)

    def configure(self):
        if super().configure():
            self.name_box = None

    def run(self):
        success = super().run_upward()
        if not success:
            self.state = Node.FAIL
            self.update()
            self.message = 'Failed: input failed.'
            return

        input_data = self.in_port.mother.parentItem().data
        if input_data.filename == self.filename:
            self.state = Node.FAIL
            self.message = 'Failed: cannot overwrite to the input file.'
            self.update()
            return
        self.progress_bar.setVisible(True)
        output_header = input_data.header.copy()
        output_header.nb_var = len(input_data.selected_vars)
        output_header.var_IDs, output_header.var_names, \
                             output_header.var_units = [], [], []
        for var_ID, (var_name, var_unit) in input_data.selected_vars_names.items():
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)

        with Serafin.Read(input_data.filename, self.scene().language) as resin:
            resin.header = input_data.header
            resin.time = input_data.time
            with Serafin.Write(self.filename, self.scene().language, self.scene().overwrite) as resout:
                resout.write_header(output_header)
                for i, time_index in enumerate(input_data.selected_time_indices):
                    values = do_calculations_in_frame(input_data.equations, input_data.us_equation,
                                                      resin, time_index, input_data.selected_vars,
                                                      output_header.float_type)
                    resout.write_entire_frame(output_header, input_data.time[time_index], values)

                    self.progress_bar.setValue(100 * (i+1)/len(input_data.selected_time_indices))
                    QApplication.processEvents()

        self.state = Node.SUCCESS
        self.message = 'Successful.'
        self.update()
        self.progress_bar.setVisible(False)


class SerafinData:
    def __init__(self, filename, language):
        self.language = language
        self.filename = filename
        self.has_mesh = False
        self.mesh = None
        self.header = None
        self.time = []
        self.time_second = []
        self.start_time = None

        self.selected_vars = []
        self.selected_vars_names = {}
        self.selected_time_indices = []
        self.equations = []
        self.us_equation = None

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
        copy_data.has_mesh = self.has_mesh
        copy_data.mesh = self.mesh
        copy_data.header = self.header
        copy_data.time = self.time
        copy_data.start_time = self.start_time
        copy_data.time_second = self.time_second

        copy_data.selected_vars = self.selected_vars[:]
        copy_data.selected_vars_names = deepcopy(self.selected_vars_names)
        copy_data.selected_time_indices = self.selected_time_indices[:]
        copy_data.equations = self.equations[:]
        copy_data.us_equation = self.us_equation
        return copy_data

