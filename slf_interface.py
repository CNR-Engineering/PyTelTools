
import os
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import logging
import copy
import numpy as np
from slf import Serafin
from slf.SerafinBasicVariables import get_new_var_IDs

_YELLOW = QColor(245, 255, 207)

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
        self.addition_vars = []

        self.initWidgets()  # some instance attributes will be set there

        self.setFixedSize(900, 900)
        self.setWindowTitle('Serafin Tool')
        self._center()
        self.show()


    def initWidgets(self):
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
            tw.setFixedHeight(300)
            tw.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self)
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.resize(self.btnSubmit.sizeHint())

        # putting the widgets together and bind event handlers
        self._setLayout()
        self._bindEvents()


    def _bindEvents(self):
        # binding widget events
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

    def _setLayout(self):
        # setting the layout
        glayout = QGridLayout()
        glayout.setHorizontalSpacing(30)
        glayout.addWidget(self.langBox, 1, 1)
        glayout.addWidget(QLabel('Input file'), 1, 2)
        glayout.addWidget(self.inNameBox, 1, 3)
        glayout.addWidget(self.btnOpen, 2, 1)
        glayout.addWidget(QLabel('Summary'), 2, 2)
        glayout.addWidget(self.summaryTextBox, 2, 3)

        glayout.addWidget(QLabel('Variables'), 3, 2)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.firstTable)
        hlayout.addWidget(self.secondTable)
        glayout.addLayout(hlayout, 3, 3)

        glayout.addWidget(QLabel('   Drag and drop \n   available variables (left) to\n   '
                                 'output variables (right)'), 3, 1)

        glayout.addItem(QSpacerItem(10, 100), 4, 1)
        glayout.addWidget(self.btnSubmit, 5, 1)

        vlayout = QVBoxLayout()
        vlayout.addLayout(glayout)
        vlayout.addItem(QSpacerItem(800, 100))

        vlayout.addWidget(QLabel('   Message logs'))
        vlayout.addWidget(self.logTextBox.widget)
        self.setLayout(vlayout)

    def _center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _initVarTables(self):
        self.addition_vars = []
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)

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

        # find new computable variables
        new_vars = get_new_var_IDs(self.header.var_IDs)
        for var_ID in new_vars:
            var_name, var_unit = self.header.specifications.ID_to_name_unit(var_ID)
            self.addition_vars.append((var_ID, var_name, var_unit))

        # add new variables to the table
        for i, (id, name, unit) in enumerate(self.addition_vars):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.firstTable.setItem(offset+i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(offset+i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(offset+i, 2, QTableWidgetItem(unit_item))
            self.firstTable.item(offset+i, 0).setBackground(_YELLOW)  # set new variables colors to yellow
            self.firstTable.item(offset+i, 1).setBackground(_YELLOW)
            self.firstTable.item(offset+i, 2).setBackground(_YELLOW)

    def btnOpenEvent(self):
        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

        self.summaryTextBox.clear()

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', options=options)
        if not filename:
            return

        self.filename = filename
        self.inNameBox.setText(self.filename)


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

    def btnSubmitEvent(self):
        # check if everything is ready to submit
        if self.header is None:
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

        # handle overwrite
        overwrite = False
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it ?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                logging.info('Output canceled')
                return
            overwrite = True

        # do some calculations
        with Serafin.Read(self.filename, self.language) as resin:
            resin.header = self.header
            resin.time = self.time
            print('U', resin.read_var_in_frame(2, 'U')[1:5])
            print('V', resin.read_var_in_frame(2, 'V')[1:5])

            with Serafin.Write(filename, self.language, overwrite) as resout:
                output_header = resin.header.copy()

                output_header.nb_var = 3
                output_header.var_IDs = ['U', 'V', 'M']
                output_header.var_names = [b'VITESSE U       ', b'VITESSE V       ', b'VITESSE SCALAIRE']
                output_header.var_units = [b'M/S             ', b'M/S             ', b'M/S             ']

                resout.write_header(output_header)

                for i, i_time in enumerate(resin.time):
                    vals = resin.read_vars_in_frame(i, ['U', 'V'])
                    vals = np.vstack([vals, np.sqrt(np.square(vals[0]) + np.square(vals[1]))])
                    resout.write_entire_frame(output_header, i_time, vals)
        logging.info('Finished writing the output')

        # do some tests on the results
        with Serafin.Read(filename, self.language) as resin:
            resin.read_header()
            resin.get_time()
            print('output file has variablees', resin.header.var_IDs)
            print('U', resin.read_var_in_frame(2, 'U')[1:5])
            print('M', resin.read_var_in_frame(2, 'V')[1:5])
            print('M', resin.read_var_in_frame(2, 'M')[1:5])




if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = SerafinToolInterface()
    sys.exit(app.exec_())
