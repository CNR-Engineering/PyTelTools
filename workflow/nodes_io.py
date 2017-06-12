from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import numpy as np
from workflow.Node import Node, ConfigureDialog, SingleOutputNode, SingleInputNode
from slf import Serafin


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
        configure_dialog = ConfigureDialog(self.get_option_panel(), self.label)
        if configure_dialog.exec_() == QDialog.Accepted:
            self.state = Node.READY
        self.name_box = None
        self.reconfigure()

    def run(self):
        with Serafin.Read(self.filename, 'fr') as resin:
            resin.read_header()

            if not resin.header.is_2d:
                self.state = Node.FAIL
                self.update()
                return
            resin.get_time()
            self.data = (self.filename, resin.header.copy(), resin.time[:])

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
        configure_dialog = ConfigureDialog(self.get_option_panel(), self.label)
        if configure_dialog.exec_() == QDialog.Accepted:
            self.state = Node.READY
        self.name_box = None
        self.reconfigure()

    def run(self):
        if self.in_port.mother.parentItem().data is None:
            self.in_port.mother.parentItem().run()
        input_filename, input_header, input_time = self.in_port.mother.parentItem().data
        if input_filename == self.filename:
            self.state = Node.FAIL
            self.update()
            return
        with Serafin.Read(input_filename, self.scene().language) as resin:
            resin.header = input_header
            resin.time = input_time
            with Serafin.Write(self.filename, self.scene().language, self.scene().overwrite) as resout:
                resout.write_header(input_header)
                for time_index, time_value in enumerate(input_time):
                    values = np.empty((input_header.nb_var, input_header.nb_nodes))
                    for i, var_ID in enumerate(input_header.var_IDs):
                        values[i, :] = resin.read_var_in_frame(time_index, var_ID)
                    resout.write_entire_frame(input_header, time_value, values)
        self.state = Node.SUCCESS
        self.update()


