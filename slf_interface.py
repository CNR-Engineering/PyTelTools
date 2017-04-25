
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

        self.setFixedSize(900, 900)
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
        self.btnOpen.resize(self.btnOpen.sizeHint())

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
            tw.setFixedWidth(300)
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
        self.secondTable.setFixedHeight(500)

        # create a button for interpreting W from user-defined friction law
        self.btnAddUS = QPushButton('Add US from friction law', self)
        self.btnAddUS.setToolTip('<b>Compute</b> US based on a friction law')
        self.btnAddUS.resize(self.btnAddUS.sizeHint())
        self.btnAddUS.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self)
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.resize(self.btnSubmit.sizeHint())

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
        glayout = QGridLayout()
        glayout.setHorizontalSpacing(20)
        glayout.setHorizontalSpacing(30)
        glayout.addWidget(self.langBox, 1, 1)
        glayout.addWidget(QLabel('Input file'), 1, 2)
        glayout.addWidget(self.inNameBox, 1, 3)
        glayout.addWidget(self.btnOpen, 2, 1)
        glayout.addWidget(QLabel('Summary'), 2, 2)
        glayout.addWidget(self.summaryTextBox, 2, 3)

        glayout.addItem(QSpacerItem(1, 30), 3, 2)
        glayout.addWidget(QLabel('Variables'), 4, 2)
        hlayout = QHBoxLayout()

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('                                 Available variables'))
        vlayout.addWidget(self.firstTable)
        vlayout.addItem(QSpacerItem(1, 50))
        vlayout.addWidget(self.btnAddUS)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('                                 Output variables'))
        vlayout.addWidget(self.secondTable)
        hlayout.addLayout(vlayout)
        hlayout.setAlignment(Qt.AlignTop)

        glayout.addLayout(hlayout, 4, 3)

        glayout.addWidget(QLabel('   Drag and drop \n   available variables (left) to\n   '
                                 'output variables (right)'), 4, 1)

        glayout.addItem(QSpacerItem(10, 100), 5, 1)
        glayout.addWidget(self.singlePrecisionBox, 6, 1)
        glayout.addWidget(self.btnSubmit, 7, 1)

        vlayout = QVBoxLayout()
        vlayout.addLayout(glayout)
        vlayout.addItem(QSpacerItem(800, 100))

        vlayout.addWidget(QLabel('   Message logs'))
        vlayout.addWidget(self.logTextBox.widget)
        self.setLayout(vlayout)

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

