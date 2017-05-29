import sys
import logging
import copy
import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd

from slf import Serafin
from geom import Shapefile
from gui.util import TemporalPlotViewer, MapViewer, MapCanvas, QPlainTextEditLogger, \
    TableWidgetDragRows, OutputProgressDialog, LoadMeshDialog, handleOverwrite, TelToolWidget, testOpen


class WriteCSVProcess(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, mesh):
        super().__init__()
        self.mesh = mesh

    def write_header(self, output_stream, selected_vars, points):
        output_stream.write('time')
        for x, y in points:
            for var in selected_vars:
                output_stream.write(';')
                output_stream.write('%s (%.4f, %.4f)' % (var, x, y))
        output_stream.write('\n')

    def write_csv(self, input_stream, output_time, selected_vars, output_stream, points, point_interpolators):
        self.write_header(output_stream, selected_vars, points)

        nb_selected_vars = len(selected_vars)
        nb_frames = len(output_time)

        for index, time in enumerate(output_time):
            output_stream.write(str(time))

            var_values = []
            for var in selected_vars:
                var_values.append(input_stream.read_var_in_frame(index, var))

            for (i, j, k), interpolator in point_interpolators:
                for index_var in range(nb_selected_vars):
                    output_stream.write(';')
                    output_stream.write('%.6f' % interpolator.dot(var_values[index_var][[i, j, k]]))

            output_stream.write('\n')
            self.tick.emit(int(100 * (index+1) / nb_frames))
            QApplication.processEvents()


class AttributeTable(QTableWidget):
    def __init__(self):
        super().__init__()
        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(100)
        self.resize(850, 600)
        self.setWindowTitle('Attribute table')

    def getData(self, points, is_inside, fields, all_attributes):
        self.setRowCount(0)
        true_false = {True: 'Yes', False: 'No'}

        self.setColumnCount(3 + len(fields))
        self.setHorizontalHeaderLabels(['x', 'y', 'IsInside'] + fields)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        i = 0
        for (x, y), inside, attributes in zip(points, is_inside, all_attributes):
            self.insertRow(i)
            self.setItem(i, 0, QTableWidgetItem('%.4f' % x))
            self.setItem(i, 1, QTableWidgetItem('%.4f' % y))
            self.setItem(i, 2, QTableWidgetItem(true_false[inside]))
            for j, a in enumerate(attributes):
                self.setItem(i, j+3, QTableWidgetItem(a))
            i += 1


class AttributeDialog(QDialog):
    def __init__(self, attribute_table):
        super().__init__()
        self.attribute_table = attribute_table
        self.attribute_table.setSelectionBehavior(QAbstractItemView.SelectColumns)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkSelection)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.attribute_table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Select an attribute as labels')
        self.resize(850, 500)
        self.selection = []

    def checkSelection(self):
        column = self.attribute_table.currentColumn()
        if column == -1:
            QMessageBox.critical(self, 'Error', 'Select at least one attribute.',
                                 QMessageBox.Ok)
            return
        self.selection = []
        for i in range(self.attribute_table.rowCount()):
            self.selection.append(self.attribute_table.item(i, column).text())
        self.accept()


class PointLabelEditor(QDialog):
    def __init__(self, column_labels, name, points, is_inside, fields, all_attributes):
        super().__init__()
        attribute_table = AttributeTable()
        attribute_table.getData(points, is_inside, fields, all_attributes)
        self.attribute_dialog = AttributeDialog(attribute_table)

        self.btnAttribute = QPushButton('Use attributes')
        self.btnAttribute.setFixedSize(105, 50)
        self.btnAttribute.clicked.connect(self.btnAttributeEvent)

        self.btnDefault = QPushButton('Default')
        self.btnDefault.setFixedSize(105, 50)
        self.btnDefault.clicked.connect(self.btnDefaultEvent)

        self.column_labels = column_labels
        self.table = QTableWidget()
        self.table .setColumnCount(2)
        self.table .setHorizontalHeaderLabels([name, 'Label'])
        row = 0
        for column, label in column_labels.items():
            label = column_labels[column]
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(label)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnAttribute)
        hlayout.addWidget(self.btnDefault)
        hlayout.setSpacing(10)
        vlayout.addLayout(hlayout, Qt.AlignHCenter)
        vlayout.addItem(QSpacerItem(1, 15))
        vlayout.addWidget(QLabel('Click on the label to modify'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setWindowTitle('Change %s labels' % name)
        self.resize(self.sizeHint())
        self.setMinimumWidth(300)

    def btnDefaultEvent(self):
        self.table.setRowCount(0)
        row = 0
        for column in self.column_labels.keys():
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(column)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

    def btnAttributeEvent(self):
        value = self.attribute_dialog.exec_()
        if value == QDialog.Rejected:
            return
        selected_labels = self.attribute_dialog.selection
        self.table.setRowCount(0)
        row = 0
        for column, label in zip(self.column_labels.keys(), selected_labels):
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(label)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

    def getLabels(self, old_labels):
        for row in range(self.table.rowCount()):
            column = self.table.item(row, 0).text()
            label = self.table.item(row, 1).text()
            old_labels[column] = label


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.old_frequency = '1'

        canvas = MapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

        self.filename = None
        self.header = None
        self.language = 'fr'
        self.time = []
        self.mesh = None

        self.points = []
        self.point_interpolators = []
        self.fields = []
        self.attributes = []
        self.attribute_table = AttributeTable()

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

        # create the button open points
        self.btnOpenPoints = QPushButton('Load\nPoints', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenPoints.setToolTip('<b>Open</b> a .shp file')
        self.btnOpenPoints.setFixedSize(105, 50)
        self.btnOpenPoints.setEnabled(False)

        self.btnOpenAttributes = QPushButton('Attributes\nTable', self, icon=self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.btnOpenAttributes.setToolTip('<b>Open</b> the attribute table')
        self.btnOpenAttributes.setFixedSize(105, 50)
        self.btnOpenAttributes.setEnabled(False)

        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.pointsNameBox = QPlainTextEdit()
        self.pointsNameBox.setReadOnly(True)
        self.pointsNameBox.setFixedHeight(50)

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

        self.timeSampling = QLineEdit('1')
        self.timeSampling.setFixedWidth(50)

        # create the map button
        self.btnMap = QPushButton('Locate points\non map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.btnMap.setFixedSize(135, 50)
        self.btnMap.setEnabled(False)

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

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPoints.clicked.connect(self.btnOpenPointsEvent)
        self.btnOpenAttributes.clicked.connect(self.btnOpenAttributesEvent)
        self.btnMap.clicked.connect(self.btnMapEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.timeSampling.editingFinished.connect(self._checkSamplingFrequency)

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
        hlayout.addWidget(self.btnOpenPoints)
        hlayout.addWidget(self.btnOpenAttributes)
        hlayout.addWidget(self.btnMap)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Input file'), 1, 1)
        glayout.addWidget(self.serafinNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.addWidget(QLabel('     Points file'), 3, 1)
        glayout.addWidget(self.pointsNameBox, 3, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
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

        glayout.addLayout(hlayout, 1, 1)
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(QLabel('Time sampling frequency'))
        hlayout.addWidget(self.timeSampling)
        hlayout.setAlignment(self.timeSampling, Qt.AlignLeft)
        hlayout.addStretch()
        glayout.addLayout(hlayout, 2, 1)

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

    def _reinitInput(self, filename):
        self.filename = filename
        self.has_map = False
        self.serafinNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.header = None
        self.time = []
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.btnMap.setEnabled(False)
        self.btnOpenAttributes.setEnabled(False)
        self.mesh = None
        self.btnOpenPoints.setEnabled(True)
        self.old_frequency = self.timeSampling.text()

        self.timeSampling.setText('1')
        self.btnSubmit.setEnabled(False)
        self.csvNameBox.clear()
        self.parent.tab.setTabEnabled(1, False)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def _resetDefaultOptions(self):
        if int(self.old_frequency) <= len(self.time):
            self.timeSampling.setText(self.old_frequency)

        is_inside, self.point_interpolators = self.mesh.get_point_interpolators(self.points)
        nb_inside = sum(map(int, is_inside))
        if nb_inside == 0:
            self.pointsNameBox.clear()
            self.points = []
            self.point_interpolators = []
        else:
            self.attribute_table.getData(self.points, is_inside, self.fields, self.attributes)
            old_filename = self.pointsNameBox.toPlainText().split('\n')[0]
            self.pointsNameBox.clear()
            self.pointsNameBox.appendPlainText(old_filename + '\n' + 'The file contains {} point{}.'
                                                                     '{} point{} inside the mesh.'.format(
                                               len(self.points), 's' if len(self.points) > 1 else '',
                                               nb_inside, 's are' if nb_inside > 1 else ' is'))
            self.btnSubmit.setEnabled(True)
            self.btnOpenAttributes.setEnabled(True)
            self.btnMap.setEnabled(True)

    def _initVarTables(self):
        for i, (id, name, unit) in enumerate(zip(self.header.var_IDs, self.header.var_names, self.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, id_item)
            self.firstTable.setItem(i, 1, name_item)
            self.firstTable.setItem(i, 2, unit_item)

    def _checkSamplingFrequency(self):
        try:
            sampling_frequency = int(self.timeSampling.text())
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be a number!',
                                 QMessageBox.Ok)
            self.timeSampling.setText('1')
            return
        if sampling_frequency < 1 or sampling_frequency > len(self.time):
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be in the range [1; nbFrames]!',
                                 QMessageBox.Ok)
            self.timeSampling.setText('1')
            return

    def getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append(self.secondTable.item(i, 0).text())
        return selected

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

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # record the mesh for future visualization and calculations
            logging.info('Processing the mesh')
            self.parent.inDialog()
            meshLoader = LoadMeshDialog('interpolation', resin.header)
            self.mesh = meshLoader.run()
            self.parent.outDialog()
            logging.info('Finished processing the mesh')

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        self._resetDefaultOptions()
        self.parent.imageTab.reset()

        # displaying the available variables
        self._initVarTables()

    def btnOpenPointsEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .shp file', '',
                                                  'Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        is_shp = filename[-4:] == '.shp'

        if not is_shp:
            QMessageBox.critical(self, 'Error', 'Only .shp file format is currently supported.',
                                 QMessageBox.Ok)
            return

        self.points = []
        self.attributes = []

        self.fields, indices = Shapefile.get_attribute_names(filename)
        for point, attribute in Shapefile.get_points(filename, indices):
            self.points.append(point)
            self.attributes.append(attribute)

        if not self.points:
            QMessageBox.critical(self, 'Error', 'The file does not contain any points.',
                                 QMessageBox.Ok)
            return
        logging.info('Finished reading the points file %s' % filename)

        is_inside, self.point_interpolators = self.mesh.get_point_interpolators(self.points)
        nb_inside = sum(map(int, is_inside))
        if nb_inside == 0:
            QMessageBox.critical(self, 'Error', 'No point inside the mesh.',
                                 QMessageBox.Ok)
            return

        self.attribute_table.getData(self.points, is_inside, self.fields, self.attributes)

        self.pointsNameBox.clear()
        self.pointsNameBox.appendPlainText(filename + '\n' + 'The file contains {} point{}.'
                                                             '{} point{} inside the mesh.'.format(
                                           len(self.points), 's' if len(self.points) > 1 else '',
                                           nb_inside, 's are' if nb_inside > 1 else ' is'))

        self.has_map = False
        self.btnMap.setEnabled(True)
        self.btnOpenAttributes.setEnabled(True)
        self.btnSubmit.setEnabled(True)
        self.csvNameBox.clear()
        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnOpenAttributesEvent(self):
        self.attribute_table.show()

    def btnMapEvent(self):
        if not self.has_map:
            self.map.canvas.initFigure(self.mesh)
            self.map.canvas.axes.scatter(*zip(*self.points))
            labels = ['%d' % (i+1) for i in range(len(self.points))]
            for label, (x, y) in zip(labels, self.points):
                self.map.canvas.axes.annotate(label, xy=(x, y), xytext=(-20, 20), fontsize=8,
                                              textcoords='offset points', ha='right', va='bottom',
                                              bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                                              arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

            self.map.canvas.draw()
            self.has_map = True
        self.map.show()

    def btnSubmitEvent(self):
        selected_var_IDs = self.getSelectedVariables()

        if not selected_var_IDs:
            QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                 QMessageBox.Ok)
            return

        sampling_frequency = int(self.timeSampling.text())

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

        selected_time = self.time[::sampling_frequency]
        indices_inside = [i for i in range(len(self.points)) if self.point_interpolators[i] is not None]

        # initialize the progress bar
        process = WriteCSVProcess(self.mesh)
        progressBar = OutputProgressDialog()
        progressBar.connectToThread(process)

        with Serafin.Read(self.filename, self.language) as resin:
            resin.header = self.header
            resin.time = self.time

            progressBar.setValue(1)
            QApplication.processEvents()

            with open(filename, 'w') as fout:
                process.write_csv(resin, selected_time, selected_var_IDs, fout,
                                  [self.points[i] for i in indices_inside],
                                  [self.point_interpolators[i] for i in indices_inside])

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()
        self.parent.outDialog()
        self.parent.imageTab.getData(selected_var_IDs, indices_inside)
        self.parent.tab.setTabEnabled(1, True)


class ImageTab(TemporalPlotViewer):
    def __init__(self, input):
        super().__init__('point')
        self.input = input

        self.has_map = False
        canvas = MapCanvas()
        self.map = MapViewer(canvas)

        self.var_IDs = []
        self.current_var = ''
        self.current_columns = ('Point 1',)

        self.openAttributes = QAction('Attributes\nTable', self,
                                      icon=self.style().standardIcon(QStyle.SP_FileDialogListView),
                                      triggered=self.openAttributesEvent)
        self.locatePoints = QAction('Locate points\non map', self,
                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                    triggered=self.input.btnMapEvent)
        self.input.map.closeEvent = lambda event: self.locatePoints.setEnabled(True)
        self.input.attribute_table.closeEvent = lambda event: self.openAttributes.setEnabled(True)

        self.selectVariable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                      icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))

        self.toolBar.addAction(self.locatePoints)
        self.toolBar.addAction(self.openAttributes)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.selectVariable)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locatePoints)
        self.pointsMenu = QMenu('&Data', self)
        self.pointsMenu.addAction(self.openAttributes)
        self.pointsMenu.addSeparator()
        self.pointsMenu.addAction(self.selectVariable)
        self.pointsMenu.addAction(self.selectColumnsAct)
        self.pointsMenu.addAction(self.editColumnNamesAct)
        self.pointsMenu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.pointsMenu)

    def _to_column(self, point):
        point_index = int(point.split()[1]) - 1
        x, y = self.input.points[point_index]
        return '%s (%.4f, %.4f)' % (self.current_var, x, y)

    def editColumns(self):
        msg = PointLabelEditor(self.column_labels, self.column_name,
                               self.input.points,
                               [self.input.point_interpolators[i] is not None for i in range(len(self.input.points))],
                               self.input.fields, self.input.attributes)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLabels(self.column_labels)
        self.replot()

    def _defaultYLabel(self, language):
        word = {'fr': 'de', 'en': 'of'}[language]
        return 'Values %s %s' % (word, self.current_var)

    def selectVariableEvent(self):
        msg = QDialog()
        combo = QComboBox()
        for var in self.var_IDs:
            combo.addItem(var)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(combo)
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText()
        self.current_ylabel = self._defaultYLabel(self.input.language)
        self.replot()

    def getData(self, var_IDs, point_indices):
        self.var_IDs = var_IDs
        self.current_var = var_IDs[0]

        # get the new data
        csv_file = self.input.csvNameBox.text()
        self.data = pd.read_csv(csv_file, header=0, sep=';')
        self.data.sort_values('time', inplace=True)

        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = ['Point %d' % (i+1) for i in point_indices]
        self.current_columns = self.columns[0:1]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.current_xlabel = self._defaultXLabel(self.input.language)
        self.current_ylabel = self._defaultYLabel(self.input.language)
        self.current_title = ''
        self.replot()

    def openAttributesEvent(self):
        self.openAttributes.setEnabled(False)
        self.input.attribute_table.show()

    def replot(self):
        self.canvas.axes.clear()
        for point in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[self._to_column(point)], '-', color=self.column_colors[point],
                                  linewidth=2, label=self.column_labels[point])
        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()

    def reset(self):
        self.has_map = False
        self.map.close()
        self.input.attribute_table.close()

        # reinitialize old graphical parameters
        super().reset()
        self.current_columns = ('Point 1',)


class PointsGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = InputTab(self)
        self.imageTab = ImageTab(self.input)
        self.setWindowTitle('Interpolate values of variables on points')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.imageTab, 'Visualize results')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 300px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)


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
    widget = PointsGUI()
    widget.show()
    app.exec_()