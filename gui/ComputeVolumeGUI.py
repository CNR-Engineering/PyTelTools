import sys
import logging
import copy
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd

from slf import Serafin
from slf.volume import VolumeCalculator
from geom import BlueKenue, Shapefile
from gui.util import TemporalPlotViewer, QPlainTextEditLogger, MapViewer, PolygonMapCanvas, \
    OutputProgressDialog, LoadMeshDialog, testOpen, handleOverwrite


class VolumeCalculatorThread(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                 time_sampling_frequency, mesh):
        super().__init__()

        self.calculator = VolumeCalculator(volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                                           time_sampling_frequency)
        self.mesh = mesh

    def run_calculator(self):
        self.tick.emit(6)
        QApplication.processEvents()

        logging.info('Starting to process the mesh')
        self.calculator.mesh = self.mesh
        self.tick.emit(15)
        QApplication.processEvents()

        self.calculator.construct_weights()
        self.tick.emit(30)
        QApplication.processEvents()
        logging.info('Finished processing the mesh')

        result = []
        init_values = None
        if self.calculator.second_var_ID == VolumeCalculator.INIT_VALUE:
            init_values = self.calculator.input_stream.read_var_in_frame(0, self.calculator.var_ID)

        for i, time_index in enumerate(self.calculator.time_indices):
            i_result = [str(self.calculator.input_stream.time[time_index])]

            values = self.calculator.input_stream.read_var_in_frame(time_index, self.calculator.var_ID)
            if self.calculator.second_var_ID is not None:
                if self.calculator.second_var_ID == VolumeCalculator.INIT_VALUE:
                    values -= init_values
                else:
                    second_values = self.calculator.input_stream.read_var_in_frame(time_index,
                                                                                   self.calculator.second_var_ID)
                    values -= second_values

            for j in range(len(self.calculator.polygons)):
                weight = self.calculator.weights[j]
                volume = self.calculator.volume_in_frame_in_polygon(weight, values, self.calculator.polygons[j])
                if self.calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append('%.6f' % v)
                else:
                    i_result.append('%.6f' % volume)
            result.append(i_result)

            self.tick.emit(30 + int(70 * (i+1) / len(self.calculator.time_indices)))
            QApplication.processEvents()

        return result

    def write_csv(self, output_stream):
        result = self.run_calculator()
        self.calculator.write_csv(result, output_stream)


class VolumePlotViewer(TemporalPlotViewer):
    def __init__(self, inputTab):
        super().__init__('polygon')
        self.input = inputTab

        # initialize the map for locating polygons
        canvas = PolygonMapCanvas()
        self.map = MapViewer(canvas)

        self.setWindowTitle('Visualize the temporal evolution of volumes')

        self.var_ID = None
        self.second_var_ID = None
        self.has_map = False

        self.current_columns = ('Polygon 1',)

        self.locatePolygons = QAction('Locate polygons\non map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                      triggered=self.locatePolygonsEvent)
        self.map.closeEvent = lambda event: self.locatePolygons.setEnabled(True)

        self.toolBar.addAction(self.locatePolygons)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locatePolygons)
        self.polyMenu = QMenu('&Polygons', self)
        self.polyMenu.addAction(self.selectColumnsAct)
        self.polyMenu.addAction(self.editColumnNamesAct)
        self.polyMenu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.polyMenu)

    def _defaultYLabel(self, language):
        word = {'fr': 'de', 'en': 'of'}[language]
        if self.second_var_ID == VolumeCalculator.INIT_VALUE:
            return 'Volume %s (%s - %s$_0$)' % (word, self.var_ID, self.var_ID)
        elif self.second_var_ID is None:
            return 'Volume %s %s' % (word, self.var_ID)
        return 'Volume %s (%s - %s)' % (word, self.var_ID, self.second_var_ID)

    def replot(self):
        self.canvas.axes.clear()
        for column in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[column], '-', color=self.column_colors[column],
                                  linewidth=2, label=self.column_labels[column])
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

    def getData(self):
        # get the new data
        csv_file = self.input.csvNameBox.text()
        self.data = pd.read_csv(csv_file, header=0, sep=';')
        self.data.sort_values('time', inplace=True)

        self.var_ID = self.input.var_ID
        self.second_var_ID = self.input.second_var_ID
        if self.input.header.date is not None:
            year, month, day, hour, minute, second = self.input.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = list(self.data)[1:]
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

    def locatePolygonsEvent(self):
        if not self.has_map:
            self.map.canvas.reinitFigure(self.input.mesh, self.input.polygons,
                                         map(self.column_labels.get, ['Polygon %d' % (i+1)
                                                                      for i in range(len(self.input.polygons))]))
            self.has_map = True
        self.locatePolygons.setEnabled(False)
        self.map.show()

    def reset(self):
        self.has_map = False
        self.map.close()

        super().reset()
        self.current_columns = ('Polygon 1',)


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.old_options = ('1', '', '0')
        self.filename = None
        self.header = None
        self.language = 'fr'
        self.time = []
        self.mesh = None
        self.polygons = []
        self.var_ID = None
        self.second_var_ID = None

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

        # create the button open Polygon
        self.btnOpenPolygon = QPushButton('Load\nPolygons', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenPolygon.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolygon.setFixedSize(105, 50)
        self.btnOpenPolygon.setEnabled(False)

        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.polygonNameBox = QPlainTextEdit()
        self.polygonNameBox.setReadOnly(True)
        self.polygonNameBox.setFixedHeight(50)
        self.csvNameBox = QLineEdit()
        self.csvNameBox.setReadOnly(True)
        self.csvNameBox.setFixedHeight(30)

        # create combo box widgets for choosing variables
        self.firstVarBox = QComboBox()
        self.firstVarBox.setFixedSize(400, 30)
        self.secondVarBox = QComboBox()
        self.secondVarBox.setFixedSize(400, 30)

        # create the boxes for volume calculation options
        self.supVolumeBox = QCheckBox('Compute positive and negative volumes (slow)', self)
        self.timeSampling = QLineEdit('1')
        self.timeSampling.setFixedWidth(50)

        # create the submit button
        self.btnSubmit = QPushButton('Submit\n(to .csv)', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)
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
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Input file'), 1, 1)
        glayout.addWidget(self.serafinNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 20))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnOpenPolygon)
        hlayout.addWidget(self.polygonNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the principal variable'), 1, 1)
        glayout.addWidget(self.firstVarBox, 1, 2)
        glayout.addWidget(QLabel('     Select a variable to subtract (optional)'), 2, 1)
        glayout.addWidget(self.secondVarBox, 2, 2)
        glayout.addWidget(QLabel('     More options'), 3, 1)
        glayout.addWidget(self.supVolumeBox, 3, 2)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Time sampling frequency'))
        hlayout.addWidget(self.timeSampling)
        hlayout.setAlignment(self.timeSampling, Qt.AlignLeft)
        hlayout.addStretch()
        glayout.addLayout(hlayout, 4, 2)

        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 20))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

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

    def _reinitInput(self, filename):
        self.filename = filename
        self.serafinNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.csvNameBox.clear()
        self.header = None
        self.time = []
        self.mesh = None
        self.old_options = (self.timeSampling.text(),
                            self.firstVarBox.currentText(),
                            self.secondVarBox.currentText())
        self.timeSampling.setText('1')
        self.firstVarBox.clear()
        self.secondVarBox.clear()
        self.csvNameBox.clear()
        self.btnOpenPolygon.setEnabled(False)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def _resetDefaultOptions(self):
        sampling_frequency, first_var, second_var = self.old_options
        if int(sampling_frequency) <= len(self.time):
            self.timeSampling.setText(sampling_frequency)
        var_ID = first_var.split('(')[0][:-1]
        if var_ID in self.header.var_IDs:
            self.firstVarBox.setCurrentIndex(self.header.var_IDs.index(var_ID))
        if '(' in second_var:
            var_ID = second_var.split('(')[0][:-1]
            if var_ID in self.header.var_IDs:
                self.secondVarBox.setCurrentIndex(2 + self.header.var_IDs.index(var_ID))
        elif second_var[:4] == 'Init':
            self.secondVarBox.setCurrentIndex(1)
        else:
            self.secondVarBox.setCurrentIndex(0)

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)',
                                                  QDir.currentPath(), options=options)
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
            meshLoader = LoadMeshDialog('volume', resin.header)
            self.mesh = meshLoader.run()
            self.parent.outDialog()
            logging.info('Finished processing the mesh')

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        self.btnOpenPolygon.setEnabled(True)
        self.secondVarBox.addItem('0')
        self.secondVarBox.addItem('Initial values of the first variable')

        for var_ID, var_name in zip(self.header.var_IDs, self.header.var_names):
            self.firstVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())
            self.secondVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())

        self._resetDefaultOptions()

        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnOpenPolygonEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)', options=options)
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

        self.polygons = []
        if is_i2s:
            with BlueKenue.Read(filename) as f:
                f.read_header()
                for poly_name, poly in f.get_polygons():
                    self.polygons.append(poly)
        else:
            for polygon in Shapefile.get_polygons(filename):
                self.polygons.append(polygon)
        if not self.polygons:
            QMessageBox.critical(self, 'Error', 'The file does not contain any polygon.',
                                 QMessageBox.Ok)
            return

        logging.info('Finished reading the polygon file %s' % filename)
        self.polygonNameBox.clear()
        self.polygonNameBox.appendPlainText(filename + '\n' + 'The file contains {} polygon{}.'.format(
                                            len(self.polygons), 's' if len(self.polygons) > 1 else ''))
        self.csvNameBox.clear()
        self.btnSubmit.setEnabled(True)
        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnSubmitEvent(self):
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

        # initialize the progress bar
        progressBar = OutputProgressDialog()

        # do the calculations
        self.var_ID = self.firstVarBox.currentText().split('(')[0][:-1]
        self.second_var_ID = self.secondVarBox.currentText()
        if self.second_var_ID == '0':
            self.second_var_ID = None
        elif '(' in self.second_var_ID:
            self.second_var_ID = self.second_var_ID.split('(')[0][:-1]
        else:
            self.second_var_ID = VolumeCalculator.INIT_VALUE

        names = ['Polygon %d' % (i+1) for i in range(len(self.polygons))]

        with Serafin.Read(self.filename, self.language) as resin:
            resin.header = self.header
            resin.time = self.time
            if self.supVolumeBox.isChecked():
                calculator = VolumeCalculatorThread(VolumeCalculator.POSITIVE, self.var_ID, self.second_var_ID,
                                                    resin, names, self.polygons, sampling_frequency, self.mesh)
            else:
                calculator = VolumeCalculatorThread(VolumeCalculator.NET, self.var_ID, self.second_var_ID,
                                                    resin, names, self.polygons, sampling_frequency, self.mesh)

            progressBar.setValue(5)
            QApplication.processEvents()
            progressBar.connectToThread(calculator)

            with open(filename, 'w') as f2:
                calculator.write_csv(f2)

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()
        self.parent.outDialog()

        # unlock the image viewer
        self.parent.imageTab.getData()
        self.parent.tab.setTabEnabled(1, True)


class ComputeVolumeGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        
        self.input = InputTab(self)
        self.imageTab = VolumePlotViewer(self.input)
        self.setWindowTitle('Compute the volume of a variable inside polygons')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.imageTab, 'Visualize results')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; width: 300px; }')

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
    widget = ComputeVolumeGUI()
    widget.show()
    app.exec_()
