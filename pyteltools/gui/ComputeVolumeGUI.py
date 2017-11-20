import datetime
from itertools import cycle
import logging
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys

from pyteltools.slf import Serafin
from pyteltools.slf.volume import VolumeCalculator

from .util import LoadMeshDialog, MapViewer, open_polygons, OutputProgressDialog, OutputThread, PolygonMapCanvas, \
    ProgressBarIterator, PyTelToolWidget, read_csv, save_dialog, SerafinInputTab, VolumePlotViewer


class VolumeCalculatorThread(OutputThread):
    def __init__(self, volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                 time_sampling_frequency, mesh, separator, fmt_float):
        super().__init__()

        self.calculator = VolumeCalculator(volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                                           time_sampling_frequency)
        self.mesh = mesh
        self.separator = separator
        self.fmt_float = fmt_float

    def run_calculator(self):
        self.tick.emit(2)
        QApplication.processEvents()

        logging.info('Starting to process the mesh')
        self.calculator.mesh = self.mesh
        self.tick.emit(10)
        QApplication.processEvents()

        iter_pbar = ProgressBarIterator.prepare(self.tick.emit, (10, 30))
        self.calculator.construct_weights(iter_pbar)
        logging.info('Finished processing the mesh')

        result = []
        iter_pbar = ProgressBarIterator.prepare(self.tick.emit, (30, 100))
        for time_index in iter_pbar(self.calculator.time_indices):
            if self.canceled:
                return []
            i_result = [str(self.calculator.input_stream.time[time_index])]
            values = self.calculator.read_values_in_frame(time_index)

            for j in range(len(self.calculator.polygons)):
                if self.canceled:
                    return []
                weight = self.calculator.weights[j]
                volume = self.calculator.volume_in_frame_in_polygon(weight, values, self.calculator.polygons[j])
                if self.calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append(self.fmt_float.format(v))
                else:
                    i_result.append(self.fmt_float.format(volume))
            result.append(i_result)

        return result

    def write_csv(self, output_stream):
        result = self.run_calculator()
        self.calculator.write_csv(result, output_stream, self.separator)


class ImageTab(VolumePlotViewer):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        # initialize the map for locating polygons
        canvas = PolygonMapCanvas()
        self.map = MapViewer(canvas)

        self.has_map = False
        self.locatePolygons = QAction('Locate polygons\non map', self,
                                      icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                      triggered=self.locatePolygonsEvent)
        self.locatePolygons_short = QAction('Locate polygons on map', self,
                                            icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                            triggered=self.locatePolygonsEvent)
        self.map.closeEvent = self.enable_locate
        self.toolBar.addAction(self.locatePolygons)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locatePolygons_short)
        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.poly_menu)

    def enable_locate(self, event):
        self.locatePolygons.setEnabled(True)
        self.locatePolygons_short.setEnabled(True)

    def getData(self):
        # get the new data
        csv_file = self.input.csvNameBox.text()
        self.data, headers = read_csv(csv_file, self.input.parent.csv_separator)

        self.var_ID = self.input.var_ID
        self.second_var_ID = self.input.second_var_ID
        if self.input.data.header.date is not None:
            year, month, day, hour, minute, second = self.input.data.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = headers[1:]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {column: color for column, color in zip(self.columns, cycle(self.defaultColors))}

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = self.input.data.language
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = ''
        self.replot()

    def locatePolygonsEvent(self):
        if not self.has_map:
            self.map.canvas.reinitFigure(self.input.mesh, self.input.polygons,
                                         map(self.column_labels.get, ['Polygon %d' % (i+1)
                                                                      for i in range(len(self.input.polygons))]))
            self.has_map = True
        self.locatePolygons.setEnabled(False)
        self.locatePolygons_short.setEnabled(False)
        self.map.show()

    def reset(self):
        self.has_map = False
        self.map.close()

        super().reset()
        self.current_columns = ('Polygon 1',)


class InputTab(SerafinInputTab):
    def __init__(self, parent):
        super().__init__(parent)
        self.old_options = ('1', '', '0')
        self.data = None
        self.mesh = None
        self.polygons = []
        self.var_ID = None
        self.second_var_ID = None

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create the button open Polygon
        self.btnOpenPolygon = QPushButton('Load\nPolygons', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenPolygon.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolygon.setFixedSize(105, 50)
        self.btnOpenPolygon.setEnabled(False)

        # create some text fields displaying the IO files info
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

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.timeSampling.editingFinished.connect(self._checkSamplingFrequency)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        mainLayout.addLayout(self.input_layout)
        mainLayout.addItem(QSpacerItem(10, 20))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnOpenPolygon)
        hlayout.addWidget(self.polygonNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addStretch()

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
        mainLayout.addStretch()

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
        if sampling_frequency < 1 or sampling_frequency > len(self.data.time):
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be in the range [1; nbFrames]!',
                                 QMessageBox.Ok)
            self.timeSampling.setText('1')
            return

    def _reinitInput(self):
        self.reset()
        self.csvNameBox.clear()
        self.old_options = (self.timeSampling.text(),
                            self.firstVarBox.currentText(),
                            self.secondVarBox.currentText())
        self.timeSampling.setText('1')
        self.firstVarBox.clear()
        self.secondVarBox.clear()
        self.csvNameBox.clear()
        self.btnOpenPolygon.setEnabled(False)

    def _resetDefaultOptions(self):
        sampling_frequency, first_var, second_var = self.old_options
        if int(sampling_frequency) <= len(self.data.time):
            self.timeSampling.setText(sampling_frequency)
        var_ID = first_var.split('(')[0][:-1]
        if var_ID in self.data.header.var_IDs:
            self.firstVarBox.setCurrentIndex(self.data.header.var_IDs.index(var_ID))
        if '(' in second_var:
            var_ID = second_var.split('(')[0][:-1]
            if var_ID in self.data.header.var_IDs:
                self.secondVarBox.setCurrentIndex(2 + self.data.header.var_IDs.index(var_ID))
        elif second_var[:4] == 'Init':
            self.secondVarBox.setCurrentIndex(1)
        else:
            self.secondVarBox.setCurrentIndex(0)

    def btnOpenSerafinEvent(self):
        canceled, filename = super().open_event()
        if canceled:
            return

        self._reinitInput()

        success, data = self.read_2d(filename)
        if not success:
            return

        # record the mesh for future visualization and calculations
        self.parent.inDialog()
        meshLoader = LoadMeshDialog('volume', data.header)
        self.mesh = meshLoader.run()
        self.parent.outDialog()
        if meshLoader.thread.canceled:
            self.polygonNameBox.clear()
            self.summaryTextBox.clear()
            return

        self.data = data
        self.btnOpenPolygon.setEnabled(True)
        self.secondVarBox.addItem('0')
        self.secondVarBox.addItem('Initial values of the first variable')

        for var_ID, var_name in zip(self.data.header.var_IDs, self.data.header.var_names):
            self.firstVarBox.addItem(var_ID + ' (%s)' % var_name.decode(Serafin.SLF_EIT).strip())
            self.secondVarBox.addItem(var_ID + ' (%s)' % var_name.decode(Serafin.SLF_EIT).strip())

        self._resetDefaultOptions()

        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnOpenPolygonEvent(self):
        success, filename, polygons = open_polygons()
        if not success:
            return
        self.polygons = polygons
        logging.info('Finished reading the polygon file %s' % filename)
        self.polygonNameBox.clear()
        self.polygonNameBox.appendPlainText(filename + '\n' + 'The file contains {} polygon{}.'.format(
                                            len(self.polygons), 's' if len(self.polygons) > 1 else ''))
        self.csvNameBox.clear()
        self.btnSubmit.setEnabled(True)
        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnSubmitEvent(self):
        canceled, filename = save_dialog('CSV')
        if canceled:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()

        # initialize the progress bar
        progressBar = OutputProgressDialog()

        # do the calculations
        sampling_frequency = int(self.timeSampling.text())
        self.var_ID = self.firstVarBox.currentText().split('(')[0][:-1]
        self.second_var_ID = self.secondVarBox.currentText()
        if self.second_var_ID == '0':
            self.second_var_ID = None
        elif '(' in self.second_var_ID:
            self.second_var_ID = self.second_var_ID.split('(')[0][:-1]
        else:
            self.second_var_ID = VolumeCalculator.INIT_VALUE

        names = ['Polygon %d' % (i+1) for i in range(len(self.polygons))]

        try:
            with Serafin.Read(self.data.filename, self.data.language) as input_stream:
                input_stream.header = self.data.header
                input_stream.time = self.data.time
                if self.supVolumeBox.isChecked():
                    volume_type = VolumeCalculator.POSITIVE
                else:
                    volume_type = VolumeCalculator.NET
                calculator = VolumeCalculatorThread(volume_type, self.var_ID, self.second_var_ID, input_stream,
                                                    names, self.polygons, sampling_frequency, self.mesh,
                                                    self.parent.csv_separator, self.parent.fmt_float)

                progressBar.setValue(5)
                QApplication.processEvents()

                with open(filename, 'w') as f2:
                    progressBar.connectToThread(calculator)
                    calculator.write_csv(f2)
        except (Serafin.SerafinRequestError, Serafin.SerafinValidationError) as e:
            QMessageBox.critical(None, 'Serafin Error', e.message, QMessageBox.Ok, QMessageBox.Ok)
            return

        if not calculator.canceled:
            progressBar.outputFinished()
        progressBar.exec_()
        self.parent.outDialog()

        if calculator.canceled:
            self.csvNameBox.clear()
            return

        # unlock the image viewer
        self.parent.imageTab.getData()
        self.parent.tab.setTabEnabled(1, True)


class ComputeVolumeGUI(PyTelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = InputTab(self)
        self.imageTab = ImageTab(self.input)
        self.setWindowTitle('Compute the volume of a variable inside polygons')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.imageTab, 'Visualize results')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 250px; }')

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
    widget = ComputeVolumeGUI()
    widget.show()
    app.exec_()
