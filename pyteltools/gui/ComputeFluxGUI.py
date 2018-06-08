import datetime
from itertools import cycle
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAction, QApplication, QComboBox, QGridLayout,  QHBoxLayout,
                             QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                             QSpacerItem, QStyle, QTabWidget, QVBoxLayout)
import sys

from pyteltools.slf.flux import FluxCalculator, PossibleFluxComputation
from pyteltools.slf import Serafin

from .util import FluxPlotViewer, LineMapCanvas, LoadMeshDialog, MapViewer, open_polylines, OutputProgressDialog, \
    OutputThread, ProgressBarIterator, PyTelToolWidget, read_csv, save_dialog, SerafinInputTab


class FluxCalculatorThread(OutputThread):
    def __init__(self, flux_type, var_IDs, input_stream, section_names, sections,
                 time_sampling_frequency, mesh, separator, fmt_float):
        super().__init__()

        self.calculator = FluxCalculator(flux_type, var_IDs, input_stream,
                                         section_names, sections, time_sampling_frequency)
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

        self.calculator.construct_intersections()
        self.tick.emit(20)
        QApplication.processEvents()
        logging.info('Finished processing the mesh')

        return self.calculator.run(iter_pbar=ProgressBarIterator.prepare(self.tick.emit, (20, 100)))

    def write_csv(self, output_stream):
        result = self.run_calculator()
        self.calculator.write_csv(result, output_stream, self.separator)


class InputTab(SerafinInputTab):
    def __init__(self, parent):
        super().__init__(parent)
        self.old_options = ('1', '')

        self.data = None
        self.mesh = None
        self.polylines = []
        self.var_IDs = []

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setMinimumWidth(800)

    def _initWidgets(self):
        # create the button open Polygon
        self.btnOpenPolyline = QPushButton('Load\nSections', self,
                                           icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenPolyline.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolyline.setFixedSize(105, 50)
        self.btnOpenPolyline.setEnabled(False)

        # create some text fields displaying the IO files info
        self.polygonNameBox = QPlainTextEdit()
        self.polygonNameBox.setReadOnly(True)
        self.polygonNameBox.setFixedHeight(50)
        self.csvNameBox = QLineEdit()
        self.csvNameBox.setReadOnly(True)
        self.csvNameBox.setFixedHeight(30)

        # create some widgets for flux options
        self.fluxBox = QComboBox()
        self.fluxBox.setFixedSize(400, 30)
        self.timeSampling = QLineEdit('1')
        self.timeSampling.setFixedWidth(50)

        # create the submit button
        self.btnSubmit = QPushButton('Submit\n(to .csv)', self,
                                     icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolyline.clicked.connect(self.btnOpenPolylineEvent)
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
        hlayout.addWidget(self.btnOpenPolyline)
        hlayout.addWidget(self.polygonNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addStretch()

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the flux to compute'), 1, 1)
        glayout.addWidget(self.fluxBox, 1, 2)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Time sampling frequency'))
        hlayout.addWidget(self.timeSampling)
        hlayout.setAlignment(self.timeSampling, Qt.AlignLeft)
        hlayout.addStretch()
        glayout.addLayout(hlayout, 2, 2)

        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)

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

    def _reinitInput(self):
        self.reset()
        self.data = None
        self.csvNameBox.clear()
        self.mesh = None
        self.csvNameBox.clear()
        self.old_options = (self.timeSampling.text(),
                            self.fluxBox.currentText())
        self.btnOpenPolyline.setEnabled(False)
        self.timeSampling.setText('1')
        self.fluxBox.clear()
        self.btnSubmit.setEnabled(False)

    def _resetDefaultOptions(self):
        sampling_frequency, flux_type = self.old_options
        if int(sampling_frequency) <= len(self.data.time):
            self.timeSampling.setText(sampling_frequency)
        for i in range(self.fluxBox.count()):
            text = self.fluxBox.itemText(i)
            if text == flux_type:
                self.fluxBox.setCurrentIndex(i)
                self.btnSubmit.setEnabled(True)
                break

    def _addFluxOptions(self, header):
        for possible_flux in PossibleFluxComputation(header.var_IDs, header.var_names):
            self.fluxBox.addItem(possible_flux)
        return self.fluxBox.count() > 0

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

    def _getFluxSection(self):
        selection = self.fluxBox.currentText()
        var_IDs = PossibleFluxComputation.get_variables(selection)
        flux_type = PossibleFluxComputation.get_flux_type(var_IDs)
        return flux_type, var_IDs, selection

    def btnOpenSerafinEvent(self):
        canceled, filename = super().open_event()
        if canceled:
            return

        self._reinitInput()
        success, data = self.read_2d(filename)
        if not success:
            return

        flux_added = self._addFluxOptions(data.header)
        if not flux_added:
            QMessageBox.critical(self, 'Error', 'No flux is computable from this file.', QMessageBox.Ok)
            self.summaryTextBox.clear()
            return

        # record the mesh for future visualization and calculations
        self.parent.inDialog()
        meshLoader = LoadMeshDialog('flux', data.header)
        self.mesh = meshLoader.run()
        self.parent.outDialog()
        if meshLoader.thread.canceled:
            self.fluxBox.clear()
            self.polygonNameBox.clear()
            self.summaryTextBox.clear()
            return

        self.data = data
        self._resetDefaultOptions()
        self.btnOpenPolyline.setEnabled(True)
        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnOpenPolylineEvent(self):
        success, filename, polylines = open_polylines()
        if not success:
            return
        self.polylines = polylines
        logging.info('Finished reading the polyline file %s' % filename)
        self.polygonNameBox.clear()
        self.polygonNameBox.appendPlainText(filename + '\n' + 'The file contains {} open polyline{}.'.format(
            len(self.polylines), 's' if len(self.polylines) > 1 else ''))
        self.csvNameBox.clear()
        self.btnSubmit.setEnabled(True)
        self.parent.imageTab.reset()
        self.parent.tab.setTabEnabled(1, False)

    def btnSubmitEvent(self):
        canceled, filename = save_dialog('CSV')
        if canceled:
            return
        self.csvNameBox.setText(filename)

        sampling_frequency = int(self.timeSampling.text())
        flux_type, self.var_IDs, flux_title = self._getFluxSection()
        self.parent.tab.setTabEnabled(1, False)

        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()

        # initialize the progress bar
        progressBar = OutputProgressDialog()

        # do the calculations
        names = [poly.id for poly in self.polylines]

        try:
            with Serafin.Read(self.data.filename, self.data.language) as input_stream:
                input_stream.header = self.data.header
                input_stream.time = self.data.time
                calculator = FluxCalculatorThread(flux_type, self.var_IDs,
                                                  input_stream, names, self.polylines, sampling_frequency,
                                                  self.mesh, self.parent.csv_separator, self.parent.fmt_float)
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
        self.parent.imageTab.getData(flux_title)
        self.parent.tab.setTabEnabled(1, True)


class ImageTab(FluxPlotViewer):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        # initialize the map for locating sections
        canvas = LineMapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False
        self.locateSections = QAction('Locate sections\non map', self,
                                      icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                      triggered=self.locateSectionsEvent)
        self.locateSections_short = QAction('Locate sections\non map', self,
                                            icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                            triggered=self.locateSectionsEvent)
        self.map.closeEvent = self.enable_locate
        self.cumulativeFluxAct = QAction('Show\ncumulative flux', self, checkable=True,
                                         icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.cumulativeFluxAct.toggled.connect(self.changeFluxType)

        self.toolBar.addAction(self.locateSections)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.cumulativeFluxAct)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locateSections_short)
        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.poly_menu)

    def enable_locate(self, event):
        self.locateSections.setEnabled(True)
        self.locateSections_short.setEnabled(True)

    def getData(self, flux_title):
        self.flux_title = flux_title

        # get the new data
        csv_file = self.input.csvNameBox.text()
        self.data, headers = read_csv(csv_file, self.input.parent.csv_separator)

        self.var_IDs = self.input.var_IDs
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
        self.current_ylabel = self.flux_title
        self.current_title = ''
        self.replot()

    def locateSectionsEvent(self):
        if not self.has_map:
            self.map.canvas.reinitFigure(self.input.mesh, self.input.polylines,
                                         map(self.column_labels.get, [poly.id for poly in self.input.polylines]),
                                         map(self.column_colors.get, [self.column_labels[poly.id]
                                                                      for poly in self.input.polylines]))

            self.has_map = True
        self.locateSections.setEnabled(False)
        self.locateSections_short.setEnabled(False)
        self.map.show()

    def reset(self):
        self.has_map = False
        self.map.close()

        # reinitialize old graphical parameters
        super().reset()
        self.current_columns = tuple()  # Has to be initialized manually


class ComputeFluxGUI(PyTelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Compute the flux of a vector field across sections')

        self.input = InputTab(self)
        self.imageTab = ImageTab(self.input)

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.imageTab, 'Visualize results')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

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
    widget = ComputeFluxGUI()
    widget.show()
    app.exec_()
