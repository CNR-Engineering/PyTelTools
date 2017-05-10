import sys
import os
import logging
import copy
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from matplotlib.collections import PatchCollection
from descartes import PolygonPatch

from slf import Serafin
from slf.volume import TruncatedTriangularPrisms, VolumeCalculator
from geom import BlueKenue, Shapefile
from gui.util import PlotViewer, QPlainTextEditLogger, TableWidgetDragRows



class VolumeCalculatorGUI(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                 time_sampling_frequency, triangles):
        super().__init__()

        self.calculator = VolumeCalculator(volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                                           time_sampling_frequency)
        self.base_triangles = triangles

    def run_calculator(self):
        self.tick.emit(6)
        QApplication.processEvents()

        self.calculator.base_triangles = self.base_triangles
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
                    second_values = self.calculator.input_stream.read_var_in_frame(time_index, self.calculator.second_var_ID)
                    values -= second_values

            for j in range(len(self.calculator.polygons)):
                weight = self.calculator.weights[j]
                volume = self.calculator.volume_in_frame_in_polygon(weight, values, self.calculator.polygons[j])
                if self.calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append(str(v))
                else:
                    i_result.append(str(volume))
            result.append(i_result)

            self.tick.emit(30 + int(70 * (i+1) / len(self.calculator.time_indices)))
        return result

    def write_csv(self, output_stream):
        result = self.run_calculator()
        self.calculator.write_csv(result, output_stream)


class OutputProgressDialog(QProgressDialog):
    def __init__(self, parent=None):
        super().__init__('Output in progress', 'OK', 0, 100, parent)

        self.cancelButton = QPushButton('OK')
        self.setCancelButton(self.cancelButton)
        self.cancelButton.setEnabled(False)

        self.setAutoReset(False)
        self.setAutoClose(False)

        self.setWindowTitle('Writing the output...')
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setFixedSize(300, 150)

        self.open()
        self.setValue(0)
        QApplication.processEvents()

    def connectToCalculator(self, thread):
        thread.tick.connect(self.setValue)


class PlotColumnsSelector(QDialog):
    def __init__(self, columns, current_columns):
        super().__init__()

        self.list = QListWidget()
        for name in columns:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if name in current_columns:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)

        self.selection = tuple([])

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkSelection)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('  Select up to 8 columns to plot'))
        vlayout.addWidget(self.list)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.resize(self.sizeHint())
        self.setWindowTitle('Select columns to plot')

    def getSelection(self):
        selection = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() == Qt.Checked:
                selection.append(item.text())
        return tuple(selection)

    def checkSelection(self):
        self.selection = self.getSelection()
        if not self.selection:
            QMessageBox.critical(self, 'Error', 'Select at least one column to plot.',
                                 QMessageBox.Ok)
            return
        if len(self.selection) > 8:
            QMessageBox.critical(self, 'Error', 'Select up to 8 columns.',
                                 QMessageBox.Ok)
            return
        self.accept()


class ColumnNameEditor(QDialog):
    def __init__(self, column_labels, selected_columns):
        super().__init__()

        self.table = QTableWidget()
        self.table .setColumnCount(2)
        self.table .setHorizontalHeaderLabels(['Column', 'Label'])
        row = 0
        for column in selected_columns:
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
        vlayout.addWidget(QLabel('Click on the name to modify'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.resize(self.sizeHint())
        self.setWindowTitle('Change column labels')

    def getLabels(self, old_labels):
        for row in range(self.table.rowCount()):
            column = self.table.item(row, 0).text()
            label = self.table.item(row, 1).text()
            old_labels[column] = label


class ColorTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['Column', 'Color'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.last_drop_row = None

    def dropMimeData(self, row, col, mimeData, action):
        self.last_drop_row = row
        return True

    def getselectedRow(self):
        for item in self.selectedItems():
            return item.row()

    def dropEvent(self, event):
        sender = event.source()
        super().dropEvent(event)
        dropRow = self.last_drop_row
        if dropRow > self.rowCount()-1:
            return

        if self != sender:
            color = QTableWidgetItem(self.item(dropRow, 1))
            selectedRows = sender.getselectedRowsFast()
            selectedRow = selectedRows[0]

            item = sender.item(selectedRow, 0)
            source = QTableWidgetItem(item)
            self.setItem(dropRow, 1, source)
            # sender.insertRow(sender.rowCount())
            # sender.setItem(sender.rowCount()-1, 0, color)
            # sender.removeRow(selectedRow)
        else:
            selectedRow = self.getselectedRow()
            source = self.item(selectedRow, 1).text()
            self.item(selectedRow, 1).setText(self.item(dropRow, 1).text())
            self.item(dropRow, 1).setText(source)
        event.accept()


class ColumnColorEditor(QDialog):
    def __init__(self, parent):
        super().__init__()

        self.table = ColorTable()
        self.table.setFixedHeight(300)
        used_colors = []
        row = 0
        for column in parent.current_columns:
            label = parent.column_labels[column]
            color = parent.colorToName[parent.column_colors[column]]
            used_colors.append(color)
            self.table.insertRow(row)
            lab = QTableWidgetItem(label)
            col = QTableWidgetItem(color)
            self.table.setItem(row, 0, lab)
            self.table.setItem(row, 1, col)
            row += 1
        self.available_colors = TableWidgetDragRows()
        self.available_colors.setSelectionMode(QAbstractItemView.SingleSelection)
        self.available_colors.setColumnCount(1)
        self.available_colors.setHorizontalHeaderLabels(['Available colors'])
        self.available_colors.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_colors.setAcceptDrops(False)
        self.available_colors.setFixedSize(150, 300)
        row = 0
        for color in parent.defaultColors:
            color_name = parent.colorToName[color]
            self.available_colors.insertRow(row)
            col = QTableWidgetItem(color_name)
            self.available_colors.setItem(row, 0, col)
            row += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Drag and drop colors on the polygons'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.available_colors)
        hlayout.addWidget(self.table)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(500, 400)
        self.setWindowTitle('Change column color')

    def getColors(self, old_colors, column_labels, name_to_color):
        label_to_column = {b: a for a, b, in column_labels.items()}
        for row in range(self.table.rowCount()):
            label = self.table.item(row, 0).text()
            color = self.table.item(row, 1).text()
            old_colors[label_to_column[label]] = name_to_color[color]


class MapCanvas(FigureCanvas):
    def __init__(self, parent):
        self.parent = parent
        self.BLUE = '#6699cc'
        self.PINK = '#fcabbd'
        self.BLACK = '#14123a'

        fig = Figure(figsize=(10, 10), dpi=60)
        self.axes = fig.add_subplot(111)

        FigureCanvas.__init__(self, fig)
        self.setParent(None)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.hasFigure = False

    def initFigure(self):
        patches = [PolygonPatch(t.buffer(0), fc=self.BLUE, ec=self.BLUE, alpha=0.5, zorder=1)
                   for t in self.parent.triangles]
        for p in self.parent.parent.polygons:
            patches.append(PolygonPatch(p.polyline().buffer(0), fc=self.PINK, ec=self.BLACK, alpha=0.5, zorder=1))

        self.axes.add_collection(PatchCollection(patches, match_original=True))
        for p, name in zip(self.parent.parent.polygons,
                           [self.parent.column_labels[p] for p in ['Polygon %d' % (i+1)
                                                         for i in range(len(self.parent.parent.polygons))]]):
            center = p.polyline().centroid
            cx, cy = center.x, center.y
            self.axes.annotate(name, (cx, cy), color='k', weight='bold',
                               fontsize=8, ha='center', va='center')

        minx, maxx, miny, maxy = self.parent.parent.locations
        w, h = maxx - minx, maxy - miny
        self.axes.set_xlim(minx - 0.05 * w, maxx + 0.05 * w)
        self.axes.set_ylim(miny - 0.05 * h, maxy + 0.05 * h)
        self.axes.set_aspect('equal', adjustable='box')

        self.hasFigure = True

    def closeEvent(self, event):
        self.parent.locatePolygonAct.setEnabled(True)
        self.hide()


class VolumePlotViewer(PlotViewer):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.map = MapCanvas(self)

        self.defaultColors = ['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']
        name = ['Blue', 'Red', 'Green', 'Yellow', 'Black', 'Cyan', 'Pink', 'Magenta']
        self.colorToName = {c: n for c, n in zip(self.defaultColors, name)}
        self.nameToColor = {n: c for c, n in zip(self.defaultColors, name)}

        self.setWindowTitle('Visualize the temporal evolution of volumes')

        self.data = None
        self.start_time = None
        self.datetime = []
        self.var_ID = None
        self.second_var_ID = None

        # initialize graphical parameters
        self.show_date = False
        self.current_columns = ('Polygon 1',)
        self.column_labels = {}
        self.column_colors = {}

        self.locatePolygonAct = QAction('Locate polygons on map', self, icon=self.style().standardIcon(QStyle.SP_DialogHelpButton),
                                        triggered=self.locate)
        self.selectColumnsAct = QAction('Select columns', self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.selectColumns)
        self.editColumnNamesAct = QAction('Edit column names', self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                          triggered=self.editColumns)
        self.editColumColorAct = QAction('Edit column color', self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                          triggered=self.editColor)

        self.convertTimeAct = QAction('Show date/time', self, checkable=True,
                                      icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.changeDateAct = QAction('Modify start date', self, triggered=self.changeDate,
                                     icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))

        self.convertTimeAct.changed.connect(self.convertTime)

        self.toolBar.addAction(self.locatePolygonAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.mapMenu = QMenu('&Map', self)
        self.mapMenu.addAction(self.locatePolygonAct)
        self.polyMenu = QMenu('&Polygons', self)
        self.polyMenu.addAction(self.selectColumnsAct)
        self.polyMenu.addAction(self.editColumnNamesAct)
        self.polyMenu.addAction(self.editColumColorAct)
        self.timeMenu = QMenu('&Date/&Time', self)
        self.timeMenu.addAction(self.convertTimeAct)
        self.timeMenu.addAction(self.changeDateAct)

        self.menuBar.addMenu(self.mapMenu)
        self.menuBar.addMenu(self.polyMenu)
        self.menuBar.addMenu(self.timeMenu)

    def _defaultXLabel(self, language):
        if language == 'fr':
            return 'Temps (seconde)'
        return 'Time (second)'

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
            self.canvas.axes.plot(self.data['time'], self.data[column], '-', color=self.column_colors[column],
                                  linewidth=2, label=self.column_labels[column])
        self.canvas.axes.legend()
        self.canvas.axes.grid()
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.show_date:
            self.canvas.axes.set_xticklabels(self.str_datetime)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        else:
            self.canvas.axes.set_xlabel(self.current_xlabel)

        self.canvas.draw()

    def getData(self):
        # reinitialize old graphical parameters
        self.show_date = False
        self.current_columns = ('Polygon 1',)
        self.current_title = ''
        self.current_size = (8.0, 6.0)
        self.column_labels = {}
        self.column_colors = {}

        # get the new data
        csv_file = self.parent.csvNameBox.text()
        self.data = pd.read_csv(csv_file, header=0, sep=';')

        self.var_ID = self.parent.var_ID
        self.second_var_ID = self.parent.second_var_ID
        if self.parent.header.date is not None:
            year, month, day, hour, minute, second = self.parent.header.date
            self.start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            self.start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time'])
        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))

        columns = list(self.data)[1:]
        self.column_labels = {x: x for x in columns}
        self.column_colors = {x: None for x in columns}
        for i in range(min(len(columns), len(self.defaultColors))):
            self.column_colors[columns[i]] = self.defaultColors[i]
        self.triangles = list(self.parent.triangles.triangles.values())

        # initialize the plot
        self.current_xlabel = self._defaultXLabel(self.parent.language)
        self.current_ylabel = self._defaultYLabel(self.parent.language)
        self.current_title = ''
        self.replot()

    def locate(self):
        if not self.map.hasFigure:
            reply = QMessageBox.question(self, 'Locate polygons on map',
                                         'This may take up to one minute. Are you sure to proceed?\n'
                                         '(You can still modify the volume plot with the map open)',
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
            self.map.initFigure()

        self.locatePolygonAct.setEnabled(False)
        self.map.show()

    def selectColumns(self):
        msg = PlotColumnsSelector(list(self.data)[1:], self.current_columns)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        self.current_columns = msg.selection
        self.replot()

    def editColumns(self):
        msg = ColumnNameEditor(self.column_labels, self.current_columns)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLabels(self.column_labels)
        self.replot()

    def editColor(self):
        msg = ColumnColorEditor(self)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.column_colors, self.column_labels, self.nameToColor)
        self.replot()

    def changeDate(self):
        value, ok = QInputDialog.getText(self, 'Change start date',
                                         'Enter the start date',
                                         text=self.start_time.strftime('%Y-%m-%d %X'))
        if not ok:
            return
        try:
            self.start_time = datetime.datetime.strptime(value, '%Y-%m-%d %X')
        except ValueError:
            QMessageBox.critical(self, 'Error', 'Invalid input.',
                                 QMessageBox.Ok)
            return
        self.datetime = map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time'])
        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.replot()

    def convertTime(self):
        self.show_date = not self.show_date
        self.xLabelAct.setEnabled(not self.show_date)
        self.replot()

    def closeEvent(self, event):
        self.parent.setEnabled(True)
        self.parent.setWindowFlags(self.parent.windowFlags() | Qt.WindowCloseButtonHint)
        self.parent.show()
        event.accept()


class ComputeVolumeGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.header = None
        self.language = 'fr'
        self.time = []
        self.triangles = None
        self.locations = tuple([])
        self.polygons = []
        self.var_ID = None
        self.second_var_ID = None

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setFixedWidth(750)
        self.setMaximumHeight(750)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowTitle('Compute and visualize volumes inside polygons')

    def _initWidgets(self):
        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.frenchButton.setChecked(True)

        # create the button open Serafin
        self.btnOpenSerafin = QPushButton('Load\nSerafin', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenSerafin.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSerafin.setFixedSize(105, 50)

        # create the button open Polygon
        self.btnOpenPolygon = QPushButton('Load\nPolygons', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenPolygon.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolygon.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.polygonNameBox = QLineEdit()
        self.polygonNameBox.setReadOnly(True)
        self.polygonNameBox.setFixedHeight(30)
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

        # create the button for opening the image viewer
        self.btnImage = QPushButton('Visualize results', self)
        self.btnImage.setFixedSize(135, 60)
        self.btnImage.setEnabled(False)

        # create the image viewer
        self.img = VolumePlotViewer(self)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnImage.clicked.connect(self.btnImageEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addWidget(self.btnOpenSerafin)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('     Input file'))
        hlayout.addWidget(self.serafinNameBox)
        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('     Summary'))
        hlayout.addWidget(self.summaryTextBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 20))
        hlayout = QHBoxLayout()
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
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addWidget(self.btnImage)
        mainLayout.setAlignment(self.btnImage, Qt.AlignHCenter)
        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def closeEvent(self, event):
        if self.parent is not None:
            self.parent.closeVolume()
        event.accept()

    def _handleOverwrite(self, filename):
        """!
        @brief (Used in btnSubmitEvent) Handle manually the overwrite option when saving output file
        """
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it ?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                return None
            return True
        return False

    def _reinitInput(self, filename):
        self.filename = filename
        self.serafinNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.csvNameBox.clear()
        self.header = None
        self.time = []
        self.triangles = None
        self.locations = tuple([])
        self.firstVarBox.clear()
        self.secondVarBox.clear()
        self.csvNameBox.clear()
        self.btnImage.setEnabled(False)
        self.timeSampling.setText('1')

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return

        self._reinitInput(filename)

        with Serafin.Read(self.filename, self.language) as resin:
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

            # record the triangles for future visualization
            self.locations = (min(resin.header.x), max(resin.header.x), min(resin.header.y), max(resin.header.y))
            self.triangles = TruncatedTriangularPrisms(resin)

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        self.secondVarBox.addItem('0')
        self.secondVarBox.addItem('Initial values of the first variable')

        for var_ID, var_name in zip(self.header.var_IDs, self.header.var_names):
            self.firstVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())
            self.secondVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())

    def btnOpenPolygonEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return
        is_i2s = filename[-4:] == '.i2s'
        is_shp = filename[-4:] == '.shp'

        if not is_i2s and not is_shp:
            QMessageBox.critical(self, 'Error', 'Only .i2s and .shp file formats are currently supported.',
                                 QMessageBox.Ok)
            return

        self.polygonNameBox.clear()
        self.polygonNameBox.setText(filename)
        self.polygons = []
        self.csvNameBox.clear()
        self.btnImage.setEnabled(False)

        if is_i2s:
            with BlueKenue.Read(filename) as f:
                f.read_header()
                for poly_name, poly in f:
                    self.polygons.append(poly)
        else:
            for polygon in Shapefile.read_shp(filename):
                self.polygons.append(polygon)

        logging.info('Finished reading the polygon file %s' % filename)

    def btnSubmitEvent(self):
        if not self.polygons or self.header is None:
            return

        try:
            sampling_frequency = int(self.timeSampling.text())
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be a number!',
                                 QMessageBox.Ok)
            return
        if sampling_frequency < 1 or sampling_frequency > len(self.time):
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

        # disable close button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()

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
                calculator = VolumeCalculatorGUI(VolumeCalculator.POSITIVE, self.var_ID, self.second_var_ID,
                                                 resin, names, self.polygons, sampling_frequency, self.triangles)
            else:
                calculator = VolumeCalculatorGUI(VolumeCalculator.NET, self.var_ID, self.second_var_ID,
                                                 resin, names, self.polygons, sampling_frequency, self.triangles)

            progressBar.setValue(5)
            QApplication.processEvents()
            progressBar.connectToCalculator(calculator)

            with open(filename, 'w') as f2:
                calculator.write_csv(f2)

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()

        # enable close button
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

        # unlock the image viewer
        self.btnImage.setEnabled(True)
        self.img.getData()

    def btnImageEvent(self):
        self.setEnabled(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()
        self.img.show()


def exception_hook(exctype, value, traceback):
    """!
    @brief Needed for supressing traceback silencing in newer vesion of PyQt5
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
