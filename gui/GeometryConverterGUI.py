import sys
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import numpy as np
import logging
from geom.Shapefile import get_attribute_names
from geom.transformation import IDENTITY, load_transformation_map
import geom.conversion as convert
from slf import Serafin
from gui.util import handleOverwrite, QPlainTextEditLogger, TelToolWidget, OutputProgressDialog, OutputThread, testOpen


class MeshTransformThread(OutputThread):
    def __init__(self, input_stream, output_stream, transformations):
        super().__init__()
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.transformations = transformations

        self.nb_var = self.input_stream.header.nb_var
        self.nb_nodes = self.input_stream.header.nb_nodes
        self.var_IDs = self.input_stream.header.var_IDs
        self.nb_frames = len(self.input_stream.time)

    def run(self):
        self.tick.emit(1)
        QApplication.processEvents()

        # apply transformations
        from_x = self.input_stream.header.x
        from_y = self.input_stream.header.y
        points = [np.array([x, y, 0]) for x, y in zip(from_x, from_y)]
        for t in self.transformations:
            if self.canceled:
                return
            points = [t(p) for p in points]
        output_header = self.input_stream.header.copy()
        output_header.x = np.array([p[0] for p in points])
        output_header.y = np.array([p[1] for p in points])

        self.tick.emit(10)
        QApplication.processEvents()

        # write header
        self.output_stream.write_header(output_header)
        self.tick.emit(20)
        QApplication.processEvents()

        # copy values
        for time_index, time_value in enumerate(self.input_stream.time):
            if self.canceled:
                return
            values = np.empty((self.nb_var, self.nb_nodes))
            for i, var_ID in enumerate(self.var_IDs):
                values[i, :] = self.input_stream.read_var_in_frame(time_index, var_ID)
            self.output_stream.write_entire_frame(output_header, time_value, values)

            self.tick.emit(20 + 80 * (time_index+1) / self.nb_frames)
            QApplication.processEvents()


class PointConverterTab(QWidget):
    def __init__(self):
        super().__init__()
        self.transformation = None

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """

        # create the group box for coordinate transformation
        self.confBox = QGroupBox('Apply coordinate transformation (optional)')
        self.confBox.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        self.btnConfig = QPushButton('Load\nTransformation', self)
        self.btnConfig.setToolTip('<b>Open</b> a transformation config file')
        self.btnConfig.setFixedSize(105, 50)
        self.confNameBox = QLineEdit()
        self.confNameBox.setReadOnly(True)
        self.confNameBox.setFixedHeight(30)
        self.fromBox = QComboBox()
        self.fromBox.setFixedWidth(150)
        self.toBox = QComboBox()

        # create the open button
        self.btnOpen = QPushButton('Load\npoints', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a .xyz or .shp file')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.inNameBox.setFixedHeight(30)
        self.outNameBox = QLineEdit()
        self.outNameBox.setReadOnly(True)
        self.outNameBox.setFixedHeight(30)

        # create the option boxes
        self.toBox.setFixedWidth(150)
        self.outFileType = QComboBox()
        self.outFileType.addItem('.xyz')
        self.outFileType.addItem('.shp')
        self.outFileType.setFixedHeight(30)
        self.zfield = QComboBox()
        self.zfield.setFixedHeight(30)
        self.znameBox = QLineEdit('Z')
        self.znameBox.setFixedHeight(30)
        self.zfield.setEnabled(False)
        self.znameBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to .xyz or .shp')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnConfig)
        hlayout.addWidget(self.confNameBox)
        vlayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Transform from'))
        hlayout.addWidget(self.fromBox)
        hlayout.addWidget(QLabel('to'))
        hlayout.addWidget(self.toBox)
        hlayout.setAlignment(Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.setSpacing(15)
        self.confBox.setLayout(vlayout)
        mainLayout.addWidget(self.confBox)

        mainLayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpen)
        hlayout.addWidget(self.inNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Input Z column name'))
        hlayout.addWidget(self.zfield)
        mainLayout.addLayout(hlayout)
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Output format'))
        hlayout.addWidget(self.outFileType)
        hlayout.addWidget(QLabel('Output Z column name'))
        hlayout.addWidget(self.znameBox)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.outNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnConfig.clicked.connect(self.btnConfigEvent)
        self.outFileType.currentIndexChanged.connect(self.enableZ)

    def btnConfigEvent(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.confNameBox.clear()
        self.transformation = None

        success, self.transformation = load_transformation_map(filename)
        if not success:
            QMessageBox.critical(self, 'Error', 'The configuration is not valid.',
                                 QMessageBox.Ok)
            return
        self.confNameBox.setText(filename)
        for label in self.transformation.labels:
            self.fromBox.addItem(label)
            self.toBox.addItem(label)

    def enableZ(self, index):
        if index == 1:
            self.znameBox.setEnabled(True)
            self.znameBox.setText('Z')
        else:
            self.znameBox.clear()
            self.znameBox.setEnabled(False)

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a point set file', '',
                                                  '.xyz Files (*.xyz);;.shp Files (*.shp)', options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self.zfield.clear()
        self.inNameBox.setText(filename)
        if filename[-4:] == '.shp':
            self.zfield.setEnabled(True)
            fields, _ = get_attribute_names(filename)
            for field in fields:
                self.zfield.addItem(field)
        elif filename[-4:] == '.xyz':
            self.zfield.setEnabled(False)
        else:
            return
        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
        output_type = self.outFileType.currentText()
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  '%s Files (*%s);;All Files (*)' % (output_type, output_type),
                                                  options=options)
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != output_type:
            filename += output_type
        if filename == self.inNameBox.text():
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        if self.transformation is None:
            trans = [IDENTITY]
        else:
            from_index, to_index = self.fromBox.currentIndex(), self.toBox.currentIndex()
            trans = self.transformation.get_transformation(from_index, to_index)

        self.outNameBox.setText(filename)
        from_file = self.inNameBox.text()
        to_file = filename

        logging.info('Start conversion from %s\nto %s' % (from_file, to_file))
        converter = convert.PointSetConverter(from_file, to_file, trans,
                                              self.znameBox.text(), self.zfield.currentIndex())
        success, cause = converter.convert()
        if not success:
            if cause == 'number':
                QMessageBox.critical(self, 'Error', 'The input Z column is not numeric.',
                                     QMessageBox.Ok)
            else:
                QMessageBox.critical(self, 'Error', "The input file doesn't contain any point.",
                                     QMessageBox.Ok)
            logging.info('Conversion failed.')
            return
        logging.info('Conversion finished with success.')


class LineConverterTab(QWidget):
    def __init__(self):
        super().__init__()
        self.transformation = None

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """

        # create the group box for coordinate transformation
        self.confBox = QGroupBox('Apply coordinate transformation (optional)')
        self.confBox.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        self.btnConfig = QPushButton('Load\nTransformation', self)
        self.btnConfig.setToolTip('<b>Open</b> a transformation config file')
        self.btnConfig.setFixedSize(105, 50)

        self.confNameBox = QLineEdit()
        self.confNameBox.setReadOnly(True)
        self.confNameBox.setFixedHeight(30)
        self.fromBox = QComboBox()
        self.fromBox.setFixedWidth(150)
        self.toBox = QComboBox()

        # create the open button
        self.btnOpen = QPushButton('Load\nlines', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a .i2s, .i3s or .shp file')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.inNameBox.setFixedHeight(30)
        self.outNameBox = QLineEdit()
        self.outNameBox.setReadOnly(True)
        self.outNameBox.setFixedHeight(30)

        # create the option boxes
        self.toBox.setFixedWidth(150)
        self.outFileType = QComboBox()
        self.outFileType.addItem('.i2s/.i3s')
        self.outFileType.addItem('.shp')
        self.outFileType.setFixedHeight(30)
        self.zfield = QComboBox()
        self.zfield.setFixedHeight(30)
        self.znameBox = QLineEdit('Z')
        self.znameBox.setFixedHeight(30)
        self.zfield.setEnabled(False)
        self.znameBox.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to .i2s, .i3s or .shp')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnConfig)
        hlayout.addWidget(self.confNameBox)
        vlayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Transform from'))
        hlayout.addWidget(self.fromBox)
        hlayout.addWidget(QLabel('to'))
        hlayout.addWidget(self.toBox)
        hlayout.setAlignment(Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.setSpacing(15)
        self.confBox.setLayout(vlayout)
        mainLayout.addWidget(self.confBox)

        mainLayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpen)
        hlayout.addWidget(self.inNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Input Z column name'))
        hlayout.addWidget(self.zfield)
        mainLayout.addLayout(hlayout)
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Output format'))
        hlayout.addWidget(self.outFileType)
        hlayout.addWidget(QLabel('Output Z column name'))
        hlayout.addWidget(self.znameBox)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.outNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnConfig.clicked.connect(self.btnConfigEvent)
        self.outFileType.currentIndexChanged.connect(self.outfileTypeChanged)

    def btnConfigEvent(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.confNameBox.clear()
        self.transformation = None

        success, self.transformation = load_transformation_map(filename)
        if not success:
            QMessageBox.critical(self, 'Error', 'The configuration is not valid.',
                                 QMessageBox.Ok)
            return
        self.confNameBox.setText(filename)
        for label in self.transformation.labels:
            self.fromBox.addItem(label)
            self.toBox.addItem(label)

    def outfileTypeChanged(self, index):
        if index == 1:
            self.znameBox.setEnabled(True)
            self.znameBox.setText('Z')
        else:
            self.znameBox.clear()
            self.znameBox.setEnabled(False)

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a line set file', '',
                                                  '.i2s Files (*.i2s);;.i3s Files (*.i3s);;.shp Files (*.shp)',
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self.zfield.clear()
        self.inNameBox.setText(filename)
        if filename[-4:] == '.shp':
            self.zfield.setEnabled(True)
            fields, _ = get_attribute_names(filename)
            for field in fields:
                self.zfield.addItem(field)
        elif filename[-4:] == '.i2s' or filename[-4:] == '.i3s':
            self.zfield.setEnabled(False)
        else:
            return
        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
        output_type = self.outFileType.currentText()
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  '%s Files (*%s);;All Files (*)' % (output_type, output_type),
                                                  options=options)
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != output_type:
            filename += output_type
        if filename == self.inNameBox.text():
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        if self.transformation is None:
            trans = [IDENTITY]
        else:
            from_index, to_index = self.fromBox.currentIndex(), self.toBox.currentIndex()
            trans = self.transformation.get_transformation(from_index, to_index)

        self.outNameBox.setText(filename)
        from_file = self.inNameBox.text()
        to_file = filename

        logging.info('Start conversion from %s\nto %s' % (from_file, to_file))
        converter = convert.PointSetConverter(from_file, to_file, trans,
                                              self.znameBox.text(), self.zfield.currentIndex())
        success, cause = converter.convert()
        if not success:
            if cause == 'number':
                QMessageBox.critical(self, 'Error', 'The input Z column is not numeric.',
                                     QMessageBox.Ok)
            else:
                QMessageBox.critical(self, 'Error', "The input file doesn't contain any point.",
                                     QMessageBox.Ok)
            logging.info('Conversion failed.')
            return
        logging.info('Conversion finished with success.')


class MeshTransformTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.filename = ''
        self.header = None
        self.time = []
        self.transformation = None

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """
        # create the group box for coordinate transformation
        self.confBox = QGroupBox('Apply coordinate transformation (optional)')
        self.confBox.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        self.btnConfig = QPushButton('Load\nTransformation', self)
        self.btnConfig.setToolTip('<b>Open</b> a transformation config file')
        self.btnConfig.setFixedSize(105, 50)

        self.confNameBox = QLineEdit()
        self.confNameBox.setReadOnly(True)
        self.confNameBox.setFixedHeight(30)
        self.fromBox = QComboBox()
        self.fromBox.setFixedWidth(150)
        self.toBox = QComboBox()
        self.toBox.setFixedWidth(150)

        # create the open button
        self.btnOpen = QPushButton('Load\nSerafin', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a .slf file')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.inNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setReadOnly(True)
        self.summaryTextBox.setFixedHeight(50)
        self.outNameBox = QLineEdit()
        self.outNameBox.setReadOnly(True)
        self.outNameBox.setFixedHeight(30)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b> to .i2s, .i3s or .shp')
        self.btnSubmit.setFixedSize(105, 50)
        self.btnSubmit.setEnabled(False)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnConfig)
        hlayout.addWidget(self.confNameBox)
        vlayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Transform from'))
        hlayout.addWidget(self.fromBox)
        hlayout.addWidget(QLabel('to'))
        hlayout.addWidget(self.toBox)
        hlayout.setAlignment(Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.setSpacing(15)
        self.confBox.setLayout(vlayout)
        mainLayout.addWidget(self.confBox)

        mainLayout.addItem(QSpacerItem(10, 15))
        glayout = QGridLayout()
        glayout.addWidget(self.btnOpen, 1, 1)
        glayout.addWidget(self.inNameBox, 1, 2)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        mainLayout.addLayout(glayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.outNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnConfig.clicked.connect(self.btnConfigEvent)

    def _reinitInput(self, filename):
        self.filename = filename
        self.inNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.header = None
        self.time = []
        self.btnSubmit.setEnabled(False)

    def btnConfigEvent(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.confNameBox.clear()
        self.transformation = None

        success, self.transformation = load_transformation_map(filename)
        if not success:
            QMessageBox.critical(self, 'Error', 'The configuration is not valid.',
                                 QMessageBox.Ok)
            return
        self.confNameBox.setText(filename)
        for label in self.transformation.labels:
            self.fromBox.addItem(label)
            self.toBox.addItem(label)

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitInput(filename)

        with Serafin.Read(filename, 'fr') as resin:
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

            # copy to avoid reading the same data in the future
            self.header = resin.header.copy()
            self.time = resin.time[:]

        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        options |= QFileDialog.DontConfirmOverwrite

        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  '.slf Files (*.slf)', options=options)
        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.slf':
            filename += '.slf'

        # overwrite to the input file is forbidden
        if filename == self.filename:
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return

        # handle overwrite manually
        overwrite = handleOverwrite(filename)
        if overwrite is None:
            return

        if self.transformation is None:
            trans = [IDENTITY]
        else:
            from_index, to_index = self.fromBox.currentIndex(), self.toBox.currentIndex()
            trans = self.transformation.get_transformation(from_index, to_index)

        self.outNameBox.setText(filename)
        from_file = self.inNameBox.text()
        to_file = filename

        self.parent.inDialog()
        logging.info('Start transformation from %s\nto %s' % (from_file, to_file))
        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.filename, 'fr') as resin:
            resin.header = self.header
            resin.time = self.time

            with Serafin.Write(filename, 'fr', overwrite) as resout:
                process = MeshTransformThread(resin, resout, trans)
                progressBar.connectToThread(process)
                process.run()

                if not process.canceled:
                    progressBar.outputFinished()
        progressBar.exec_()
        self.parent.outDialog()


class GeometryConverterGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Conversion between file formats and coordinate transformations')

        self.point = PointConverterTab()
        self.line = LineConverterTab()
        self.mesh = MeshTransformTab(self)

        self.tab = QTabWidget()
        self.tab.addTab(self.point, 'Convert point sets')
        self.tab.addTab(self.line, 'Convert line sets')
        self.tab.addTab(self.mesh, 'Transform Serafin mesh')

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)
        self.resize(700, 500)


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
    widget = GeometryConverterGUI()
    widget.show()
    app.exec_()


