from itertools import islice, cycle
import logging
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys

from conf.settings import LOGGING_LEVEL
from gui.util import MapViewer, LineMapCanvas, QPlainTextEditLogger, SerafinInputTab, TelToolWidget, OutputThread, \
    VariableTable, OutputProgressDialog, LoadMeshDialog, open_polylines,\
    MultiVarLinePlotViewer, MultiFrameLinePlotViewer, save_dialog
from slf import Serafin
from slf.interpolation import MeshInterpolator


class WriteCSVProcess(OutputThread):
    def __init__(self, separator, mesh):
        super().__init__()
        self.separator = separator
        self.mesh = mesh

    def write_header(self, output_stream, selected_vars):
        output_stream.write('Line')
        for header in ['time', 'x', 'y', 'distance'] + selected_vars:
            output_stream.write(self.separator)
            output_stream.write(header)
        output_stream.write('\n')

    def write_csv(self, input_stream, selected_vars, output_stream, line_interpolators, indices_nonempty):
        self.write_header(output_stream, selected_vars)

        nb_frames = len(input_stream.time)
        inv_steps = 1 / len(indices_nonempty) / nb_frames

        for u, v, row in MeshInterpolator.interpolate_along_lines(input_stream, selected_vars, (len(input_stream.time)),
                                                                  indices_nonempty, line_interpolators):
            output_stream.write(self.separator.join(row))
            output_stream.write('\n')
            self.tick.emit(100 * (v+1+u*nb_frames) * inv_steps)
            QApplication.processEvents()


class InputTab(SerafinInputTab):
    def __init__(self, parent):
        super().__init__(parent)

        canvas = LineMapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

        self.data = None
        self.mesh = None

        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []  # without intersection points

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create the button open lines
        self.btnOpenLines = QPushButton('Load\nLines', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenLines.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenLines.setFixedSize(105, 50)
        self.btnOpenLines.setEnabled(False)

        # create some text fields displaying the IO files info
        self.linesNameBox = QPlainTextEdit()
        self.linesNameBox.setReadOnly(True)
        self.linesNameBox.setFixedHeight(50)

        # create the map button
        self.btnMap = QPushButton('Locate lines\non map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.btnMap.setFixedSize(135, 50)
        self.btnMap.setEnabled(False)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenLines.clicked.connect(self.btnOpenLinesEvent)
        self.btnMap.clicked.connect(self.btnMapEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnOpenLines)
        hlayout.addWidget(self.btnMap)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Input file'), 1, 1)
        glayout.addWidget(self.inNameBox, 1, 2)
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

    def _reinitInput(self):
        self.reset()
        self.data = None
        self.btnMap.setEnabled(False)
        self.mesh = None
        self.btnOpenLines.setEnabled(False)

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
        canceled, filename = super().open_event()
        if canceled:
            return

        self._reinitInput()
        success, data = self.read_2d(filename)
        if not success:
            return

        # record the mesh for future visualization and calculations
        self.parent.inDialog()
        meshLoader = LoadMeshDialog('interpolation', data.header)
        self.mesh = meshLoader.run()
        self.parent.outDialog()
        if meshLoader.thread.canceled:
            self.linesNameBox.clear()
            self.summaryTextBox.clear()
            return

        self.data = data
        self.btnOpenLines.setEnabled(True)
        self._resetDefaultOptions()

    def btnOpenLinesEvent(self):
        success, filename, polylines = open_polylines()
        if not success:
            return
        self.lines = polylines
        logging.info('Finished reading the lines file %s' % filename)

        nb_nonempty, indices_nonempty, \
            self.line_interpolators, self.line_interpolators_internal = self.mesh.get_line_interpolators(self.lines)
        if nb_nonempty == 0:
            QMessageBox.critical(self, 'Error', 'No line intersects the mesh continuously.',
                                 QMessageBox.Ok)
            return

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
        self.firstTable = VariableTable()
        self.secondTable = VariableTable()

        # create the options
        self.intersect = QCheckBox('Add intersection points')
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
        logging.getLogger().setLevel(LOGGING_LEVEL)

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
        return self.secondTable.get_selected()

    def _initVarTables(self):
        self.firstTable.fill(self.input.data.header)

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

        canceled, filename = save_dialog('.csv')
        if canceled:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()

        indices_nonempty = [i for i in range(len(self.input.lines)) if self.input.line_interpolators[i][0]]

        # initialize the progress bar
        process = WriteCSVProcess(self.parent.csv_separator, self.input.mesh)
        progressBar = OutputProgressDialog()

        with Serafin.Read(self.input.data.filename, self.input.data.language) as input_stream:
            input_stream.header = self.input.data.header
            input_stream.time = self.input.data.time

            progressBar.setValue(1)
            QApplication.processEvents()

            with open(filename, 'w') as output_stream:
                progressBar.connectToThread(process)

                if self.intersect.isChecked():
                    process.write_csv(input_stream, selected_var_IDs, output_stream,
                                      self.input.line_interpolators, indices_nonempty)
                else:
                    process.write_csv(input_stream, selected_var_IDs, output_stream,
                                      self.input.line_interpolators_internal, indices_nonempty)

        if not process.canceled:
            progressBar.outputFinished()
        progressBar.exec_()
        self.parent.outDialog()

        if process.canceled:
            self.csvNameBox.clear()
            return


class LinesGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = InputTab(self)
        self.csvTab = CSVTab(self.input, self)
        self.multiVarTab = MultiVarLinePlotViewer()
        self.multiFrameTab = MultiFrameLinePlotViewer()

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
        self.csvTab.getInput()
        for tab in (self.multiVarTab, self.multiFrameTab):
            tab.getInput(self.input.data, self.input.lines,
                         self.input.line_interpolators, self.input.line_interpolators_internal)
        for i in range(1, 4):
            self.tab.setTabEnabled(i, True)


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