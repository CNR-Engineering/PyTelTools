import sys
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import re
import numpy as np
import logging
import copy
from slf import Serafin
import slf.misc as operations
from gui.util import TableWidgetDragRows, QPlainTextEditLogger, handleOverwrite, \
    OutputProgressDialog, TimeRangeSlider, testOpen


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


class ConditionDialog(QDialog):
    def __init__(self, input_header):
        super().__init__()
        self.var_IDs = input_header.var_IDs

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkCondition)
        buttons.rejected.connect(self.reject)

        self.expressionBox = QTextEdit()
        self.expressionBox.setFixedSize(150, 30)
        self.old_format = self.expressionBox.currentCharFormat()
        self.expressionBox.cursorPositionChanged.connect(lambda:
                                                         self.expressionBox.setCurrentCharFormat(self.old_format))

        self.addButton = QPushButton('Add')
        self.addButton.setFixedSize(50, 30)
        self.addButton.clicked.connect(self.addButtonEvent)

        self.clearButton = QPushButton('Clear')
        self.clearButton.setFixedSize(50, 30)
        self.clearButton.clicked.connect(self.expressionBox.clear)

        self.varBox = QComboBox()
        self.varBox.setFixedSize(150, 30)

        for var_ID, var_name in zip(input_header.var_IDs, input_header.var_names):
            var_name = var_name.decode('utf-8').strip()
            self.varBox.addItem('%s (%s)' % (var_ID, var_name))

        self.comparatorBox = QComboBox()
        for comparator in ['>', '<', '>=', '<=']:
            self.comparatorBox.addItem(comparator)
        self.comparatorBox.setFixedSize(50, 30)

        self.threashold = QLineEdit()
        self.threashold.setFixedSize(150, 30)

        self.condition = ([], '', 0.0)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Help</b>: use <b>Add</b> button to add variables to the expression.<br>'
                                    'You can also enter operators, parentheses and numbers.<br>'
                                    'Supported operators: <tt>+ - * / ^ sqrt</tt>.'))

        mainLayout.addItem(QSpacerItem(50, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Edit expression'))
        hlayout.addWidget(self.clearButton)
        hlayout.addWidget(self.addButton)
        hlayout.addWidget(self.varBox)
        hlayout.setSpacing(10)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        mainLayout.setAlignment(hlayout, Qt.AlignHCenter)
        mainLayout.addItem(QSpacerItem(50, 20))
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Expression'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Comparator'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Threshold'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.expressionBox, 2, 1)
        glayout.addWidget(self.comparatorBox, 2, 2)
        glayout.addWidget(self.threashold, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Add new condition')
        self.resize(self.sizeHint())

    def _processExpression(self, expression):
        infix = operations.to_infix(expression)
        return operations.infix_to_postfix(infix)

    def _validateExpression(self, expression):
        for item in expression:
            if item[0] == '[':  # variable ID
                if item[1:-1] not in self.var_IDs:
                    return False
            elif item in operations.OPERATORS:
                continue
            else:  # is number
                try:
                    _ = float(item)
                except ValueError:
                    return False
        return operations.is_valid_postfix(expression)

    def addButtonEvent(self):
        var_ID = self.varBox.currentText().split(' (')[0]
        self.expressionBox.insertHtml("<span style=\" font-size:8pt; "
                                      "font-weight:600; color:#554DF7;\" "
                                      ">[%s]</span>" % var_ID)
        self.expressionBox.setCurrentCharFormat(self.old_format)

    def checkCondition(self):
        expression = self.expressionBox.toPlainText()
        comparator = self.comparatorBox.currentText()
        threshold = self.threashold.text()
        self.condition = ([], '', 0.0)

        try:
            threshold = float(threshold)
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The threshold is not a number!',
                                 QMessageBox.Ok)
            return
        expression = self._processExpression(expression)

        if not self._validateExpression(expression):
            QMessageBox.critical(self, 'Error', 'Invalid expression.',
                                 QMessageBox.Ok)
            return
        self.condition = (expression, comparator, threshold)
        self.accept()


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.language = None

        # some attributes to store the input file info
        self.header = None
        self.time = []

        self._initWidgets()
        self._setLayout()
        self.btnOpen.clicked.connect(self.btnOpenEvent)

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """
        # create the button open
        self.btnOpen = QPushButton('Open', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a .slf file')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)

        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        self.frenchButton.setChecked(True)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Input file'), 1, 1)
        glayout.addWidget(self.inNameBox, 1, 2)
        glayout.addWidget(QLabel('Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _reinitInput(self):
        """!
        @brief (Used in btnOpenEvent) Reinitialize input file data before reading a new file
        """
        self.summaryTextBox.clear()
        self.header = None
        self.time = []

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

        self.parent.reset()

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        # reinitialize input file data
        self._reinitInput()

        self.filename = filename
        self.inNameBox.setText(filename)

        with Serafin.Read(self.filename, self.language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # record the time series
            resin.get_time()

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        logging.info('Finished reading the input file')

        self.parent.getInput()


class MaxMinMeanTab(QWidget):
    def __init__(self, input, parent):
        super().__init__()
        self.input = input
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

        self.secondTable.setMinimumHeight(300)

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
        for i, (id, name, unit) in enumerate(zip(self.input.header.var_IDs,
                                                 self.input.header.var_names, self.input.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
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

    def reset(self):
        self.maxButton.setChecked(True)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.timeSelection.disable()
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getOutputHeader(self, scalars, vectors):
        output_header = self.input.header.copy()
        output_header.nb_var = len(scalars) + len(vectors)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in scalars + vectors:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def getInput(self):
        self._initVarTables()
        self.btnSubmit.setEnabled(True)

        # unlock convert to single precision
        if self.input.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.input.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)

        if self.input.header.nb_frames > 1:
            self.timeSlider.setEnabled(True)
            self.timeSelection.enable()

    def btnSubmitEvent(self):
        # fetch the list of selected variables
        selected_vars = self._getSelectedVariables()
        if not selected_vars:
            QMessageBox.critical(self, 'Error', 'Select at least one variable.',
                                 QMessageBox.Ok)
            return

        # separate scalars and vectors
        scalars, vectors, additional_equations = operations.scalars_vectors(self.input.header.var_IDs, selected_vars)

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
        if filename == self.input.filename:
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return

        # handle overwrite manually
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        # get the operation type
        if self.maxButton.isChecked():
            scalar_operation = operations.scalar_max
            vector_operation = operations.vector_max
        elif self.minButton.isChecked():
            scalar_operation = operations.scalar_min
            vector_operation = operations.vector_min
        else:
            scalar_operation = operations.mean
            vector_operation = operations.mean
        scalar_values, vector_values = None, None

        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader(scalars, vectors)

        start_index = int(self.timeSelection.startIndex.text()) - 1
        end_index = int(self.timeSelection.endIndex.text())
        time_indices = list(range(start_index, end_index))

        output_message = 'Computing %s of variables %s between frame %d and %d.' \
                          % ('Max' if self.maxButton.isChecked() else ('Min' if self.minButton.isChecked() else 'Mean'),
                             str(output_header.var_IDs), start_index+1, end_index)

        # disable close button
        self.parent.inDialog()
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.input.filename, self.input.language) as resin:
            resin.header = self.input.header
            resin.time = self.input.time

            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.input.language, overwrite) as resout:
                logging.info(output_message)

                resout.write_header(output_header)
                if scalars:
                    scalar_values = scalar_operation(resin, scalars, time_indices)
                    progressBar.setValue(50)
                if vectors:
                    vector_values = vector_operation(resin, vectors, time_indices, additional_equations)

                if scalars and not vectors:
                    values = scalar_values
                elif not scalars and vectors:
                    values = vector_values
                else:
                    values = np.vstack((scalar_values, vector_values))

                resout.write_entire_frame(output_header, self.input.time[0], values)

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()

        # enable close button
        self.parent.outDialog()


class ArrivalDurationTab(QWidget):
    def __init__(self, input, parent):
        super().__init__()
        self.input = input
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
        logging.getLogger().setLevel(logging.INFO)

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

    def _checkName(self, row, column):
        if column == 1 or column == 2:
            name = self.conditionTable.item(row, column).text()
            if len(name) < 2 or len(name) > 16:
                QMessageBox.critical(self, 'Error', 'The variable names should be between 2 and 16 characters!',
                                     QMessageBox.Ok)
                # back to default
                condition = self.conditionTable.item(row, 0).text()
                condition_tight = operations.remove_spaces(condition)
                if column == 1:
                    self.conditionTable.setItem(row, column, QTableWidgetItem(('A ' + condition_tight)[:16]))
                else:
                    self.conditionTable.setItem(row, column, QTableWidgetItem(('D ' + condition_tight)[:16]))

    def reset(self):
        self.conditions = []
        self.conditionTable.setRowCount(0)
        self.timeSelection.disable()
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getInput(self):
        self.btnSubmit.setEnabled(True)

        # unlock convert to single precision
        if self.input.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.input.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)

        if self.input.header.nb_frames > 1:
            self.timeSlider.setEnabled(True)
            self.timeSelection.enable()

    def getOutputHeader(self):
        output_header = self.input.header.copy()
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
        dlg = ConditionDialog(self.input.header)
        value = dlg.exec_()
        if value == QDialog.Rejected:
            return
        condition = '%s %s %.4f' % (''.join(dlg.condition[0]), dlg.condition[1], dlg.condition[2])
        condition_tight = operations.remove_spaces(condition)  # used to define variable names
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
        if filename == self.input.filename:
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return

        # handle overwrite manually
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        # disable close button
        self.parent.inDialog()
        progressBar = OutputProgressDialog()

        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader()

        output_message = 'Computing Arrival / Duration between frame %d and %d.' \
                          % (start_index+1, end_index)
        nb_conditions = len(self.conditions)

        # do some calculations
        with Serafin.Read(self.input.filename, self.input.language) as resin:
            resin.header = self.input.header
            resin.time = self.input.time

            progressBar.setValue(5)
            QApplication.processEvents()
            with Serafin.Write(filename, self.input.language, overwrite) as resout:
                logging.info(output_message)

                resout.write_header(output_header)

                values = np.empty((2*nb_conditions, self.input.header.nb_nodes))
                for i, (expression, comparator, threshold) in enumerate(self.conditions):
                    arrival, duration = operations.arrival_duration(resin, time_indices,
                                                                    expression, comparator, threshold)
                    values[2*i, :] = arrival
                    values[2*i+1, :] = duration

                time_unit = self.unitBox.currentText()
                if time_unit == 'minute':
                    values /= 60
                elif time_unit == 'hour':
                    values /= 3600
                elif time_unit == 'day':
                    values /= 86400
                elif time_unit == 'percentage':
                    values *= 100 / (self.input.time[time_indices[-1]] - self.input.time[time_indices[0]])

                resout.write_entire_frame(output_header, self.input.time[0], values)
                progressBar.setValue(5 + 95 * (i+1) / nb_conditions)
                QApplication.processEvents()

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()

        # enable close button
        self.parent.outDialog()


class MaxMinMeanGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Compute Max/Min/Mean')

        self.input = InputTab(self)
        self.maxMinTab = MaxMinMeanTab(self.input, self)
        self.arrivalDurationTab = ArrivalDurationTab(self.input, self)

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.maxMinTab, 'Max/Min/Mean')
        self.tab.addTab(self.arrivalDurationTab, 'Arrival/Duration')

        self.tab.setTabEnabled(1, False)
        self.tab.setTabEnabled(2, False)

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setMinimumWidth(600)

    def inDialog(self):
        if self.parent is not None:
            self.parent.inDialog()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
            self.setEnabled(False)
            self.show()

    def outDialog(self):
        if self.parent is not None:
            self.parent.outDialog()
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
            self.setEnabled(True)
            self.show()

    def reset(self):
        for i, tab in enumerate([self.maxMinTab, self.arrivalDurationTab]):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def getInput(self):
        for i, tab in enumerate([self.maxMinTab, self.arrivalDurationTab]):
            tab.getInput()
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


