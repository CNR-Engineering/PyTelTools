import sys
import logging
import datetime
import numpy as np

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd
from itertools import islice, cycle

from slf import Serafin
from geom import Shapefile, BlueKenue
from gui.util import MapViewer, LineMapCanvas, QPlainTextEditLogger, ColumnColorEditor, TelToolWidget, OutputThread, \
    testOpen, TableWidgetDragRows, OutputProgressDialog, LoadMeshDialog, handleOverwrite, PlotViewer, SimpleTimeDateSelection


class WriteCSVProcess(OutputThread):
    def __init__(self, mesh):
        super().__init__()
        self.mesh = mesh

    def write_header(self, output_stream, selected_vars):
        output_stream.write('Line')
        for header in ['time', 'x', 'y', 'distance'] + selected_vars:
            output_stream.write(';')
            output_stream.write(header)
        output_stream.write('\n')

    def write_csv(self, input_stream, selected_vars, output_stream, line_interpolators,
                        indices_nonemtpy):
        self.write_header(output_stream, selected_vars)

        nb_lines = len(indices_nonemtpy)

        for u, id_line in enumerate(indices_nonemtpy):
            line_interpolator, distances = line_interpolators[id_line]

            for index, time in enumerate(input_stream.time):
                if self.canceled:
                    return
                var_values = []
                for var in selected_vars:
                    var_values.append(input_stream.read_var_in_frame(index, var))

                for (x, y, (i, j, k), interpolator), distance in zip(line_interpolator, distances):
                    if self.canceled:
                        return
                    output_stream.write(str(id_line+1))
                    output_stream.write(';')
                    output_stream.write(str(time))

                    output_stream.write(';')
                    output_stream.write('%.6f' % x)
                    output_stream.write(';')
                    output_stream.write('%.6f' % y)
                    output_stream.write(';')
                    output_stream.write('%.6f' % distance)

                    for i_var, var in enumerate(selected_vars):
                        values = var_values[i_var]
                        output_stream.write(';')
                        output_stream.write('%.6f' % interpolator.dot(values[[i, j, k]]))
                    output_stream.write('\n')

            self.tick.emit(int(100 * (u+1) / nb_lines))
            QApplication.processEvents()


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        canvas = LineMapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

        self.filename = None
        self.header = None
        self.language = 'fr'
        self.time = []
        self.mesh = None

        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []  # without intersection points

        self._initWidgets()  # some instance attributes will be set there
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

        # create the button open Serafin
        self.btnOpenSerafin = QPushButton('Load\nSerafin', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenSerafin.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSerafin.setFixedSize(105, 50)

        # create the button open lines
        self.btnOpenLines = QPushButton('Load\nLines', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenLines.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenLines.setFixedSize(105, 50)
        self.btnOpenLines.setEnabled(False)

        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.linesNameBox = QPlainTextEdit()
        self.linesNameBox.setReadOnly(True)
        self.linesNameBox.setFixedHeight(50)

        # create the map button
        self.btnMap = QPushButton('Locate lines\non map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.btnMap.setFixedSize(135, 50)
        self.btnMap.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenLines.clicked.connect(self.btnOpenLinesEvent)
        self.btnMap.clicked.connect(self.btnMapEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addWidget(self.btnOpenSerafin)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnOpenLines)
        hlayout.addWidget(self.btnMap)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Input file'), 1, 1)
        glayout.addWidget(self.serafinNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.addWidget(QLabel('     Lines file'), 3, 1)
        glayout.addWidget(self.linesNameBox, 3, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _reinitInput(self, filename):
        self.filename = filename
        self.has_map = False
        self.serafinNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.header = None
        self.time = []

        self.btnMap.setEnabled(False)
        self.mesh = None
        self.btnOpenLines.setEnabled(False)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def _resetDefaultOptions(self):
        nb_nonempty = 0

        self.line_interpolators = []
        self.line_interpolators_internal = []

        for line in self.lines:
            line_interpolators, distances, \
                line_interpolators_internal, distances_internal = self.mesh.get_line_interpolators(line)
            if line_interpolators:
                nb_nonempty += 1
            self.line_interpolators.append((line_interpolators, distances))
            self.line_interpolators_internal.append((line_interpolators_internal, distances_internal))

        if nb_nonempty == 0:
            self.lines = []
            self.line_interpolators = []
            self.line_interpolators_internal = []

            self.linesNameBox.clear()
            self.parent.reset()

        else:
            old_filename = self.linesNameBox.toPlainText().split('\n')[0]
            self.linesNameBox.clear()
            self.linesNameBox.appendPlainText(old_filename + '\n' + 'The file contains {} open polyline{}.'
                                              '{} line{} the mesh continuously.'.format(
                                              len(self.lines), 's' if len(self.lines) > 1 else '',
                                              nb_nonempty, 's intersect' if nb_nonempty > 1 else ' intersects'))

            self.has_map = False
            self.btnMap.setEnabled(True)
            self.parent.getInput()

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitInput(filename)

        with Serafin.Read(filename, self.language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # record the mesh for future visualization and calculations
            self.parent.inDialog()
            meshLoader = LoadMeshDialog('interpolation', resin.header)
            self.mesh = meshLoader.run()
            self.parent.outDialog()
            if meshLoader.thread.canceled:
                return

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.header = resin.header.copy()
            self.time = resin.time[:]

        self.btnOpenLines.setEnabled(True)
        self._resetDefaultOptions()

    def btnOpenLinesEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)',
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        is_i2s = filename[-4:] == '.i2s'
        is_shp = filename[-4:] == '.shp'

        if not is_i2s and not is_shp:
            QMessageBox.critical(self, 'Error', 'Only .i2s and .shp file formats are currently supported.',
                                 QMessageBox.Ok)
            return


        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []

        nb_nonempty = 0

        if is_i2s:
            with BlueKenue.Read(filename) as f:
                f.read_header()
                for poly_name, poly in f.get_open_polylines():
                    line_interpolators, distances, \
                        line_interpolators_internal, distances_internal = self.mesh.get_line_interpolators(poly)
                    if line_interpolators:
                        nb_nonempty += 1
                    self.lines.append(poly)
                    self.line_interpolators.append((line_interpolators, distances))
                    self.line_interpolators_internal.append((line_interpolators_internal, distances_internal))
        else:
            for poly in Shapefile.get_open_polylines(filename):
                line_interpolators, distances, \
                    line_interpolators_internal, distances_internal = self.mesh.get_line_interpolators(poly)
                if line_interpolators:
                    nb_nonempty += 1
                self.lines.append(poly)
                self.line_interpolators.append((line_interpolators, distances))
                self.line_interpolators_internal.append((line_interpolators_internal, distances_internal))
        if not self.lines:
            QMessageBox.critical(self, 'Error', 'The file does not contain any open polyline.',
                                 QMessageBox.Ok)
            return
        if nb_nonempty == 0:
            QMessageBox.critical(self, 'Error', 'No line intersects the mesh continuously.',
                                 QMessageBox.Ok)
            return

        logging.info('Finished reading the lines file %s' % filename)

        self.linesNameBox.clear()
        self.linesNameBox.appendPlainText(filename + '\n' + 'The file contains {} open polyline{}.'
                                          '{} line{} the mesh continuously.'.format(
                                          len(self.lines), 's' if len(self.lines) > 1 else '',
                                          nb_nonempty, 's intersect' if nb_nonempty > 1 else ' intersects'))

        self.has_map = False
        self.btnMap.setEnabled(True)
        self.parent.getInput()

    def btnMapEvent(self):
        if not self.has_map:
            self.map.canvas.reinitFigure(self.mesh, self.lines,
                                         ['Line %d' % (i+1) for i in range(len(self.lines))],
                                         list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                              len(self.lines))))

            self.has_map = True

            self.map.canvas.draw()
            self.has_map = True
        self.map.show()


class CSVTab(QWidget):
    def __init__(self, inputTab, parent):
        super().__init__()
        self.input = inputTab
        self.parent = parent

        self._initWidget()
        self._setLayout()
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

    def _initWidget(self):
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
            tw.setMinimumHeight(250)

        # create the options
        self.intersect = QCheckBox()
        self.intersect.setChecked(True)

        # create the submit button
        self.btnSubmit = QPushButton('Submit\nto .csv', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Write</b> output to .csv')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the output file name box
        self.csvNameBox = QLineEdit()
        self.csvNameBox.setReadOnly(True)
        self.csvNameBox.setFixedHeight(30)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        glayout = QGridLayout()
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.firstTable)
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.intersect)
        hlayout2.addWidget(QLabel('Add intersection points'))
        hlayout2.setAlignment(self.intersect, Qt.AlignLeft)
        hlayout2.addStretch()
        vlayout.addLayout(hlayout2)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))

        vlayout = QVBoxLayout()
        lb = QLabel('Output variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.secondTable)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(30, 1))
        glayout.addLayout(hlayout, 1, 1)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(30, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))

        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append(self.secondTable.item(i, 0).text())
        return selected

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

    def getInput(self):
        self._initVarTables()
        self.btnSubmit.setEnabled(True)
        self.csvNameBox.clear()

    def reset(self):
        self.intersect.setChecked(True)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.btnSubmit.setEnabled(False)
        self.csvNameBox.clear()

    def btnSubmitEvent(self):
        selected_var_IDs = self.getSelectedVariables()

        if not selected_var_IDs:
            QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                 QMessageBox.Ok)
            return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        options |= QFileDialog.DontConfirmOverwrite
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  'CSV Files (*.csv)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.csv':
            filename += '.csv'
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()

        indices_nonempty = [i for i in range(len(self.input.lines)) if self.input.line_interpolators[i][0]]

        # initialize the progress bar
        process = WriteCSVProcess(self.input.mesh)
        progressBar = OutputProgressDialog()

        with Serafin.Read(self.input.filename, self.input.language) as resin:
            resin.header = self.input.header
            resin.time = self.input.time

            progressBar.setValue(1)
            QApplication.processEvents()

            with open(filename, 'w') as fout:
                progressBar.connectToThread(process)

                if self.intersect.isChecked():
                    process.write_csv(resin, selected_var_IDs, fout,
                                      self.input.line_interpolators, indices_nonempty)
                else:
                    process.write_csv(resin, selected_var_IDs, fout,
                                      self.input.line_interpolators_internal, indices_nonempty)

        if not process.canceled:
            progressBar.outputFinished()
        progressBar.exec_()
        self.parent.outDialog()

        if process.canceled:
            self.csvNameBox.clear()
            return


class MultiVarControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.timeSelection = SimpleTimeDateSelection()

        # create widgets plot options
        self.lineBox = QComboBox()
        self.lineBox.setFixedHeight(30)
        self.lineBox.setMaximumWidth(200)
        self.intersection = QCheckBox()
        self.intersection.setChecked(True)
        self.addInternal = QCheckBox()

        self.unitBox = QComboBox()
        self.unitBox.setFixedHeight(30)
        self.unitBox.setMaximumWidth(200)
        self.varList = QListWidget()
        self.varList.setMaximumWidth(200)

        # create the compute button
        self.btnCompute = QPushButton('Compute', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCompute.setFixedSize(105, 50)

        # set layout
        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(self.timeSelection)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a polyline'))
        hlayout.addWidget(self.lineBox)
        hlayout.setAlignment(self.lineBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.intersection)
        lb = QLabel('Add intersection points')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.addInternal)
        lb = QLabel('Mark original points in plot')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        vlayout2 = QVBoxLayout()
        vlayout2.addWidget(self.unitBox)
        vlayout2.addWidget(self.varList)
        vlayout2.setSpacing(10)
        hlayout.addLayout(vlayout2)
        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignRight | Qt.AlignTop)
        hlayout.setSpacing(10)
        vlayout.addItem(hlayout)

        self.setLayout(vlayout)


class MultiVariableImageTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        self.var_table = {}
        self.current_vars = []
        self.var_colors = {}

        # set up a custom plot viewer
        self.editVarColorAct = QAction('Edit variable colors', self,
                                        icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.editColor)
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.editVarColorAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        self.plotViewer.canvas.figure.canvas.mpl_connect('motion_notify_event', self.plotViewer.mouseMove)

        # put it in a group box to get a nice border
        self.gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        self.gb.setLayout(ly)
        self.gb.setStyleSheet('QGroupBox {border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        self.gb.setMinimumWidth(600)

        self.control = MultiVarControlPanel()
        self.control.btnCompute.clicked.connect(self.btnComputeEvent)
        self.control.unitBox.currentTextChanged.connect(self._updateList)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.control)
        self.splitter.addWidget(self.gb)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(self.splitter)
        self.setLayout(mainLayout)

    def _updateList(self, text):
        self.control.varList.clear()
        unit = text.split(': ')[1]
        unit = '' if unit == 'None' else unit
        for var_ID in self.var_table[unit]:
            item = QListWidgetItem(var_ID)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            item.setCheckState(Qt.Unchecked)
            self.control.varList.addItem(item)

    def _getSelection(self):
        selection = []
        for row in range(self.control.varList.count()):
            item = self.control.varList.item(row)
            if item.checkState() == Qt.Checked:
                selection.append(item.text().split(' (')[0])
        return selection

    def editColor(self):
        var_labels = {var: var for var in self.var_colors}
        msg = ColumnColorEditor('Variable', self._getSelection(),
                                var_labels, self.var_colors,
                                self.plotViewer.defaultColors, self.plotViewer.colorToName)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.var_colors, var_labels, self.plotViewer.nameToColor)
        self.btnComputeEvent()

    def _compute(self, time_index, line_interpolator):
        values = []
        with Serafin.Read(self.input.filename, self.input.language) as input_stream:
            input_stream.header = self.input.header
            input_stream.time = self.input.time
            for var in self.current_vars:
                line_var_values = []
                var_values = input_stream.read_var_in_frame(time_index, var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)
        return values

    def btnComputeEvent(self):
        self.current_vars = self._getSelection()
        if not self.current_vars:
            QMessageBox.critical(self, 'Error', 'Select at least one variable to plot.',
                                 QMessageBox.Ok)
            return

        self.plotViewer.current_title = 'Values of variables along line %s' \
                                        % self.control.lineBox.currentText().split()[1]
        self.plotViewer.current_ylabel = 'Value (%s)' \
                                        % self.control.unitBox.currentText().split(': ')[1]

        line_id = int(self.control.lineBox.currentText().split()[1]) - 1
        if self.control.intersection.isChecked():
            line_interpolator, distances = self.input.line_interpolators[line_id]
        else:
            line_interpolator, distances = self.input.line_interpolators_internal[line_id]

        time_index = int(self.control.timeSelection.index.text()) - 1
        values = self._compute(time_index, line_interpolator)

        self.plotViewer.canvas.axes.clear()

        if self.control.addInternal.isChecked():
            if self.control.intersection.isChecked():
                line_interpolator_internal, distances_internal = self.input.line_interpolators_internal[line_id]
                values_internal = self._compute(time_index, line_interpolator_internal)

                for i, var in enumerate(self.current_vars):
                    self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2, label=var,
                                                     color=self.var_colors[var])
                    self.plotViewer.canvas.axes.plot(distances_internal, values_internal[i],
                                                     'o', color=self.var_colors[var])

            else:
                for i, var in enumerate(self.current_vars):
                    self.plotViewer.canvas.axes.plot(distances, values[i], 'o-', linewidth=2, label=var,
                                                     color=self.var_colors[var])

        else:
            for i, var in enumerate(self.current_vars):
                self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2, label=var,
                                                 color=self.var_colors[var])

        self.plotViewer.canvas.axes.legend()
        self.plotViewer.canvas.axes.grid(linestyle='dotted')
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()

    def reset(self):
        self.control.addInternal.setChecked(False)
        self.control.intersection.setChecked(True)
        self.control.lineBox.clear()
        self.var_table = {}
        self.current_vars = []
        self.var_colors = {}
        self.control.varList.clear()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = ''
        self.plotViewer.current_xlabel = 'Cumulative distance (M)'
        self.plotViewer.current_ylabel = ''
        self.control.timeSelection.clearText()

    def getInput(self):
        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        frames = list(map(lambda x: start_time + datetime.timedelta(seconds=x), self.input.time))
        self.control.timeSelection.initTime(self.input.time, frames)

        for i in range(len(self.input.lines)):
            id_line = str(i+1)
            if self.input.line_interpolators[i][0]:
                self.control.lineBox.addItem('Line %s' % id_line)
        for var_ID, var_name, var_unit in zip(self.input.header.var_IDs, self.input.header.var_names,
                                              self.input.header.var_units):
            var_unit = var_unit.decode('utf-8').strip()
            var_name = var_name.decode('utf-8').strip()
            if var_unit in self.var_table:
                self.var_table[var_unit].append('%s (%s)' % (var_ID, var_name))
            else:
                self.var_table[var_unit] = ['%s (%s)' % (var_ID, var_name)]

        for var_unit in self.var_table:
            if not var_unit:
                self.control.unitBox.addItem('Unit: None')
            else:
                self.control.unitBox.addItem('Unit: %s' % var_unit)
        if 'M' in self.var_table:
            self.control.unitBox.setCurrentIndex(list(self.var_table.keys()).index('M'))
        self._updateList(self.control.unitBox.currentText())

        # initialize default variable colors
        j = 0
        for var_ID in self.input.header.var_IDs:
            j %= len(self.plotViewer.defaultColors)
            self.var_colors[var_ID] = self.plotViewer.defaultColors[j]
            j += 1


class MultiFrameControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        # create widgets plot options
        self.lineBox = QComboBox()
        self.lineBox.setFixedHeight(30)
        self.lineBox.setMaximumWidth(200)
        self.varBox = QComboBox()
        self.varBox.setMaximumWidth(200)
        self.varBox.setFixedHeight(30)

        self.timeTable = QTableWidget()
        self.timeTable.setColumnCount(3)
        self.timeTable.setHorizontalHeaderLabels(['Index', 'Time (s)', 'Date'])
        vh = self.timeTable.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(20)
        hh = self.timeTable.horizontalHeader()
        hh.setDefaultSectionSize(110)
        self.timeTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.timeTable.setSelectionMode(QAbstractItemView.NoSelection)
        self.timeTable.setMinimumHeight(300)
        self.timeTable.setMaximumWidth(400)

        # create the compute button
        self.btnCompute = QPushButton('Compute', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCompute.setFixedSize(105, 50)
        self.intersection = QCheckBox()
        self.intersection.setChecked(True)
        self.addInternal = QCheckBox()

        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a polyline'))
        hlayout.addWidget(self.lineBox)
        hlayout.setAlignment(self.lineBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a variable'))
        hlayout.addWidget(self.varBox)
        hlayout.setAlignment(self.varBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.intersection)
        lb = QLabel('Add intersection points')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.addInternal)
        lb = QLabel('Mark original points in plot')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.timeTable)

        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignRight | Qt.AlignTop)
        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)


class MultiFrameImageTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        # set up a custom plot viewer
        self.editFrameColorAct = QAction('Edit frame colors', self,
                                        icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.editColor)
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.editFrameColorAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        self.plotViewer.canvas.figure.canvas.mpl_connect('motion_notify_event', self.plotViewer.mouseMove)

        self.frame_colors = {}

        # put it in a group box to get a nice border
        self.gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        self.gb.setLayout(ly)
        self.gb.setStyleSheet('QGroupBox {border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        self.gb.setMinimumWidth(600)

        self.control = MultiFrameControlPanel()
        self.splitter = QSplitter()

        self.splitter.addWidget(self.control)
        self.splitter.addWidget(self.gb)

        mainLayout = QHBoxLayout()

        mainLayout.addWidget(self.splitter)
        self.setLayout(mainLayout)
        self.control.btnCompute.clicked.connect(self.btnComputeEvent)

    def _getTime(self):
        time_indices = []
        for row in range(self.control.timeTable.rowCount()):
            if self.control.timeTable.item(row, 0).checkState() == Qt.Checked:
                time_indices.append(int(self.control.timeTable.item(row, 0).text()) - 1)
        return time_indices

    def _compute(self, time_indices, line_interpolator, current_var):
        values = []
        with Serafin.Read(self.input.filename, self.input.language) as input_stream:
            input_stream.header = self.input.header
            input_stream.time = self.input.time
            for index in time_indices:
                line_var_values = []
                var_values = input_stream.read_var_in_frame(index, current_var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)
        return values

    def editColor(self):
        frame_labels = {i: 'Frame %d' % (i+1) for i in self.frame_colors}
        msg = ColumnColorEditor('Frame', self._getTime(),
                                frame_labels, self.frame_colors,
                                self.plotViewer.defaultColors, self.plotViewer.colorToName)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.frame_colors, frame_labels, self.plotViewer.nameToColor)
        self.btnComputeEvent()

    def btnComputeEvent(self):
        time_indices = self._getTime()
        if not time_indices:
            QMessageBox.critical(self, 'Error', 'Select at least one frame to plot.',
                                 QMessageBox.Ok)
            return

        current_var = self.control.varBox.currentText().split(' (')[0]
        self.plotViewer.current_title = 'Values of %s along line %s' % (current_var,
                                                                        self.control.lineBox.currentText().split()[1])
        var_index = self.input.header.var_IDs.index(current_var)
        self.plotViewer.current_ylabel = '%s (%s)' % (self.input.header.var_names[var_index].decode('utf-8').strip(),
                                                      self.input.header.var_units[var_index].decode('utf-8').strip())

        line_id = int(self.control.lineBox.currentText().split()[1]) - 1
        if self.control.intersection.isChecked():
            line_interpolator, distances = self.input.line_interpolators[line_id]
        else:
            line_interpolator, distances = self.input.line_interpolators_internal[line_id]

        values = self._compute(time_indices, line_interpolator, current_var)

        self.plotViewer.canvas.axes.clear()

        if self.control.addInternal.isChecked():
            if self.control.intersection.isChecked():
                line_interpolator_internal, distances_internal = self.input.line_interpolators_internal[line_id]
                values_internal = self._compute(time_indices, line_interpolator_internal, current_var)

                for i, index in enumerate(time_indices):
                    self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2,
                                                     label='Frame %d' % (index+1), color=self.frame_colors[index])
                    self.plotViewer.canvas.axes.plot(distances_internal, values_internal[i],
                                                     'o', color=self.frame_colors[index])

            else:
                for i, index in enumerate(time_indices):
                    self.plotViewer.canvas.axes.plot(distances, values[i], 'o-', linewidth=2,
                                                     label='Frame %d' % (index+1), color=self.frame_colors[index])

        else:
            for i, index in enumerate(time_indices):
                self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2,
                                                 label='Frame %d' % (index+1), color=self.frame_colors[index])

        self.plotViewer.canvas.axes.legend()
        self.plotViewer.canvas.axes.grid(linestyle='dotted')
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()

    def reset(self):
        self.control.addInternal.setChecked(False)
        self.control.intersection.setChecked(True)
        self.control.lineBox.clear()
        self.control.varBox.clear()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = ''
        self.plotViewer.current_xlabel = 'Cumulative distance (M)'
        self.plotViewer.current_ylabel = ''
        self.control.timeTable.setRowCount(0)
        self.frame_colors = {}

    def getInput(self):
        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        frames = list(map(lambda x: start_time + datetime.timedelta(seconds=x), self.input.time))

        j = 0
        for index, value, date in zip(range(len(self.input.time)), self.input.time, frames):
            index_item = QTableWidgetItem(str(1+index))
            value_item = QTableWidgetItem(str(value))
            date_item = QTableWidgetItem(str(date))
            index_item.setCheckState(Qt.Unchecked)
            self.control.timeTable.insertRow(index)
            self.control.timeTable.setItem(index, 0, index_item)
            self.control.timeTable.setItem(index, 1, value_item)
            self.control.timeTable.setItem(index, 2, date_item)

            # initialize default frame colors
            j %= len(self.plotViewer.defaultColors)
            self.frame_colors[index] = self.plotViewer.defaultColors[j]
            j += 1

        for i in range(len(self.input.lines)):
            id_line = str(i+1)
            if self.input.line_interpolators[i][0]:
                self.control.lineBox.addItem('Line %s' % id_line)
        for var_ID, var_name in zip(self.input.header.var_IDs, self.input.header.var_names):
            var_name = var_name.decode('utf-8').strip()
            self.control.varBox.addItem('%s (%s)' % (var_ID, var_name))


class LinesGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = InputTab(self)
        self.csvTab = CSVTab(self.input, self)
        self.multiVarTab = MultiVariableImageTab(self.input)
        self.multiFrameTab = MultiFrameImageTab(self.input)

        self.setWindowTitle('Interpolate values of variables along lines')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.csvTab, 'Output to CSV')
        self.tab.addTab(self.multiVarTab, 'Visualization (MultiVar)')
        self.tab.addTab(self.multiFrameTab, 'Visualization (MultiFrame)')

        self.tab.setTabEnabled(1, False)
        self.tab.setTabEnabled(2, False)
        self.tab.setTabEnabled(3, False)

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def reset(self):
        for i, tab in enumerate([self.csvTab, self.multiVarTab, self.multiFrameTab]):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def getInput(self):
        for i, tab in enumerate([self.csvTab, self.multiVarTab, self.multiFrameTab]):
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
    widget = LinesGUI()
    widget.show()
    app.exec_()