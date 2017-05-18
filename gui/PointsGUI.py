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
from slf.mesh2D import Mesh2D
from geom import Shapefile
from gui.util import TemporalPlotViewer, MapViewer, MapCanvas, QPlainTextEditLogger


class AttributeTable(QTableWidget):
    def __init__(self):
        super().__init__()
        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(100)
        self.resize(850, 600)
        self.setWindowTitle('Attribute table')

    def getData(self, points, is_inside, fields, all_attributes):
        self.setRowCount(0)

        self.setColumnCount(3 + len(fields))
        self.setHorizontalHeaderLabels(['x', 'y', 'inside'] + fields)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        i = 0
        for (x, y), inside, attributes in zip(points, is_inside, all_attributes):
            self.insertRow(i)
            self.setItem(i, 0, QTableWidgetItem('%.4f' % x))
            self.setItem(i, 1, QTableWidgetItem('%.4f' % y))
            self.setItem(i, 2, QTableWidgetItem(inside))
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
        self.attribute_table = AttributeTable()
        self.var_ID = None
        self.second_var_ID = None

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
        # self.csvNameBox = QLineEdit()
        # self.csvNameBox.setReadOnly(True)
        # self.csvNameBox.setFixedHeight(30)

        # create combo box widgets for choosing variables
        self.varBox = QComboBox()
        self.varBox.setFixedSize(400, 30)
        #
        # # create the boxes for volume calculation options
        # self.supVolumeBox = QCheckBox('Compute positive and negative volumes (slow)', self)
        self.timeSampling = QLineEdit('1')
        self.timeSampling.setFixedWidth(50)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPoints.clicked.connect(self.btnOpenPointsEvent)
        self.btnOpenAttributes.clicked.connect(self.btnOpenAttributesEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
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
        hlayout.addWidget(self.btnOpenPoints)
        hlayout.addWidget(self.pointsNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the variable'), 1, 1)
        glayout.addWidget(self.varBox, 1, 2)
        # glayout.addWidget(QLabel('     Select a variable to subtract (optional)'), 2, 1)
        # glayout.addWidget(self.secondVarBox, 2, 2)
        # glayout.addWidget(QLabel('     More options'), 3, 1)
        # glayout.addWidget(self.supVolumeBox, 3, 2)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Time sampling frequency'))
        hlayout.addWidget(self.timeSampling)
        hlayout.setAlignment(self.timeSampling, Qt.AlignLeft)
        hlayout.addStretch()
        glayout.addLayout(hlayout, 2, 2)

        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 20))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnOpenAttributes)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.btnSubmit)
        # hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)

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
        self.btnSubmit.setEnabled(False)
        self.btnOpenAttributes.setEnabled(False)
        self.mesh = None
        self.varBox.clear()
        self.pointsNameBox.clear()
        self.btnOpenPoints.setEnabled(True)
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
            self.mesh = Mesh2D(resin.header)

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        for var_ID, var_name in zip(self.header.var_IDs, self.header.var_names):
            self.varBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())

        # self.parent.imageTab.reset()
        # self.parent.tab.setTabEnabled(1, False)

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

        is_inside = ['Yes'] * len(self.points)
        self.attribute_table.getData(self.points, is_inside, fields, attributes)

        logging.info('Finished reading the points file %s' % filename)
        self.pointsNameBox.clear()
        self.pointsNameBox.appendPlainText(filename + '\n' + 'The file contains {} point{}.'.format(
                                           len(self.points), 's' if len(self.points) > 1 else ''))

        self.has_map = False
        self.btnSubmit.setEnabled(True)
        self.btnOpenAttributes.setEnabled(True)
        # self.parent.imageTab.reset()
        # self.parent.tab.setTabEnabled(1, False)

    def btnOpenAttributesEvent(self):
        self.attribute_table.show()

    def btnSubmitEvent(self):
        if not self.has_map:
            self.map.canvas.initFigure(self.mesh)
            self.map.canvas.axes.scatter(*zip(*self.points))
            self.map.canvas.draw()
            self.has_map = True
        self.map.show()



class PointsGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.input = InputTab(self)
        # self.imageTab = VolumePlotViewer(self.input)
        self.setWindowTitle('Plot the values of a variable on points')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        # self.tab.addTab(self.imageTab, 'Visualize results')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; width: 300px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)

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
    @brief Needed for supressing traceback silencing in newer vesion of PyQt5
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