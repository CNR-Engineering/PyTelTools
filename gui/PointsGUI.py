import datetime
from itertools import cycle
import logging
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys

from gui.util import PointPlotViewer, MapViewer, MapCanvas, OutputThread,\
    VariableTable, OutputProgressDialog, LoadMeshDialog, SerafinInputTab, TelToolWidget, \
    PointAttributeTable, PointLabelEditor, open_points, save_dialog, read_csv
from slf import Serafin


class WriteCSVProcess(OutputThread):
    def __init__(self, separator, digits, mesh):
        super().__init__()
        self.mesh = mesh
        self.format_string = '{0:.%df}' % digits
        self.separator = separator

    def write_header(self, output_stream, selected_vars, indices, points):
        output_stream.write('time')
        for index, (x, y) in zip(indices, points):
            for var in selected_vars:
                output_stream.write(self.separator)
                output_stream.write('Point %d %s (%.4f|%.4f)' % (index+1, var, x, y))
        output_stream.write('\n')

    def write_csv(self, input_stream, output_time, selected_vars, output_stream, indices,
                  points, point_interpolators):
        self.write_header(output_stream, selected_vars, indices, points)

        nb_selected_vars = len(selected_vars)
        nb_frames = len(output_time)

        for index, time in enumerate(output_time):
            if self.canceled:
                return
            output_stream.write(str(time))

            var_values = []
            for var in selected_vars:
                var_values.append(input_stream.read_var_in_frame(index, var))

            for (i, j, k), interpolator in point_interpolators:
                if self.canceled:
                    return
                for index_var in range(nb_selected_vars):
                    output_stream.write(self.separator)
                    output_stream.write(self.format_string.format(interpolator.dot(var_values[index_var][[i, j, k]])))

            output_stream.write('\n')
            self.tick.emit(int(100 * (index+1) / nb_frames))
            QApplication.processEvents()


class InputTab(SerafinInputTab):
    def __init__(self, parent):
        super().__init__(parent)
        self.old_frequency = '1'

        canvas = MapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

        self.data = None
        self.mesh = None

        self.points = []
        self.point_interpolators = []
        self.fields = []
        self.attributes = []
        self.attribute_table = PointAttributeTable()

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
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
        self.pointsNameBox = QPlainTextEdit()
        self.pointsNameBox.setReadOnly(True)
        self.pointsNameBox.setFixedHeight(50)

        # create two 3-column tables for variables selection
        self.firstTable = VariableTable()
        self.secondTable = VariableTable()

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

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenSerafinEvent)
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
        hlayout.addWidget(self.btnOpen)
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
        glayout.addWidget(self.inNameBox, 1, 2)
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

    def _reinitInput(self):
        self.reset()
        self.data = None
        self.has_map = False
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.btnMap.setEnabled(False)
        self.btnOpenAttributes.setEnabled(False)
        self.mesh = None
        self.btnOpenPoints.setEnabled(False)
        self.old_frequency = self.timeSampling.text()

        self.timeSampling.setText('1')
        self.btnSubmit.setEnabled(False)
        self.csvNameBox.clear()
        self.parent.tab.setTabEnabled(1, False)

    def _resetDefaultOptions(self):
        if int(self.old_frequency) <= len(self.data.time):
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
        self.firstTable.fill(self.data.header)

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

    def getSelectedVariables(self):
        return self.secondTable.get_selected()

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
            self.pointsNameBox.clear()
            self.summaryTextBox.clear()
            return

        self.data = data
        self.btnOpenPoints.setEnabled(True)
        self._resetDefaultOptions()
        self.parent.imageTab.reset()

        # displaying the available variables
        self._initVarTables()

    def btnOpenPointsEvent(self):
        success, filename, points, attributes, fields = open_points()
        if not success:
            return

        logging.info('Finished reading the points file %s' % filename)
        is_inside, point_interpolators = self.mesh.get_point_interpolators(points)
        nb_inside = sum(map(int, is_inside))
        if nb_inside == 0:
            QMessageBox.critical(self, 'Error', 'No point inside the mesh.', QMessageBox.Ok)
            return

        self.points = points
        self.attributes = attributes
        self.fields = fields
        self.attribute_table.getData(self.points, is_inside, self.fields, self.attributes)
        self.point_interpolators = point_interpolators
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

        canceled, filename = save_dialog('CSV')
        if canceled:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)
        self.parent.inDialog()


        sampling_frequency = int(self.timeSampling.text())
        selected_time = self.data.time[::sampling_frequency]
        indices_inside = [i for i in range(len(self.points)) if self.point_interpolators[i] is not None]

        # initialize the progress bar
        process = WriteCSVProcess(self.parent.csv_separator, self.parent.digits, self.mesh)
        progressBar = OutputProgressDialog()

        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time

            progressBar.setValue(1)
            QApplication.processEvents()

            with open(filename, 'w') as output_stream:
                progressBar.connectToThread(process)
                process.write_csv(input_stream, selected_time, selected_var_IDs, output_stream,
                                  indices_inside,
                                  [self.points[i] for i in indices_inside],
                                  [self.point_interpolators[i] for i in indices_inside])
        if not process.canceled:
            progressBar.outputFinished()
        progressBar.exec_()
        self.parent.outDialog()

        if process.canceled:
            self.csvNameBox.clear()
            return

        self.parent.imageTab.getData(selected_var_IDs, indices_inside)
        self.parent.tab.setTabEnabled(1, True)


class ImageTab(PointPlotViewer):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        self.has_map = False
        canvas = MapCanvas()
        self.map = MapViewer(canvas)

        self.var_IDs = []
        self.current_var = ''
        self.openAttributes = QAction('Attributes\nTable', self,
                                      icon=self.style().standardIcon(QStyle.SP_FileDialogListView),
                                      triggered=self.openAttributesEvent)
        self.openAttributes_short = QAction('Attributes Table', self,
                                            icon=self.style().standardIcon(QStyle.SP_FileDialogListView),
                                            triggered=self.openAttributesEvent)
        self.locatePoints = QAction('Locate points\non map', self,
                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                    triggered=self.map_event)
        self.locatePoints_short = QAction('Locate points on map', self,
                                          icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                          triggered=self.map_event)
        self.input.map.closeEvent = self.enable_locate
        self.input.attribute_table.closeEvent = self.enable_attribute

        self.toolBar.addAction(self.locatePoints)
        self.toolBar.addAction(self.openAttributes)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.select_variable)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locatePoints)
        self.pointsMenu = QMenu('&Data', self)
        self.pointsMenu.addAction(self.openAttributes_short)
        self.pointsMenu.addSeparator()
        self.pointsMenu.addAction(self.select_variable_short)
        self.pointsMenu.addAction(self.selectColumnsAct_short)
        self.pointsMenu.addAction(self.editColumnNamesAct_short)
        self.pointsMenu.addAction(self.editColumColorAct_short)

        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.pointsMenu)

    def enable_attribute(self, event):
        self.openAttributes.setEnabled(True)
        self.openAttributes_short.setEnabled(True)

    def enable_locate(self, event):
        self.locatePoints.setEnabled(True)
        self.locatePoints_short.setEnabled(True)

    def map_event(self):
        self.locatePoints.setEnabled(False)
        self.locatePoints_short.setEnabled(False)
        self.input.btnMapEvent()

    def _to_column(self, point):
        point_index = int(point.split()[1]) - 1
        x, y = self.input.points[point_index]
        return 'Point %d %s (%.4f|%.4f)' % (point_index+1, self.current_var, x, y)

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

    def getData(self, var_IDs, point_indices):
        self.var_IDs = var_IDs
        self.current_var = var_IDs[0]

        # get the new data
        csv_file = self.input.csvNameBox.text()
        self.data, headers = read_csv(csv_file, self.input.parent.csv_separator)

        if self.input.data.header.date is not None:
            year, month, day, hour, minute, second = self.input.data.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = ['Point %d' % (i+1) for i in point_indices]
        self.current_columns = self.columns[0:1]
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

    def openAttributesEvent(self):
        self.openAttributes.setEnabled(False)
        self.openAttributes_short.setEnabled(False)
        self.input.attribute_table.show()

    def replot(self):
        self.canvas.axes.clear()
        for point in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[self._to_column(point)], '-',
                                  color=self.column_colors[point], linewidth=2, label=self.column_labels[point])
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