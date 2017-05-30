import sys
import logging
import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import numpy as np

from gui.util import LoadMeshDialog, OutputProgressDialog, OutputThread, \
    TableWidgetDragRows, QPlainTextEditLogger, TelToolWidget, testOpen, handleOverwrite
from slf import Serafin


class ProjectMeshThread(OutputThread):
    def __init__(self, first_in, second_in, out_stream, out_header, is_inside, point_interpolators,
                 time_indices, operation_type):
        super().__init__()

        self.first_in = first_in
        self.second_in = second_in
        self.out_stream = out_stream
        self.out_header = out_header
        self.is_inside = is_inside
        self.point_interpolators = point_interpolators
        self.time_indices = time_indices
        self.operation_type = operation_type

        self.nb_frames = len(time_indices)
        self.nb_var = self.out_header.nb_var
        self.nb_nodes = self.out_header.nb_nodes

    def read_values_in_frame(self, time_index, read_second):
        values = []
        for i, var_ID in enumerate(self.out_header.var_IDs):
            if read_second:
                values.append(self.second_in.read_var_in_frame(time_index, var_ID))
            else:
                values.append(self.first_in.read_var_in_frame(time_index, var_ID))
        return values

    def interpolate(self, values):
        interpolated_values = []
        for index_node in range(self.nb_nodes):
            if not self.is_inside[index_node]:
                interpolated_values.append(np.nan)
            else:
                (i, j, k), interpolator = self.point_interpolators[index_node]
                interpolated_values.append(interpolator.dot(values[[i, j, k]]))
        return interpolated_values

    def operation_in_frame(self, first_time_index, second_time_index):
        if self.operation_type == 0:  # projection
            second_values = self.read_values_in_frame(second_time_index, True)
            return np.array([self.interpolate(second_values[i]) for i in range(self.nb_var)])

        first_values = np.array(self.read_values_in_frame(first_time_index, False))
        second_values = self.read_values_in_frame(second_time_index, True)

        if self.operation_type == 1:  # A - B
            return np.array([first_values[i] - np.array(self.interpolate(second_values[i]))
                             for i in range(self.nb_var)])
        elif self.operation_type == 2:  # B - A
            return np.array([np.array(self.interpolate(second_values[i])) - first_values[i]
                             for i in range(self.nb_var)])
        elif self.operation_type == 3:  # max
            return np.array([np.maximum(self.interpolate(second_values[i]), first_values[i])
                             for i in range(self.nb_var)])
        else:  # min
            return np.array([np.minimum(self.interpolate(second_values[i]), first_values[i])
                             for i in range(self.nb_var)])

    def run(self):
        for i, (first_time_index, second_time_index) in enumerate(self.time_indices):
            if self.canceled:
                return
            values = self.operation_in_frame(first_time_index, second_time_index)
            self.out_stream.write_entire_frame(self.out_header,
                                               self.first_in.time[first_time_index], values)

            self.tick.emit(5 + 95 * (i+1) / self.nb_frames)
            QApplication.processEvents()


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.first_language = 'fr'
        self.second_language = 'fr'
        self.first_filename = None
        self.second_filename = None
        self.first_header = None
        self.second_header = None
        self.first_time = []
        self.second_time = []
        self.first_start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.second_start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.common_frames = []

        self.second_mesh = None
        self.is_inside = []
        self.point_interpolators = []

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        self.frenchButton.setChecked(True)

        # create the button open the reference file
        self.btnOpenFirst = QPushButton('Load\nFile A', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenFirst.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenFirst.setFixedSize(105, 50)

        # create the button open the test file
        self.btnOpenSecond = QPushButton('Load\nFile B', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenSecond.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSecond.setFixedSize(105, 50)
        self.btnOpenSecond.setEnabled(False)

        # create some text fields displaying the IO files info
        self.firstNameBox = QLineEdit()
        self.firstNameBox.setReadOnly(True)
        self.firstNameBox.setFixedHeight(30)
        self.firstNameBox.setMinimumWidth(600)
        self.firstSummaryTextBox = QPlainTextEdit()
        self.firstSummaryTextBox.setMinimumHeight(40)
        self.firstSummaryTextBox.setMaximumHeight(50)
        self.firstSummaryTextBox.setMinimumWidth(600)
        self.firstSummaryTextBox.setReadOnly(True)
        self.secondNameBox = QLineEdit()
        self.secondNameBox.setReadOnly(True)
        self.secondNameBox.setFixedHeight(30)
        self.secondNameBox.setMinimumWidth(600)
        self.secondSummaryTextBox = QPlainTextEdit()
        self.secondSummaryTextBox.setReadOnly(True)
        self.secondSummaryTextBox.setMinimumHeight(40)
        self.secondSummaryTextBox.setMaximumHeight(50)
        self.secondSummaryTextBox.setMinimumWidth(600)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenFirst.clicked.connect(self.btnOpenFirstEvent)
        self.btnOpenSecond.clicked.connect(self.btnOpenSecondEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 20))
        mainLayout.setSpacing(15)

        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpenFirst)
        hlayout.addWidget(self.btnOpenSecond)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     File A'), 1, 1)
        glayout.addWidget(self.firstNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.firstSummaryTextBox, 2, 2)
        glayout.addWidget(QLabel('     File B'), 3, 1)
        glayout.addWidget(self.secondNameBox, 3, 2)
        glayout.addWidget(QLabel('     Summary'), 4, 1)
        glayout.addWidget(self.secondSummaryTextBox, 4, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setVerticalSpacing(10)
        mainLayout.addLayout(glayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)
        self.setLayout(mainLayout)

    def _reinitFirst(self, filename):
        if not self.frenchButton.isChecked():
            self.first_language = 'en'
        else:
            self.first_language = 'fr'
        self.first_filename = filename
        self.firstNameBox.setText(filename)
        self.firstSummaryTextBox.clear()
        self.first_header = None
        self.btnOpenSecond.setEnabled(False)
        self.first_start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

    def _reinitSecond(self, filename):
        if not self.frenchButton.isChecked():
            self.second_language = 'en'
        else:
            self.second_language = 'fr'
        self.second_header = None
        self.second_mesh = None
        self.second_filename = filename
        self.secondNameBox.setText(filename)
        self.secondSummaryTextBox.clear()
        self.second_start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.parent.reset()

    def _reinitStartTime(self):
        if self.first_header.date is not None:
            year, month, day, hour, minute, second = self.first_header.date
            self.first_start_time = datetime.datetime(year, month, day, hour, minute, second)
        if self.second_header is not None:
            if self.second_header.date is not None:
                year, month, day, hour, minute, second = self.second_header.date
                self.second_start_time = datetime.datetime(year, month, day, hour, minute, second)

    def _reinitCommonFrames(self):
        first_frames = list(map(lambda x: self.first_start_time + datetime.timedelta(seconds=x), self.first_time))
        second_frames = list(map(lambda x: self.second_start_time + datetime.timedelta(seconds=x), self.second_time))
        self.common_frames = []
        for first_index, first_frame in enumerate(first_frames):
            for second_index, second_frame in enumerate(second_frames):
                if first_frame == second_frame:
                    self.common_frames.append((first_index, second_index))

    def btnOpenFirstEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitFirst(filename)

        with Serafin.Read(self.first_filename, self.first_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # update the file summary
            self.firstSummaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.first_header = resin.header.copy()
            self.first_time = resin.time[:]

        self.btnOpenSecond.setEnabled(True)
        self._reinitStartTime()

        if self.second_header is not None:
            keep_second = self.parent.resetFirst()
            if not keep_second:
                self._reinitSecond('')
            else:
                self._reinitCommonFrames()
                self.parent.getSecond(True, [])

    def btnOpenSecondEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitSecond(filename)

        with Serafin.Read(self.second_filename, self.second_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # check if the second file has common variables with the first file
            common_vars = [(var_ID, var_names, var_unit) for var_ID, var_names, var_unit
                           in zip(self.first_header.var_IDs, self.first_header.var_names, self.first_header.var_units)
                           if var_ID in resin.header.var_IDs]
            if not common_vars:
                QMessageBox.critical(self, 'Error', 'No common variable with file A.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()
            # copy to avoid reading the same data in the future
            self.second_header = resin.header.copy()
            self.second_time = resin.time[:]

            # check if the second file has common frames with the first file
            self._reinitStartTime()
            self._reinitCommonFrames()

            if not self.common_frames:
                QMessageBox.critical(self, 'Error', 'No common frame with file A.',
                                     QMessageBox.Ok)
                return

            # record the mesh
            self.parent.inDialog()
            meshLoader = LoadMeshDialog('interpolation', resin.header)
            self.second_mesh = meshLoader.run()
            # locate all points of the first mesh in the second mesh
            self.is_inside, self.point_interpolators \
                = self.second_mesh.get_point_interpolators(list(zip(self.first_header.x, self.first_header.y)))

            self.parent.outDialog()
            if meshLoader.thread.canceled:
                return

            # update the file summary
            self.secondSummaryTextBox.appendPlainText(resin.get_summary())

        self.parent.getSecond(False, common_vars)


class SubmitTab(QWidget):
    def __init__(self, inputTab, parent):
        super().__init__()
        self.input = inputTab
        self.parent = parent

        self._initWidgets()
        self._bindEvents()
        self._setLayout()

    def _initWidgets(self):
        # create a text field for mesh intersection info display
        self.infoBox = QPlainTextEdit()
        self.infoBox.setFixedHeight(60)
        self.infoBox.setReadOnly(True)

        # create two 3-column tables for variables selection
        self.firstTable = TableWidgetDragRows()
        self.secondTable = TableWidgetDragRows()
        for tw in [self.firstTable, self.secondTable]:
            tw.setColumnCount(3)
            tw.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
            hh = tw.horizontalHeader()
            hh.setDefaultSectionSize(110)
            tw.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tw.setMaximumHeight(800)
            tw.setMinimumHeight(150)

        # create combo box widgets for choosing the operation
        self.operationBox = QComboBox()
        self.operationBox.setFixedSize(400, 30)
        for op in ['Project B on A', 'B - A', 'A - B', 'max(A, B)', 'min(A, B)']:
            self.operationBox.addItem(op)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(105, 50)

    def _bindEvents(self):
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(1, 10))
        mainLayout.addWidget(self.infoBox)
        mainLayout.addItem(QSpacerItem(1, 15))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))

        vlayout = QVBoxLayout()
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.firstTable)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))

        vlayout = QVBoxLayout()
        lb = QLabel('Output variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.secondTable)

        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(30, 1))

        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(50, 20))
        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select an operation'), 1, 1)
        glayout.addWidget(self.operationBox, 1, 2)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.setAlignment(glayout, Qt.AlignTop | Qt.AlignLeft)
        mainLayout.addItem(QSpacerItem(50, 20))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.singlePrecisionBox)
        hlayout.addItem(QSpacerItem(50, 10))
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _initVarTables(self, common_vars):
        for i, (var_ID, var_name, var_unit) in enumerate(common_vars):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var_ID.strip())
            name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, id_item)
            self.firstTable.setItem(i, 1, name_item)
            self.firstTable.setItem(i, 2, unit_item)

    def _getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append((self.secondTable.item(i, 0).text(),
                             bytes(self.secondTable.item(i, 1).text(), 'utf-8').ljust(16),
                             bytes(self.secondTable.item(i, 2).text(), 'utf-8').ljust(16)))
        return selected

    def _getOutputHeader(self):
        selected_vars = self._getSelectedVariables()
        output_header = self.input.first_header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in selected_vars:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def _updateInfo(self):
        self.infoBox.clear()
        self.infoBox.appendPlainText('The two files has {} common variables and {} common frames.\n'
                                     'The mesh A has {} / {} nodes inside the mesh B.'.format(
                                     self.firstTable.rowCount() + self.secondTable.rowCount(),
                                     len(self.input.common_frames),
                                     sum(self.input.is_inside), self.input.first_header.nb_nodes))

    def reset(self):
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def resetFirst(self):
        common_vars = [(var_ID, var_name, var_unit) for var_ID, var_name, var_unit
                        in zip(self.input.first_header.var_IDs, self.input.first_header.var_names,
                               self.input.first_header.var_units)
                        if var_ID in self.input.second_header.var_IDs]
        if not common_vars:
            self.firstTable.setRowCount(0)
            self.secondTable.setRowCount(0)
            return False
        else:
            # recover, if possible, old variable selection
            old_selected = self._getSelectedVariables()
            self.firstTable.setRowCount(0)
            self.secondTable.setRowCount(0)

            self._initVarTables([(var_ID, var_name, var_unit) for var_ID, var_name, var_unit in common_vars
                                 if var_ID not in old_selected])
            for var_ID, var_name, var_unit in common_vars:
                if var_ID in old_selected:
                    row = self.secondTable.rowCount()
                    self.secondTable.insertRow(row)
                    id_item = QTableWidgetItem(var_ID.strip())
                    name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
                    unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
                    self.secondTable.setItem(row, 0, id_item)
                    self.secondTable.setItem(row, 1, name_item)
                    self.secondTable.setItem(row, 2, unit_item)
            return True

    def getSecond(self, old_second, common_vars):
        if not old_second:
            self.firstTable.setRowCount(0)
            self.secondTable.setRowCount(0)
            self._initVarTables(common_vars)
            if self.input.second_header.float_type == 'd':
                self.singlePrecisionBox.setEnabled(True)
        self._updateInfo()

    def btnSubmitEvent(self):
        if self.secondTable.rowCount() == 0:
            QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                 QMessageBox.Ok)
            return

        # create the save file dialog
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        options |= QFileDialog.DontConfirmOverwrite
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  'Serafin Files (*.slf)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.slf':
            filename += '.slf'

        # overwrite to the input file is forbidden
        if filename == self.input.first_filename or filename == self.input.second_filename:
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return

        # handle overwrite manually
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        # deduce header from selected variable IDs and write header
        output_header = self._getOutputHeader()
        time_indices = self.input.common_frames
        self.parent.inDialog()
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.input.first_filename, self.input.first_language) as first_in:
            first_in.header = self.input.first_header
            first_in.time = self.input.first_time

            with Serafin.Read(self.input.second_filename, self.input.second_language) as second_in:
                second_in.header = self.input.second_header
                second_in.time = self.input.second_time

                progressBar.setValue(5)
                QApplication.processEvents()

                with Serafin.Write(filename, self.input.first_language, overwrite) as out_stream:

                    out_stream.write_header(output_header)
                    process = ProjectMeshThread(first_in, second_in, out_stream, output_header, self.input.is_inside,
                                                self.input.point_interpolators, time_indices,
                                                self.operationBox.currentIndex())
                    progressBar.connectToThread(process)
                    process.run()

                    if not process.canceled:
                        progressBar.outputFinished()

        progressBar.exec_()
        self.parent.outDialog()


class ProjectMeshGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Compute the difference between two meshes')
        self.tab = QTabWidget()
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 150px; }')

        self.input = InputTab(self)
        self.submit = SubmitTab(self.input, self)

        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.submit, 'Submit')
        self.tab.setTabEnabled(1, False)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def reset(self):
        self.submit.reset()
        self.tab.setTabEnabled(1, False)

    def resetFirst(self):
        keep_old = self.submit.resetFirst()
        if not keep_old:
            self.tab.setTabEnabled(1, False)
        return keep_old

    def getSecond(self, old_second, common_vars):
        self.submit.getSecond(old_second, common_vars)
        self.tab.setTabEnabled(1, True)


def exception_hook(exctype, value, traceback):
    """!
    @brief Needed for suppressing traceback silencing in newer version of PyQt5
    """
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == '__main__':
    # suppress explicitly traceback silencing
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    widget = ProjectMeshGUI()
    widget.show()
    app.exec_()



