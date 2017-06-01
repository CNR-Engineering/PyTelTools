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
from gui.util import handleOverwrite, QPlainTextEditLogger, TelToolWidget, testOpen


class PointConverterTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
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

        # create the open config button
        self.btnConfig = QPushButton('Load\nTransformation', self)
        self.btnConfig.setToolTip('<b>Open</b> a transformation config file')
        self.btnConfig.setFixedSize(105, 50)

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


class FileConverterGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Conversion between file formats')

        self.point = PointConverterTab(self)

        self.tab = QTabWidget()
        self.tab.addTab(self.point, 'Convert point sets')

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
    widget = FileConverterGUI()
    widget.show()
    app.exec_()


