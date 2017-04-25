
import os
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import logging
import copy
import numpy as np
from slf import Serafin
from slf.SerafinVariables import get_available_variables, \
    do_calculations_in_frame, get_necessary_equations, get_US_equation, add_US

_YELLOW = QColor(245, 255, 207)
_GREEN = QColor(200, 255, 180)

class QPlainTextEditLogger(logging.Handler):
    """
    @brief: A text edit box displaying the message logs
    """
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)


class TableWidgetDragRows(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragDropOverwriteMode(False)
        self.last_drop_row = None

    # Override this method to get the correct row index for insertion
    def dropMimeData(self, row, col, mimeData, action):
        self.last_drop_row = row
        return True

    def dropEvent(self, event):
        # The QTableWidget from which selected rows will be moved
        sender = event.source()

        # Default dropEvent method fires dropMimeData with appropriate parameters (we're interested in the row index).
        super().dropEvent(event)
        # Now we know where to insert selected row(s)
        dropRow = self.last_drop_row

        selectedRows = sender.getselectedRowsFast()

        # Allocate space for transfer
        for _ in selectedRows:
            self.insertRow(dropRow)

        # if sender == receiver (self), after creating new empty rows selected rows might change their locations
        sel_rows_offsets = [0 if self != sender or srow < dropRow else len(selectedRows) for srow in selectedRows]
        selectedRows = [row + offset for row, offset in zip(selectedRows, sel_rows_offsets)]

        # copy content of selected rows into empty ones
        for i, srow in enumerate(selectedRows):
            for j in range(self.columnCount()):
                item = sender.item(srow, j)
                if item:
                    source = QTableWidgetItem(item)
                    self.setItem(dropRow + i, j, source)

        # delete selected rows
        for srow in reversed(selectedRows):
            sender.removeRow(srow)

        event.accept()

    def getselectedRowsFast(self):
        selectedRows = []
        for item in self.selectedItems():
            if item.row() not in selectedRows:
                selectedRows.append(item.row())
        selectedRows.sort()
        return selectedRows


class FrictionLawMessage(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.chezy = QRadioButton('Chezy')
        self.chezy.setChecked(True)
        self.strickler = QRadioButton('Strickler')
        self.manning = QRadioButton('Manning')
        self.nikuradse = QRadioButton('Nikuradse')
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.chezy)
        hlayout.addWidget(self.strickler)
        hlayout.addWidget(self.manning)
        hlayout.addWidget(self.nikuradse)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.resize(self.sizeHint())
        self.setWindowTitle('Select a friction law')

    def getChoice(self):
        if self.chezy.isChecked():
            return 0
        elif self.strickler.isChecked():
            return 1
        elif self.manning.isChecked():
            return 2
        elif self.nikuradse.isChecked():
            return 3
        return -1


class DoubleSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)

        # Set integer max and min on parent. These stay constant
        super().setMinimum(0)
        self._max_int = 10000
        super().setMaximum(self._max_int)

        # The min and max values seen by user
        self._min_value = 0.0
        self._max_value = 100.0

        def setMinimum(self, value):
            self.setRange(value, self._max_value)

        def setMaximum(self, value):
            self.setRange(self._min_value, value)

        def setRange(self, minimum, maximum):
            old_value = self.value()
            self._min_value = minimum
            self._max_value = maximum
            self.setValue(old_value)  # Put slider in correct position

        def proportion(self):
            return (self.value() - self._min_value) / self._value_range

    @property
    def _value_range(self):
        return self._max_value - self._min_value

    def value(self):
        return float(super().value()) / self._max_int * self._value_range

    def setValue(self, value):
        super().setValue(int(value / self._value_range * self._max_int))


class SerafinToolInterface(QWidget):
    """
    @brief: A graphical interface for extracting and computing variables from .slf file
    """
    def __init__(self):
        super().__init__()
        self.filename = None
        self.language = None

        # some attributes to store the input file info
        self.header = None
        self.time = []
        self.available_vars = []
        self.us_equation = None

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setFixedSize(800, 900)
        self.setWindowTitle('Serafin Tool')
        self._center()
        self.show()


    def _initWidgets(self):
        """
        @brief: (Used in __init__) Create widgets
        """
        # create the button open
        self.btnOpen = QPushButton('Open', self)
        self.btnOpen.setToolTip('<b>Open</b> a .slf file')
        self.btnOpen.setFixedSize(85, 50)

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
        self.frenchButton.setChecked(True)

        # create two 3-column tables for variables selection
        self.firstTable = TableWidgetDragRows()
        self.secondTable = TableWidgetDragRows()
        for tw in [self.firstTable, self.secondTable]:
            tw.setColumnCount(3)
            tw.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
        self.secondTable.setFixedHeight(300)

        # create a button for interpreting W from user-defined friction law
        self.btnAddUS = QPushButton('Add US from friction law', self)
        self.btnAddUS.setToolTip('Compute <b>US</b> based on a friction law')
        self.btnAddUS.setEnabled(False)
        self.btnAddUS.setFixedWidth(200)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create a slider for time selection
        self.timeSlider = DoubleSlider(self)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self)
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(85, 50)

    def _bindEvents(self):
        """
        @brief: (Used in __init__) Bind events to widgets
        """
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnAddUS.clicked.connect(self.btnAddUSEvent)

    def _setLayout(self):
        """
        @brief: (Used in __init__) Set up layout
        """
        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 20))

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Input file'))
        hlayout.addWidget(self.inNameBox)

        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Summary'))
        hlayout.addWidget(self.summaryTextBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(1, 30))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)

        vlayout.addWidget(QLabel('                                         Available variables'))
        vlayout.addWidget(self.firstTable)
        vlayout.addItem(QSpacerItem(1, 10))
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.btnAddUS)
        hlayout2.addItem(QSpacerItem(30, 1))
        vlayout.addLayout(hlayout2)
        vlayout.addItem(QSpacerItem(1, 10))
        vlayout.setAlignment(Qt.AlignLeft)

        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))

        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
        vlayout.addWidget(QLabel('                                         Output variables'))
        vlayout.addWidget(self.secondTable)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(30, 1))

        mainLayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 50))
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.timeSlider)
        hlayout.addItem(QSpacerItem(30, 1))
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 30))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.singlePrecisionBox)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(800, 30))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _center(self):
        """
        @brief: (Used in __init__) Center the window with respect to the screen
        """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _initVarTables(self):
        """
        @brief: (Used in btnOpenEvent) Put available variables ID-name-unit in the table display
        """

        # add original variables to the table
        for i, (id, name, unit) in enumerate(zip(self.header.var_IDs, self.header.var_names, self.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(i, 2, QTableWidgetItem(unit_item))
        offset = self.firstTable.rowCount()

        # find new computable variables (stored as Equation object)
        self.available_vars = get_available_variables(self.header.var_IDs)

        # add new variables to the table
        for i, var in enumerate(self.available_vars):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.language).decode('utf-8').strip())
            unit_item = QTableWidgetItem(var.unit().decode('utf-8').strip())
            self.firstTable.setItem(offset+i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(offset+i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(offset+i, 2, QTableWidgetItem(unit_item))
            self.firstTable.item(offset+i, 0).setBackground(_YELLOW)  # set new variables colors to yellow
            self.firstTable.item(offset+i, 1).setBackground(_YELLOW)
            self.firstTable.item(offset+i, 2).setBackground(_YELLOW)

    def _reinitInput(self):
        """
        @brief: (Used in btnOpenEvent) Reinitialize input file data before reading a new file
        """
        self.summaryTextBox.clear()
        self.available_vars = []
        self.header = None
        self.time = []
        self.us_equation = None
        self.btnAddUS.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def _handleOverwrite(self, filename):
        """
        @brief: (Used in btnSubmitEvent) Handle manually the overwrite option when saving output file
        """
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it ?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                logging.info('Output canceled')
                return False
            return True
        return False

    def _getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append((self.secondTable.item(i, 0).text(),
                            bytes(self.secondTable.item(i, 1).text(), 'utf-8').ljust(16),
                            bytes(self.secondTable.item(i, 2).text(), 'utf-8').ljust(16)))
        return selected

    def _getOuputHeader(self, selected_vars):
        output_header = self.header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in selected_vars:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def btnAddUSEvent(self):
        msg = FrictionLawMessage()
        value = msg.exec_()
        if value == QDialog.Accepted:
            friction_law = msg.getChoice()
        else:
            return

        self.us_equation = get_US_equation(friction_law)
        add_US(self.available_vars)

        # add US, TAU and DMAX to available variable
        offset = self.firstTable.rowCount()
        for i in range(3):
            var = self.available_vars[-3+i]
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.language).decode('utf-8').strip())
            unit_item = QTableWidgetItem(var.unit().decode('utf-8').strip())
            self.firstTable.setItem(offset+i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(offset+i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(offset+i, 2, QTableWidgetItem(unit_item))
            self.firstTable.item(offset+i, 0).setBackground(_GREEN)  # set new US color to green
            self.firstTable.item(offset+i, 1).setBackground(_GREEN)
            self.firstTable.item(offset+i, 2).setBackground(_GREEN)

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', options=options)
        if not filename:
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


        logging.info('File closed')

        # displaying the available variables
        self._initVarTables()

        # unlock convert to single precision
        if self.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        # unlock add US button
        if 'US' not in self.header.var_IDs and 'W' in self.header.var_IDs:
            available_var_IDs = list(map(lambda x: x.ID(), self.available_vars))
            available_var_IDs.extend(self.header.var_IDs)
            if 'H' in available_var_IDs and 'M' in available_var_IDs:
                self.btnAddUS.setEnabled(True)

    def btnSubmitEvent(self):
        selected_vars = self._getSelectedVariables()

        # check if everything is ready to submit
        if self.header is None:
            return
        if not selected_vars:
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

        # handle overwrite manually
        overwrite = self._handleOverwrite(filename)

        # do some calculations
        with Serafin.Read(self.filename, self.language) as resin:
            resin.header = self.header
            resin.time = self.time

            # print('U', resin.read_var_in_frame(0, 'U')[1:10])
            # print('W', resin.read_var_in_frame(0, 'W')[1:10])
            # print('H', resin.read_var_in_frame(0, 'H')[1:10])
            # print('M', resin.read_var_in_frame(0, 'M')[1:10])

            with Serafin.Write(filename, self.language, overwrite) as resout:
                # deduce header from selected variable IDs and write header
                output_header = self._getOuputHeader(selected_vars)
                logging.info('Writing the output with variables %s' % str(output_header.var_IDs))

                resout.write_header(output_header)

                # do some additional computations
                necessary_equations = get_necessary_equations(self.header.var_IDs, output_header.var_IDs,
                                                              self.us_equation)

                for i, time_i in enumerate(self.time):
                    vals = do_calculations_in_frame(necessary_equations, self.us_equation, resin, i,
                                                    output_header.var_IDs, output_header.np_float_type)
                    resout.write_entire_frame(output_header, time_i, vals)
        logging.info('Finished writing the output')

        # do some tests on the results
        # with Serafin.Read(filename, self.language) as resin:
        #     resin.read_header()
        #     resin.get_time()
        #     print('output file has variables', resin.header.var_IDs)
        #     print('US', resin.read_var_in_frame(0, 'US')[1:10])


def exception_hook(exctype, value, traceback):
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == '__main__':
    # suppress explicitly traceback silencing
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    widget = SerafinToolInterface()
    try:
        app.exec_()
    except:
        print('exiting')

