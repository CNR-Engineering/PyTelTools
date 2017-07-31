import datetime
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import logging
import numpy as np
import sys

from conf.settings import LOGGING_LEVEL
from gui.util import VariableTable, QPlainTextEditLogger, save_dialog, \
    OutputProgressDialog, TimeRangeSlider, SerafinInputTab, TelToolWidget, OutputThread, ConditionDialog
import slf.misc as operations
from slf import Serafin


class MaxMinMeanThread(OutputThread):
    def __init__(self, max_min_type, input_stream, selected_scalars, selected_vectors,
                 time_indices, additional_equations):
        super().__init__()
        self.has_scalar, self.has_vector = False, False
        if selected_scalars:
            self.has_scalar = True
            self.scalar_calculator = operations.ScalarMaxMinMeanCalculator(max_min_type, input_stream,
                                                                           selected_scalars, time_indices)
        if selected_vectors:
            self.has_vector = True
            self.vector_calculator = operations.VectorMaxMinMeanCalculator(max_min_type, input_stream,
                                                                           selected_vectors, time_indices,
                                                                           additional_equations)
        self.time_indices = time_indices
        self.nb_frames = len(time_indices)

    def run(self):
        for i, time_index in enumerate(self.time_indices):
            if self.canceled:
                return []
            if self.has_scalar:
                self.scalar_calculator.max_min_mean_in_frame(time_index)
            if self.has_vector:
                self.vector_calculator.max_min_mean_in_frame(time_index)

            self.tick.emit(int(95 * (i+1) / self.nb_frames))
            QApplication.processEvents()

        if self.has_scalar and not self.has_vector:
            values = self.scalar_calculator.finishing_up()
        elif not self.has_scalar and self.has_vector:
            values = self.vector_calculator.finishing_up()
        else:
            values = np.vstack((self.scalar_calculator.finishing_up(), self.vector_calculator.finishing_up()))
        return values


class ArrivalDurationThread(OutputThread):
    def __init__(self, input_stream, conditions, time_indices):
        super().__init__()
        self.input_stream = input_stream
        self.time_indices = time_indices
        self.conditions = conditions
        self.nb_conditions = len(self.conditions)
        self.nb_frames = len(time_indices)
        self.calculators = []

        for i, condition in enumerate(self.conditions):
            self.calculators.append(operations.ArrivalDurationCalculator(self.input_stream, self.time_indices,
                                                                         condition))

    def run(self):
        for i, index in enumerate(self.time_indices[1:]):
            if self.canceled:
                return []

            for calculator in self.calculators:
                calculator.arrival_duration_in_frame(index)

            self.tick.emit(int(95 * (i+1) / self.nb_frames))
            QApplication.processEvents()

        values = np.empty((2*self.nb_conditions, self.input_stream.header.nb_nodes))
        for i, calculator in enumerate(self.calculators):
            values[2*i, :] = calculator.arrival
            values[2*i+1, :] = calculator.duration
        return values


class SynchMaxThread(OutputThread):
    def __init__(self, input_stream, selected_vars, time_indices, var):
        super().__init__()
        self.time_indices = time_indices
        self.nb_frames = len(time_indices)
        self.calculator = operations.SynchMaxCalculator(input_stream, selected_vars, time_indices, var)

    def run(self):
        for i, time_index in enumerate(self.time_indices[1:]):
            if self.canceled:
                return []
            self.calculator.synch_max_in_frame(time_index)

            self.tick.emit(int(95 * (i+1) / self.nb_frames))
            QApplication.processEvents()

        return self.calculator.finishing_up()


class TimeSelection(QWidget):
    """!
    @brief Text fields for time selection display (with slider)
    """
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.startIndex = QLineEdit('', self)
        self.endIndex = QLineEdit('', self)
        self.startValue = QLineEdit('', self)
        self.endValue = QLineEdit('', self)
        self.startDate = QLineEdit('', self)
        self.endDate = QLineEdit('', self)
        for w in [self.startDate, self.endDate]:
            w.setReadOnly(True)

        self.startIndex.setMinimumWidth(30)
        self.startIndex.setMaximumWidth(50)
        self.endIndex.setMinimumWidth(30)
        self.endIndex.setMaximumWidth(50)
        self.startValue.setMaximumWidth(100)
        self.endValue.setMaximumWidth(100)
        self.startDate.setMinimumWidth(110)
        self.endDate.setMinimumWidth(110)

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Start time index'), 1, 1)
        glayout.addWidget(self.startIndex, 1, 2)
        glayout.addWidget(QLabel('value'), 1, 3)
        glayout.addWidget(self.startValue, 1, 4)
        glayout.addWidget(QLabel('date'), 1, 5)
        glayout.addWidget(self.startDate, 1, 6)

        glayout.addWidget(QLabel('End time index'), 2, 1)
        glayout.addWidget(self.endIndex, 2, 2)
        glayout.addWidget(QLabel('value'), 2, 3)
        glayout.addWidget(self.endValue, 2, 4)
        glayout.addWidget(QLabel('date'), 2, 5)
        glayout.addWidget(self.endDate, 2, 6)

        self.setLayout(glayout)

    def updateText(self, start_index, start_value, start_date, end_index, end_value, end_date):
        self.startIndex.setText(str(start_index+1))
        self.endIndex.setText((str(end_index+1)))
        self.startValue.setText(str(start_value))
        self.endValue.setText(str(end_value))
        self.startDate.setText(str(start_date))
        self.endDate.setText(str(end_date))

    def clearText(self):
        for w in [self.startIndex, self.endIndex, self.startValue, self.endValue, self.startDate, self.endDate]:
            w.clear()

    def enable(self):
        self.startIndex.setEnabled(True)
        self.endIndex.setEnabled(True)
        self.startValue.setEnabled(True)
        self.endValue.setEnabled(True)

    def disable(self):
        self.startIndex.setEnabled(False)
        self.endIndex.setEnabled(False)
        self.startValue.setEnabled(False)
        self.endValue.setEnabled(False)


class InputTab(SerafinInputTab):
    def __init__(self, parent):
        super().__init__(parent)
        self.btnOpen.clicked.connect(self.btnOpenEvent)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        mainLayout.addLayout(self.input_layout)
        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addStretch()
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def btnOpenEvent(self):
        canceled, filename = self.open_event()
        if canceled:
            return

        self.reset()
        self.parent.reset()
        success, data = self.read_2d(filename)
        if not success:
            return
        if data.header.nb_frames == 1:
            QMessageBox.critical(self, 'Error', 'The input file must have more than one frame!',
                                 QMessageBox.Ok)
            return False, None
        self.parent.getInput(data)


class MaxMinMeanTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.data = None
        self.parent = parent

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create a checkbox for operation selection
        self.opBox = QGroupBox('Compute')
        hlayout = QHBoxLayout()
        self.maxButton = QRadioButton('Max')
        self.minButton = QRadioButton('Min')
        meanButton = QRadioButton('Mean')

        hlayout.addWidget(self.maxButton)
        hlayout.addWidget(self.minButton)
        hlayout.addWidget(meanButton)

        self.opBox.setLayout(hlayout)
        self.opBox.setMaximumHeight(80)
        self.opBox.setMaximumWidth(200)
        self.maxButton.setChecked(True)

        # create a slider for time selection
        self.timeSlider = TimeRangeSlider()
        self.timeSlider.setFixedHeight(30)
        self.timeSlider.setMinimumWidth(600)
        self.timeSlider.setEnabled(False)

        # create text boxes for displaying the time selection
        self.timeSelection = TimeSelection(self)
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.startValue.setEnabled(False)
        self.timeSelection.endValue.setEnabled(False)

        # create two 3-column tables for variables selection
        self.firstTable = VariableTable()
        self.secondTable = VariableTable()
        self.secondTable.setMinimumHeight(300)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(LOGGING_LEVEL)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(1, 10))
        mainLayout.addWidget(self.timeSlider)
        mainLayout.addWidget(self.timeSelection)
        mainLayout.addItem(QSpacerItem(1, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
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
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.opBox)
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.singlePrecisionBox)
        hlayout.addItem(QSpacerItem(50, 10))
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.timeSelection.startIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.endIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.startValue.editingFinished.connect(self.timeSlider.enterValueEvent)
        self.timeSelection.endValue.editingFinished.connect(self.timeSlider.enterValueEvent)

    def _initVarTables(self):
        self.firstTable.fill(self.data.header)

    def _getSelectedVariables(self):
        return self.secondTable.get_selected_all()

    def reset(self):
        self.maxButton.setChecked(True)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.timeSelection.disable()
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getOutputHeader(self, scalars, vectors):
        output_header = self.data.header.copy()
        output_header.nb_var = len(scalars) + len(vectors)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in scalars + vectors:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def getInput(self, data):
        self.data = data
        self._initVarTables()
        self.btnSubmit.setEnabled(True)

        # unlock convert to single precision
        if self.data.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        if self.data.header.date is not None:
            year, month, day, hour, minute, second = self.data.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.data.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)
        self.timeSlider.setEnabled(True)
        self.timeSelection.enable()

    def btnSubmitEvent(self):
        # fetch the list of selected variables
        selected_vars = self._getSelectedVariables()
        if not selected_vars:
            QMessageBox.critical(self, 'Error', 'Select at least one variable.',
                                 QMessageBox.Ok)
            return

        canceled, filename = save_dialog('.slf', self.data.filename)
        if canceled:
            return

        # separate scalars and vectors
        scalars, vectors, additional_equations = operations.scalars_vectors(self.data.header.var_IDs, selected_vars)

        # get the operation type
        if self.maxButton.isChecked():
            max_min_type = operations.MAX
        elif self.minButton.isChecked():
            max_min_type = operations.MIN
        else:
            max_min_type = operations.MEAN

        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader(scalars, vectors)

        start_index = int(self.timeSelection.startIndex.text()) - 1
        end_index = int(self.timeSelection.endIndex.text())
        time_indices = list(range(start_index, end_index))

        output_message = 'Computing %s of variables %s between frame %d and %d.' \
                          % ('Max' if self.maxButton.isChecked() else ('Min' if self.minButton.isChecked() else 'Mean'),
                             str(output_header.var_IDs), start_index+1, end_index)
        self.parent.inDialog()
        logging.info(output_message)
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time

            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.data.language) as output_stream:
                process = MaxMinMeanThread(max_min_type, input_stream, scalars, vectors, time_indices,
                                           additional_equations)
                progressBar.connectToThread(process)
                values = process.run()

                if not process.canceled:
                    output_stream.write_header(output_header)
                    output_stream.write_entire_frame(output_header, self.data.time[0], values)
                    progressBar.outputFinished()

        progressBar.exec_()
        self.parent.outDialog()


class ArrivalDurationTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.data = None
        self.parent = parent

        self.conditions = []

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create a slider for time selection
        self.timeSlider = TimeRangeSlider()
        self.timeSlider.setFixedHeight(30)
        self.timeSlider.setMinimumWidth(600)
        self.timeSlider.setEnabled(False)

        # create a button for add condition
        self.btnAdd = QPushButton('Add new condition')
        self.btnAdd.setFixedSize(135, 50)

        # create a table for created condition
        self.conditionTable = QTableWidget()
        self.conditionTable.setColumnCount(3)
        self.conditionTable .setHorizontalHeaderLabels(['Condition', 'Arrival', 'Duration'])
        vh = self.conditionTable .verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(20)
        hh = self.conditionTable .horizontalHeader()
        hh.setDefaultSectionSize(150)
        self.conditionTable.setMaximumHeight(500)

        # create text boxes for displaying the time selection
        self.timeSelection = TimeSelection(self)
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.startValue.setEnabled(False)
        self.timeSelection.endValue.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(LOGGING_LEVEL)

        # create a combo box for time unit
        self.unitBox = QComboBox()
        for unit in ['second', 'minute', 'hour', 'day', 'percentage']:
            self.unitBox.addItem(unit)
        self.unitBox.setFixedHeight(30)
        self.unitBox.setMaximumWidth(200)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(1, 10))
        mainLayout.addWidget(self.timeSlider)
        mainLayout.addWidget(self.timeSelection)
        mainLayout.addItem(QSpacerItem(1, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.btnAdd)
        lb = QLabel('Double click on the cells to edit Arrival / Duration variable names')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignBottom | Qt.AlignRight)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(1, 5))
        mainLayout.addWidget(self.conditionTable)

        mainLayout.addItem(QSpacerItem(1, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 10))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addItem(QSpacerItem(10, 10))
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Time unit'))
        vlayout.addWidget(self.unitBox)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.singlePrecisionBox)
        hlayout.addItem(QSpacerItem(50, 10))
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnAdd.clicked.connect(self.btnAddEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.conditionTable.cellChanged.connect(self._checkName)
        self.timeSelection.startIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.endIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.startValue.editingFinished.connect(self.timeSlider.enterValueEvent)
        self.timeSelection.endValue.editingFinished.connect(self.timeSlider.enterValueEvent)

    def _current_names(self, ignore_row, ignore_column):
        names = []
        for row in range(self.conditionTable.rowCount()):
            for column in range(1, 3):
                if row == ignore_row and column == ignore_column:
                    continue
                item = self.conditionTable.item(row, column)
                if item is not None:
                    names.append(item.text())
        return names

    def _current_conditions(self):
        conditions = []
        for row in range(self.conditionTable.rowCount()):
            conditions.append(self.conditionTable.item(row, 0).text())
        return conditions

    def _checkName(self, row, column):
        if column == 1 or column == 2:
            name = self.conditionTable.item(row, column).text()
            if len(name) < 2 or len(name) > 16:
                QMessageBox.critical(self, 'Error', 'The variable names should be between 2 and 16 characters!',
                                     QMessageBox.Ok)
            elif name in self._current_names(row, column):
                QMessageBox.critical(self, 'Error', 'Duplicated name.',
                                     QMessageBox.Ok)
            else:
                return
            # back to default
            condition = self.conditionTable.item(row, 0).text()
            condition_tight = operations.tighten_expression(condition)
            if column == 1:
                self.conditionTable.setItem(row, column, QTableWidgetItem(('A ' + condition_tight)[:16]))
            else:
                self.conditionTable.setItem(row, column, QTableWidgetItem(('D ' + condition_tight)[:16]))

    def _convertTimeUnit(self, time_indices, values):
        time_unit = self.unitBox.currentText()
        if time_unit == 'minute':
            values /= 60
        elif time_unit == 'hour':
            values /= 3600
        elif time_unit == 'day':
            values /= 86400
        elif time_unit == 'percentage':
            values *= 100 / (self.input.time[time_indices[-1]] - self.input.time[time_indices[0]])
        return values

    def reset(self):
        self.conditions = []
        self.conditionTable.setRowCount(0)
        self.timeSelection.disable()
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getInput(self, data):
        self.btnSubmit.setEnabled(True)
        self.data = data

        # unlock convert to single precision
        if self.data.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        if self.data.header.date is not None:
            year, month, day, hour, minute, second = self.data.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.data.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)

        self.timeSlider.setEnabled(True)
        self.timeSelection.enable()

    def getOutputHeader(self):
        output_header = self.data.header.copy()
        output_header.nb_var = 2 * len(self.conditions)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for row in range(self.conditionTable.rowCount()):
            a_name = self.conditionTable.item(row, 1).text()
            d_name = self.conditionTable.item(row, 2).text()
            for name in [a_name, d_name]:
                output_header.var_IDs.append('')
                output_header.var_names.append(bytes(name, 'utf-8').ljust(16))
                output_header.var_units.append(bytes(self.unitBox.currentText().upper(), 'utf-8').ljust(16))
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def btnAddEvent(self):
        dlg = ConditionDialog(self.data.header.var_IDs, self.data.header.var_names)
        value = dlg.exec_()
        if value == QDialog.Rejected:
            return
        condition = str(dlg.condition)
        if condition in self._current_conditions():
            QMessageBox.critical(self, 'Error', 'This condition is already added!',
                                 QMessageBox.Ok)
            return
        condition_tight = operations.tighten_expression(condition)  # used to define variable names
        self.conditions.append(dlg.condition)

        row = self.conditionTable.rowCount()
        self.conditionTable.insertRow(row)
        condition_item = QTableWidgetItem(condition)
        condition_item.setFlags(Qt.ItemIsEditable)
        self.conditionTable.setItem(row, 0, condition_item)
        self.conditionTable.setItem(row, 1, QTableWidgetItem(('A ' + condition_tight)[:16]))
        self.conditionTable.setItem(row, 2, QTableWidgetItem(('D ' + condition_tight)[:16]))

    def btnSubmitEvent(self):
        if not self.conditions:
            QMessageBox.critical(self, 'Error', 'Add at least one condition.',
                                 QMessageBox.Ok)
            return

        start_index = int(self.timeSelection.startIndex.text()) - 1
        end_index = int(self.timeSelection.endIndex.text())
        time_indices = list(range(start_index, end_index))

        if len(time_indices) == 1:
            QMessageBox.critical(self, 'Error', 'Start and end frame cannot be the same.',
                                 QMessageBox.Ok)
            return

        canceled, filename = save_dialog('.slf', self.data.filename)
        if canceled:
            return
        
        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader()
        output_message = 'Computing Arrival / Duration between frame %d and %d.' \
                          % (start_index+1, end_index)
        self.parent.inDialog()
        logging.info(output_message)
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time

            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.data.language) as output_stream:
                process = ArrivalDurationThread(input_stream, self.conditions, time_indices)
                progressBar.connectToThread(process)
                values = process.run()

                if not process.canceled:
                    values = self._convertTimeUnit(time_indices, values)
                    output_stream.write_header(output_header)
                    output_stream.write_entire_frame(output_header, self.data.time[0], values)
                    progressBar.outputFinished()

        progressBar.exec_()
        self.parent.outDialog()


class SynchMaxTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.data = None
        self.parent = parent

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create a combox box for variable selection
        self.varBox = QComboBox()
        self.varBox.setFixedSize(200, 30)

        # create a slider for time selection
        self.timeSlider = TimeRangeSlider()
        self.timeSlider.setFixedHeight(30)
        self.timeSlider.setMinimumWidth(600)
        self.timeSlider.setEnabled(False)

        # create text boxes for displaying the time selection
        self.timeSelection = TimeSelection(self)
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.startValue.setEnabled(False)
        self.timeSelection.endValue.setEnabled(False)

        # create two 3-column tables for variables selection
        self.firstTable = VariableTable()
        self.secondTable = VariableTable()
        self.secondTable.setMinimumHeight(300)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(LOGGING_LEVEL)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(1, 10))
        mainLayout.addWidget(self.timeSlider)
        mainLayout.addWidget(self.timeSelection)
        mainLayout.addItem(QSpacerItem(1, 10))

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('  Select the reference variable '))
        hlayout.addWidget(self.varBox, Qt.AlignLeft)
        hlayout.addStretch()
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(1, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
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

    def _bindEvents(self):
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.timeSelection.startIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.endIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.startValue.editingFinished.connect(self.timeSlider.enterValueEvent)
        self.timeSelection.endValue.editingFinished.connect(self.timeSlider.enterValueEvent)

    def _initVarTables(self):
        self.firstTable.fill(self.data.header)
        self.secondTable.insertRow(0)
        self.secondTable.setItem(0, 0, QTableWidgetItem('MAX TIME'))
        self.secondTable.setItem(0, 1, QTableWidgetItem('MAX TIME'))
        self.secondTable.setItem(0, 2, QTableWidgetItem('S'))
        for j in range(3):
            self.secondTable.item(0, j).setFlags(Qt.NoItemFlags)

    def _getSelectedVariables(self):
        return self.secondTable.get_selected_all()

    def reset(self):
        self.varBox.clear()
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.timeSelection.disable()
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getOutputHeader(self, selected_vars):
        output_header = self.data.header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in selected_vars:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def getInput(self, data):
        self.data = data
        self._initVarTables()
        for var, var_name in zip(self.data.header.var_IDs, self.data.header.var_names):
            item = '%s (%s)' % (var, var_name.decode('utf-8').strip())
            self.varBox.addItem(item)

        self.btnSubmit.setEnabled(True)

        # unlock convert to single precision
        if self.data.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        if self.data.header.date is not None:
            year, month, day, hour, minute, second = self.data.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.data.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)
        self.timeSlider.setEnabled(True)
        self.timeSelection.enable()

    def btnSubmitEvent(self):
        # fetch the list of selected variables
        selected_vars = self._getSelectedVariables()
        if not selected_vars:
            QMessageBox.critical(self, 'Error', 'Select at least one variable.',
                                 QMessageBox.Ok)
            return

        canceled, filename = save_dialog('.slf', self.data.filename)
        if canceled:
            return

        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader(selected_vars)

        start_index = int(self.timeSelection.startIndex.text()) - 1
        end_index = int(self.timeSelection.endIndex.text())
        time_indices = list(range(start_index, end_index))
        var = self.varBox.currentText().split(' (')[0]

        output_message = 'Computing SynchMax of variables %s between frame %d and %d.' \
                          % (str(list(map(lambda x: x[0], selected_vars[1:]))), start_index+1, end_index)
        self.parent.inDialog()
        logging.info(output_message)
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time

            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.data.language) as output_stream:
                process = SynchMaxThread(input_stream, selected_vars[1:], time_indices, var)
                progressBar.connectToThread(process)
                values = process.run()

                if not process.canceled:
                    output_stream.write_header(output_header)
                    output_stream.write_entire_frame(output_header, self.data.time[0], values)
                    progressBar.outputFinished()

        progressBar.exec_()
        self.parent.outDialog()


class MaxMinMeanGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Compute Max/Min/Mean')

        self.input = InputTab(self)
        self.maxMinTab = MaxMinMeanTab(self)
        self.arrivalDurationTab = ArrivalDurationTab( self)
        self.syncMaxTab = SynchMaxTab(self)

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.maxMinTab, 'Max/Min/Mean')
        self.tab.addTab(self.arrivalDurationTab, 'Arrival/Duration')
        self.tab.addTab(self.syncMaxTab, 'SynchMax')

        for i in range(1, 4):
            self.tab.setTabEnabled(i, False)

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def reset(self):
        for i, tab in enumerate([self.maxMinTab, self.arrivalDurationTab, self.syncMaxTab]):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def getInput(self, data):
        for i, tab in enumerate([self.maxMinTab, self.arrivalDurationTab, self.syncMaxTab]):
            tab.getInput(data)
            self.tab.setTabEnabled(i+1, True)


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
    widget = MaxMinMeanGUI()
    widget.show()
    app.exec_()


