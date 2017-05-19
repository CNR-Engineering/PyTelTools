import sys
import os
import logging
import copy
import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd

from slf import Serafin
from slf.interpolation import Interpolator, MeshInterpolator
from geom import Shapefile
from gui.util import TemporalPlotViewer, MapViewer, MapCanvas, QPlainTextEditLogger, TableWidgetDragRows, OutputProgressDialog


class MeshInterpolatorGUI(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, input_header):
        super().__init__()
        self.mesh = MeshInterpolator(input_header)

    def get_point_interpolators(self, points):
        nb_points = len(points)
        is_inside = [False] * nb_points
        point_interpolators = [None] * nb_points
        nb_inside = 0

        # updating the progress bar for every 5% of triangles processed
        nb_processed = 0
        current_percent = 0
        five_percent_triangles = self.mesh.nb_triangles * 0.05

        for (i, j, k), t in self.mesh.triangles.items():
            nb_processed += 1
            if nb_processed > five_percent_triangles:
                nb_processed = 0
                current_percent += 5
                self.tick.emit(current_percent)
                # QApplication.processEvents()

            t_interpolator = Interpolator(t)
            for p_index, (x, y) in enumerate(points):
                if is_inside[p_index]:
                    continue
                p_is_inside, p_interpolator = t_interpolator.is_in_triangle(x, y)
                if p_is_inside:
                    is_inside[p_index] = True
                    nb_inside += 1
                    point_interpolators[p_index] = ((i, j, k), p_interpolator)
            if nb_inside == nb_points:
                break

        return is_inside, point_interpolators

    def write_header(self, output_stream, selected_vars, points):
        output_stream.write('time')
        output_stream.write(';')
        for x, y in points:
            for var in selected_vars:
                output_stream.write('%s (%.4f, %.4f)' % (var, x, y))
                output_stream.write(';')
        output_stream.write('\n')

    def write_csv(self, input_stream, output_time, selected_vars, output_stream, points, point_interpolators):
        self.write_header(output_stream, selected_vars, points)

        nb_selected_vars = len(selected_vars)
        nb_frames = len(output_time)

        for index, time in enumerate(output_time):
            output_stream.write(str(time))
            output_stream.write(';')

            var_values = []
            for var in selected_vars:
                var_values.append(input_stream.read_var_in_frame(index, var))

            for (i, j, k), interpolator in point_interpolators:
                for index_var in range(nb_selected_vars):
                    output_stream.write('%.6f' % interpolator.dot(var_values[index_var][[i, j, k]]))
                    output_stream.write(';')

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


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

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
        self.attribute_table = AttributeTable()

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setMinimumWidth(800)

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
        self.csvNameBox = QLineEdit()
        self.csvNameBox.setReadOnly(True)
        self.csvNameBox.setFixedHeight(30)

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

        self.timeSampling = QLineEdit('1')
        self.timeSampling.setFixedWidth(50)

        # create the submit button
        self.btnMap = QPushButton('Locate points\non map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.btnMap.setFixedSize(135, 50)
        self.btnMap.setEnabled(False)

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

    def _setLayout(self):
        mainLayout = QVBoxLayout()
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

        mainLayout.addItem(QSpacerItem(10, 15))
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
        self.points = []
        self.point_interpolators = []
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.btnMap.setEnabled(False)
        self.btnOpenAttributes.setEnabled(False)
        self.mesh = None
        self.pointsNameBox.clear()
        self.btnOpenPoints.setEnabled(True)
        self.timeSampling.setText('1')

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

        self.parent.reset()

    def _initVarTables(self):
        for i, (id, name, unit) in enumerate(zip(self.header.var_IDs, self.header.var_names, self.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, id_item)
            self.firstTable.setItem(i, 1, name_item)
            self.firstTable.setItem(i, 2, unit_item)

    def _handleOverwrite(self, filename):
        """!
        @brief (Used in btnSubmitEvent) Handle manually the overwrite option when saving output file
        """
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                return None
            return True
        return False

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

        with Serafin.Read(filename, self.language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            self._reinitInput(filename)

            # record the time series
            resin.get_time()

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # record the mesh for future visualization and calculations
            logging.info('Starting to process the mesh')
            self.mesh = MeshInterpolatorGUI(resin.header)
            logging.info('Done')

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        # displaying the available variables
        self._initVarTables()

    def btnOpenPointsEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .shp file', '',
                                                  'Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return
        is_shp = filename[-4:] == '.shp'

        if not is_shp:
            QMessageBox.critical(self, 'Error', 'Only .shp file formats are currently supported.',
                                 QMessageBox.Ok)
            return

        self.points = []
        attributes = []

        fields, indices = Shapefile.get_attribute_names(filename)
        for point, attribute in Shapefile.get_points(filename, indices):
            self.points.append(point)
            attributes.append(attribute)

        if not self.points:
            QMessageBox.critical(self, 'Error', 'The file does not contain any points.',
                                 QMessageBox.Ok)
            return
        logging.info('Finished reading the points file %s' % filename)


        # locate the points in the msh
        logging.info('Starting to process the points')
        self.parent.inDialog()

        # initialize the progress bar
        progressBar = OutputProgressDialog('Processing the points. Please wait.', 'Processing the points...')
        progressBar.setValue(1)
        QApplication.processEvents()
        progressBar.connectToThread(self.mesh)

        is_inside, self.point_interpolators = self.mesh.get_point_interpolators(self.points)

        self.attribute_table.getData(self.points, is_inside, fields, attributes)
        logging.info('Done')

        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()
        self.parent.outDialog()


        self.pointsNameBox.clear()
        self.pointsNameBox.appendPlainText(filename + '\n' + 'The file contains {} point{}.'
                                                             '{} points are inside the mesh.'.format(
                                           len(self.points), 's' if len(self.points) > 1 else '',
                                           sum(map(int, is_inside))))

        self.has_map = False
        self.btnMap.setEnabled(True)
        self.btnOpenAttributes.setEnabled(True)

        self.parent.getInput()

    def btnOpenAttributesEvent(self):
        self.attribute_table.show()

    def btnMapEvent(self):
        if not self.has_map:
            self.map.canvas.initFigure(self.mesh.mesh)
            self.map.canvas.axes.scatter(*zip(*self.points))
            self.map.canvas.draw()
            self.has_map = True
        self.map.show()


class WriteCSVTab(QWidget):
    def __init__(self, input, parent):
        super().__init__()
        self.input = input
        self.parent = parent

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

        # bind events
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

        # set layout
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _handleOverwrite(self, filename):
        """!
        @brief (Used in btnSubmitEvent) Handle manually the overwrite option when saving output file
        """
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                logging.info('Output canceled')
                return None
            return True
        return False

    def reset(self):
        self.btnSubmit.setEnabled(False)

    def getInput(self):
        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
        selected_var_IDs = self.input.getSelectedVariables()

        if not selected_var_IDs:
            QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                 QMessageBox.Ok)
            return

        try:
            sampling_frequency = int(self.input.timeSampling.text())
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be a number!',
                                 QMessageBox.Ok)
            return
        if sampling_frequency < 1 or sampling_frequency > len(self.input.time):
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be in the range [1; nbFrames]!',
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
        overwrite = self._handleOverwrite(filename)
        if overwrite is None:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()

        selected_time = self.input.time[::sampling_frequency]
        indices_inside = [i for i in range(len(self.input.points)) if self.input.point_interpolators[i] is not None]

        # initialize the progress bar
        progressBar = OutputProgressDialog()
        progressBar.connectToThread(self.input.mesh)

        with Serafin.Read(self.input.filename, self.input.language) as resin:
            resin.header = self.input.header
            resin.time = self.input.time

            progressBar.setValue(1)
            QApplication.processEvents()

            with open(filename, 'w') as fout:
                self.input.mesh.write_csv(resin, selected_time, selected_var_IDs, fout,
                                          [self.input.points[i] for i in indices_inside],
                                          [self.input.point_interpolators[i] for i in indices_inside])

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()
        self.parent.outDialog()


class PointsGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.input = InputTab(self)
        self.csvTab = WriteCSVTab(self.input, self)
        self.setWindowTitle('Interpolate values of variables on points')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.csvTab, 'Write CSV')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; width: 300px; }')
        self.tab.currentChanged.connect(self.switch_tab)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)

    def switch_tab(self, index):
        if index == 1:
            if self.input.secondTable.rowCount() == 0:
                QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                     QMessageBox.Ok)
                self.tab.setCurrentIndex(0)
                return

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
        for i, tab in enumerate([self.csvTab]):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def getInput(self):
        for i, tab in enumerate([self.csvTab]):
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
    widget = PointsGUI()
    widget.show()
    app.exec_()