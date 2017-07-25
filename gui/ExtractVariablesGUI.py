import sys
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import logging
from slf import Serafin
from slf.variables import get_available_variables, \
    do_calculations_in_frame, get_necessary_equations, get_US_equation, add_US
from gui.util import TableWidgetDragRows, QPlainTextEditLogger, FallVelocityMessage, FrictionLawMessage, \
    TimeRangeSlider, DoubleSliderBox, OutputProgressDialog, OutputThread, TelToolWidget, testOpen, handleOverwrite


class ExtractVariablesThread(OutputThread):
    def __init__(self, necessary_equations, us_equation, input_stream, output_stream,
                 output_header, time_indices):
        super().__init__()
        self.necessary_equations = necessary_equations
        self.us_equation = us_equation
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.output_header = output_header
        self.time_indices = time_indices
        self.nb_frames = len(time_indices)

    def run(self):
        for i, time_index in enumerate(self.time_indices):
            if self.canceled:
                return
            values = do_calculations_in_frame(self.necessary_equations, self.us_equation, self.input_stream, time_index,
                                             self.output_header.var_IDs, self.output_header.np_float_type)
            self.output_stream.write_entire_frame(self.output_header, self.input_stream.time[time_index], values)
            self.tick.emit(5 + int(95 * (i+1) / self.nb_frames))


class TimeTable(TableWidgetDragRows):
    def __init__(self):
        super().__init__()

    def dropEvent(self, event):
        super().dropEvent(event)
        # sort the table
        self.sortItems(2, Qt.AscendingOrder)


class ManualTimeSelection(QWidget):
    def __init__(self, input, timeSelection):
        super().__init__()
        self.input = input
        self.timeSelection = timeSelection

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

        self.time_frames = None
        self.hasData = False

        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint |
                            Qt.WindowMaximizeButtonHint)
        self.setWindowFlags(self.windowFlags() & ~ Qt.WindowCloseButtonHint)
        self.setWindowTitle('Select manually the time frames in the output file')

    def _initWidgets(self):
        # create the default button (regular sampling)
        self.btnDefault = QPushButton('Default')
        self.btnDefault.setToolTip('Regular sampling with the chosen frequency')
        self.btnDefault.setFixedSize(100, 40)

        # create the clear button
        self.btnClear = QPushButton('Clear')
        self.btnClear.setToolTip('Clear selection')
        self.btnClear.setFixedSize(100, 40)

        # create the OK button
        self.btnOK = QPushButton('OK', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnOK.setFixedSize(100, 40)

        # create two 3-column tables for variables selection
        self.firstTable = TimeTable()
        self.secondTable = TimeTable()
        for tw in [self.firstTable, self.secondTable]:
            tw.setColumnCount(3)
            tw.setHorizontalHeaderLabels(['Index', 'Time (s)', 'Date'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
            hh = tw.horizontalHeader()
            hh.setDefaultSectionSize(110)
            tw.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tw.setMaximumHeight(800)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(30, 15))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 10))
        hlayout.addWidget(self.btnDefault)
        hlayout.addWidget(self.btnClear)
        hlayout.setSpacing(10)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 15))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Available frames'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(self.firstTable, 2, 1)
        glayout.addWidget(QLabel('Selected frames'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(self.secondTable, 2, 2)
        glayout.setSpacing(5)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 15))

        mainLayout.addWidget(self.btnOK)
        mainLayout.setAlignment(self.btnOK, Qt.AlignRight)
        mainLayout.addItem(QSpacerItem(10, 15))
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnDefault.clicked.connect(self.defaultSelection)
        self.btnClear.clicked.connect(self._clearTables)
        self.btnOK.clicked.connect(self.timeSelection.quitManualSelection)

    def _clearTables(self):
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)

        for i, (value, date) in enumerate(zip(self.input.time, self.time_frames)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            index_item = QTableWidgetItem(str(i+1))
            value_item = QTableWidgetItem(str(value))
            date_item = QTableWidgetItem(str(date))
            self.firstTable.setItem(i, 0, index_item)
            self.firstTable.setItem(i, 1, value_item)
            self.firstTable.setItem(i, 2, date_item)

    def getData(self):
        if self.time_frames is None:
            self.time_frames = list(map(lambda x: self.timeSelection.start_time + datetime.timedelta(seconds=x),
                                        self.input.time))
        self.defaultSelection()
        self.hasData = True

    def defaultSelection(self):
        _, _, _, time_indices = self.timeSelection.getTime()
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)

        for i, (value, date) in enumerate(zip(self.input.time, self.time_frames)):
            index_item = QTableWidgetItem(str(i+1))
            value_item = QTableWidgetItem(str(value))
            date_item = QTableWidgetItem(str(date))
            if i in time_indices:
                row = self.secondTable.rowCount()
                self.secondTable.insertRow(row)
                self.secondTable.setItem(row, 0, index_item)
                self.secondTable.setItem(row, 1, value_item)
                self.secondTable.setItem(row, 2, date_item)
            else:
                row = self.firstTable.rowCount()
                self.firstTable.insertRow(row)
                self.firstTable.setItem(row, 0, index_item)
                self.firstTable.setItem(row, 1, value_item)
                self.firstTable.setItem(row, 2, date_item)


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.language = None

        # some attributes to store the input file info
        self.header = None
        self.time = []
        self.available_vars = []
        self.us_equation = None
        self.fall_velocities = []

        self.YELLOW = QColor(245, 255, 207)
        self.GREEN = QColor(200, 255, 180)
        self.BLUE = QColor(200, 230, 250)
        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

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
        englishButton = QRadioButton('English')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(englishButton)
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        if self.parent.language == 'fr':
            self.frenchButton.setChecked(True)
        else:
            englishButton.setChecked(True)

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

        # create a button for interpreting W from user-defined friction law
        self.btnAddUS = QPushButton('Add US from friction law', self)
        self.btnAddUS.setToolTip('Compute <b>US</b> based on a friction law')
        self.btnAddUS.setEnabled(False)
        self.btnAddUS.setFixedWidth(200)

        # create a button for adding Rouse number from user-defined fall velocity
        self.btnAddWs = QPushButton('Add Rouse from fall velocity', self)
        self.btnAddWs.setToolTip('Compute <b>Rouse</b> for specific fall velocity')
        self.btnAddWs.setEnabled(False)
        self.btnAddWs.setFixedWidth(200)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        """!
        @brief (Used in __init__) Bind events to widgets
        """
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnAddUS.clicked.connect(self.btnAddUSEvent)
        self.btnAddWs.clicked.connect(self.btnAddWsEvent)

    def _setLayout(self):
        """
        @brief: (Used in __init__) Set up layout
        """
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

        mainLayout.addItem(QSpacerItem(1, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.firstTable)
        vlayout.addItem(QSpacerItem(1, 5))
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.btnAddUS)
        hlayout2.addItem(QSpacerItem(30, 1))
        vlayout.addLayout(hlayout2)
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.btnAddWs)
        hlayout2.addItem(QSpacerItem(30, 1))
        vlayout.addLayout(hlayout2)
        vlayout.addItem(QSpacerItem(1, 5))
        vlayout.setAlignment(Qt.AlignLeft)

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

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _initVarTables(self):
        """!
        @brief (Used in btnOpenEvent) Put available variables ID-name-unit in the table display
        """

        # add original variables to the table
        for i, (var_ID, var_name, var_unit) in enumerate(zip(self.header.var_IDs, self.header.var_names, self.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var_ID.strip())
            name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, id_item)
            self.firstTable.setItem(i, 1, name_item)
            self.firstTable.setItem(i, 2, unit_item)
        offset = self.firstTable.rowCount()

        if self.header.is_2d:
            # find new computable variables (stored as slf.variables.Variable objects)
            self.available_vars = get_available_variables(self.header.var_IDs)

            # add new variables to the table
            for i, var in enumerate(self.available_vars):
                self.firstTable.insertRow(self.firstTable.rowCount())
                id_item = QTableWidgetItem(var.ID())
                name_item = QTableWidgetItem(var.name(self.language))
                unit_item = QTableWidgetItem(var.unit())
                self.firstTable.setItem(offset+i, 0, id_item)
                self.firstTable.setItem(offset+i, 1, name_item)
                self.firstTable.setItem(offset+i, 2, unit_item)
                self.firstTable.item(offset+i, 0).setBackground(self.YELLOW)  # set new variables colors to yellow
                self.firstTable.item(offset+i, 1).setBackground(self.YELLOW)
                self.firstTable.item(offset+i, 2).setBackground(self.YELLOW)

    def _reinitInput(self):
        """!
        @brief (Used in btnOpenEvent) Reinitialize input file data before reading a new file
        """
        self.summaryTextBox.clear()
        self.available_vars = []
        self.header = None
        self.time = []
        self.us_equation = None
        self.fall_velocities = []
        self.btnAddUS.setEnabled(False)
        self.btnAddWs.setEnabled(False)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

        self.parent.reset()

    def getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append((self.secondTable.item(i, 0).text(),
                            bytes(self.secondTable.item(i, 1).text(), 'utf-8').ljust(16),
                            bytes(self.secondTable.item(i, 2).text(), 'utf-8').ljust(16)))
        return selected

    def btnAddUSEvent(self):
        msg = FrictionLawMessage()
        value = msg.exec_()
        if value != QDialog.Accepted:
            return

        friction_law = msg.getChoice()
        self.us_equation = get_US_equation(friction_law)
        new_vars = []
        add_US(new_vars, self.header.var_IDs)

        # add US, TAU and DMAX to available variable
        offset = self.firstTable.rowCount()
        for i in range(len(new_vars)):
            var = self.new_vars[i]
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.language))
            unit_item = QTableWidgetItem(var.unit())
            self.firstTable.setItem(offset+i, 0, id_item)
            self.firstTable.setItem(offset+i, 1, name_item)
            self.firstTable.setItem(offset+i, 2, unit_item)
            self.firstTable.item(offset+i, 0).setBackground(self.GREEN)  # set new US color to green
            self.firstTable.item(offset+i, 1).setBackground(self.GREEN)
            self.firstTable.item(offset+i, 2).setBackground(self.GREEN)

        # lock the add US button again
        self.btnAddUS.setEnabled(False)

        # unlock add Ws button
        self.btnAddWs.setEnabled(True)

    def btnAddWsEvent(self):
        msg = FallVelocityMessage(self.fall_velocities)
        value = msg.exec_()
        if value != QDialog.Accepted:
            return
        table = msg.get_table()
        offset = self.secondTable.rowCount()
        for i in range(len(table)):
            self.secondTable.insertRow(offset+i)
            for j in range(3):
                item = QTableWidgetItem(table[i][j])
                self.secondTable.setItem(offset+i, j, item)
                self.secondTable.item(offset+i, j).setBackground(self.BLUE)
        for i in range(len(table)):
            self.fall_velocities.append(float(table[i][0][6:]))

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf)', options=options)
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

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # record the time series
            resin.get_time()

            # copy to avoid reading the same data in the future
            self.header = resin.header.copy()
            self.time = resin.time[:]

        logging.info('Finished reading the input file')

        # displaying the available variables
        self._initVarTables()

        if self.header.is_2d:
            # unlock add US button
            if 'US' not in self.header.var_IDs and 'W' in self.header.var_IDs:
                available_var_IDs = list(map(lambda x: x.ID(), self.available_vars))
                available_var_IDs.extend(self.header.var_IDs)
                if 'H' in available_var_IDs and 'M' in available_var_IDs:
                    self.btnAddUS.setEnabled(True)

            # unlock add Ws button
            if 'US' in self.header.var_IDs:
                self.btnAddWs.setEnabled(True)
        self.parent.getInput()


class TimeTab(QWidget):
    def __init__(self, parent, input):
        super().__init__()
        self.parent = parent
        self.input = input
        self.start_time = None

        # create a slider for time selection
        self.timeSlider = TimeRangeSlider()
        self.timeSlider.setFixedHeight(30)
        self.timeSlider.setMinimumWidth(600)
        self.timeSlider.setEnabled(False)
        self.last_sampling_frequency = 1

        # create text boxes for displaying the time selection and sampling
        self.timeSelection = DoubleSliderBox(self)
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.startValue.setEnabled(False)
        self.timeSelection.endValue.setEnabled(False)

        # create the tables for manual selection
        self.manualSelection = ManualTimeSelection(self.input, self)

        # create the button for manual selection
        self.btnManual = QPushButton('Manual selection')
        self.btnManual.setFixedSize(130, 50)
        self.btnManual.setEnabled(False)

        # create a text field for selection display
        self.selectionTextBox = QPlainTextEdit()

        # bind events
        self.timeSelection.startIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.endIndex.editingFinished.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.startValue.editingFinished.connect(self.timeSlider.enterValueEvent)
        self.timeSelection.endValue.editingFinished.connect(self.timeSlider.enterValueEvent)

        self.btnManual.clicked.connect(self.btnManualEvent)
        self.timeSelection.startDate.textChanged.connect(self.regularSelectionEvent)
        self.timeSelection.endDate.textChanged.connect(self.regularSelectionEvent)
        self.timeSelection.timeSamplig.editingFinished.connect(self.regularSelectionEvent)

        # set layout
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(self.timeSlider)
        mainLayout.addItem(QSpacerItem(10, 5))
        mainLayout.addWidget(self.timeSelection)
        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(20, 20))
        hlayout.addWidget(self.btnManual)
        hlayout.addWidget(self.selectionTextBox, Qt.AlignLeft)
        hlayout.setSpacing(15)
        hlayout.setAlignment(self.btnManual, Qt.AlignTop)
        mainLayout.addLayout(hlayout)
        mainLayout.setAlignment(Qt.AlignTop)
        self.setLayout(mainLayout)

        self.setMinimumWidth(800)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)

    def getTime(self):
        start_index = int(self.timeSelection.startIndex.text())
        end_index = int(self.timeSelection.endIndex.text())
        try:
            sampling_frequency = int(self.timeSelection.timeSamplig.text())
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be a number!',
                                 QMessageBox.Ok)
            self.timeSelection.timeSamplig.setText(str(self.last_sampling_frequency))
            return []
        if sampling_frequency < 1 or sampling_frequency > end_index:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be in the range [1; nbFrames]!',
                                 QMessageBox.Ok)
            self.timeSelection.timeSamplig.setText(str(self.last_sampling_frequency))
            return []
        self.last_sampling_frequency = sampling_frequency
        return start_index, end_index, sampling_frequency, list(range(start_index-1, end_index, sampling_frequency))

    def getManualTime(self):
        selected_indices = []
        for i in range(self.manualSelection.secondTable.rowCount()):
            selected_indices.append(int(self.manualSelection.secondTable.item(i, 0).text())-1)
        return selected_indices

    def reset(self):
        self.timeSlider.setEnabled(False)
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.startValue.setEnabled(False)
        self.timeSelection.endValue.setEnabled(False)
        self.btnManual.setEnabled(False)
        self.manualSelection.hasData = False
        self.manualSelection.time_frames = None
        self.timeSelection.visited = False
        self.selectionTextBox.clear()
        self.selectionTextBox.appendPlainText('=== Manual selection mode OFF ===')

    def getInput(self):
        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), self.input.time))
        self.timeSelection.clearText()
        self.timeSlider.reinit(self.start_time, time_frames, self.timeSelection)

        if self.input.header.nb_frames > 1:
            self.timeSlider.setEnabled(True)
            self.timeSelection.startIndex.setEnabled(True)
            self.timeSelection.endIndex.setEnabled(True)
            self.timeSelection.startValue.setEnabled(True)
            self.timeSelection.endValue.setEnabled(True)
            self.btnManual.setEnabled(True)

    def regularSelectionEvent(self):
        if not self.timeSelection.visited:   # avoid redundant text display at initialization
            self.timeSelection.visited = True
            return
        selection = self.getTime()
        if not selection:
            return
        start_index, end_index, sampling_frequency, indices = selection
        message = 'Current selection: %d frame%s between frame %d and %d with sampling frequency %d.' \
                  % (len(indices), ['', 's'][len(indices) > 1], start_index, end_index, sampling_frequency)

        if self.manualSelection.hasData:
            reply = QMessageBox.warning(self, 'Confirm turn off selection',
                                        'Do you want to turn off the manuel selection mode?\n(Your manual selection will be cleared)',
                                        QMessageBox.Ok | QMessageBox.Cancel,
                                        QMessageBox.Ok)
            if reply == QMessageBox.Cancel:
                return
            self.manualSelection.hasData = False
            self.selectionTextBox.appendPlainText('== Manual selection mode OFF ==')
        self.selectionTextBox.appendPlainText(message)

    def btnManualEvent(self):
        if not self.manualSelection.hasData:
            reply = QMessageBox.warning(self, 'Confirm manuel selection',
                                        'Do you want to enter the manuel selection mode?',
                                        QMessageBox.Ok | QMessageBox.Cancel,
                                        QMessageBox.Ok)
            if reply == QMessageBox.Cancel:
                return
            self.manualSelection.getData()
            self.selectionTextBox.appendPlainText('=== Manual selection mode ON ===')
        self.parent.inDialog()
        self.manualSelection.show()

    def quitManualSelection(self):
        selected = self.getManualTime()
        if not selected:
            _ = QMessageBox.critical(self, 'Error',
                                     'Please select at least one frame',
                                     QMessageBox.Ok, QMessageBox.Ok)
            return
        self.parent.outDialog()
        self.manualSelection.hide()
        self.selectionTextBox.appendPlainText('Current selection: %d frame%s between frame %d and %d.'
                                              % (len(selected), ['', 's'][len(selected) > 1],
                                                 selected[0]+1, selected[-1]+1))


class SubmitTab(QWidget):
    def __init__(self, inputTab, timeSelection, parent):
        super().__init__()
        self.input = inputTab
        self.timeSelection = timeSelection
        self.parent = parent

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

        # bind events
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

        # set layout
        mainLayout = QVBoxLayout()
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

    def reset(self):
        self.btnSubmit.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)

    def getOutputHeader(self, selected_vars):
        output_header = self.input.header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in selected_vars:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def getInput(self):
        # unlock convert to single precision
        if self.input.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        # unlock the submit button
        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
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

        # fetch the list of selected variables
        selected_vars = self.input.getSelectedVariables()

        # deduce header from selected variable IDs and write header
        output_header = self.getOutputHeader(selected_vars)

        # fetch the list of selected frames
        if self.timeSelection.manualSelection.hasData:
            output_time_indices = self.timeSelection.getManualTime()
            output_message = 'Writing the output with variables %s for %d frame%s between frame %d and %d.' \
                              % (str(output_header.var_IDs), len(output_time_indices), ['', 's'][len(output_time_indices) > 1],
                                 output_time_indices[0]+1, output_time_indices[-1]+1)
        else:
            start_index, end_index, sampling_frequency, output_time_indices = self.timeSelection.getTime()
            output_message = 'Writing the output with variables %s between frame %d and %d with sampling frequency %d.' \
                              % (str(output_header.var_IDs), start_index, end_index, sampling_frequency)


        self.parent.inDialog()
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.input.filename, self.input.language) as resin:
            # instead of re-reading the header and the time, just do a copy
            resin.header = self.input.header
            resin.time = self.input.time
            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.input.language, overwrite) as resout:
                logging.info(output_message)

                resout.write_header(output_header)

                # do some additional computations
                necessary_equations = get_necessary_equations(self.input.header.var_IDs, output_header.var_IDs,
                                                              self.input.us_equation)

                process = ExtractVariablesThread(necessary_equations, self.input.us_equation, resin, resout,
                                                 output_header, output_time_indices)
                progressBar.connectToThread(process)
                process.run()

                if not process.canceled:
                    progressBar.outputFinished()
                progressBar.exec_()
                self.parent.outDialog()


class ExtractVariablesGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = InputTab(self)
        self.timeTab = TimeTab(self, self.input)
        self.submitTab = SubmitTab(self.input, self.timeTab, self)

        self.setWindowTitle('Extract variables and time')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.timeTab, 'Select time frames')
        self.tab.addTab(self.submitTab, 'Submit')

        self.tab.setTabEnabled(1, False)
        self.tab.setTabEnabled(2, False)

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')
        self.tab.currentChanged.connect(self.switch_tab)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def switch_tab(self, index):
        if index == 2:
            if self.input.secondTable.rowCount() == 0:
                QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                     QMessageBox.Ok)
                self.tab.setCurrentIndex(0)
                return

    def reset(self):
        for i, tab in enumerate([self.timeTab, self.submitTab]):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def getInput(self):
        for i, tab in enumerate([self.timeTab, self.submitTab]):
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
    widget = ExtractVariablesGUI()
    widget.show()
    app.exec_()


