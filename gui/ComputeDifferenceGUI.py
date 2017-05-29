import sys
import logging
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import numpy as np

from gui.util import LoadMeshDialog, QPlainTextEditLogger, TelToolWidget, testOpen
from slf import Serafin


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.first_language = 'fr'
        self.second_language = 'fr'
        self.first_filename = None
        self.second_filename = None
        self.first_header = None
        self.second_header = None
        self.first_time = []
        self.second_time = []

        self.first_mesh = None
        self.second_mesh = None

        self._initWidgets()
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

        # create the button open the reference file
        self.btnOpenFirst = QPushButton('Load\nFile A', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenFirst.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenFirst.setFixedSize(105, 50)

        # create the button open the test file
        self.btnOpenSecond = QPushButton('Load\nFile B', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenSecond.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSecond.setFixedSize(105, 50)
        self.btnOpenSecond.setEnabled(False)

        # create some text fields displaying the IO files info
        self.firstNameBox = QLineEdit()
        self.firstNameBox.setReadOnly(True)
        self.firstNameBox.setFixedHeight(30)
        self.firstNameBox.setMinimumWidth(600)
        self.firstSummaryTextBox = QPlainTextEdit()
        self.firstSummaryTextBox.setMinimumHeight(40)
        self.firstSummaryTextBox.setMaximumHeight(50)
        self.firstSummaryTextBox.setMinimumWidth(600)
        self.firstSummaryTextBox.setReadOnly(True)
        self.secondNameBox = QLineEdit()
        self.secondNameBox.setReadOnly(True)
        self.secondNameBox.setFixedHeight(30)
        self.secondNameBox.setMinimumWidth(600)
        self.secondSummaryTextBox = QPlainTextEdit()
        self.secondSummaryTextBox.setReadOnly(True)
        self.secondSummaryTextBox.setMinimumHeight(40)
        self.secondSummaryTextBox.setMaximumHeight(50)
        self.secondSummaryTextBox.setMinimumWidth(600)
        
        # create combo box widgets for choosing the variable
        self.varBox = QComboBox()
        self.varBox.setFixedSize(400, 30)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenFirst.clicked.connect(self.btnOpenFirstEvent)
        self.btnOpenSecond.clicked.connect(self.btnOpenSecondEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 20))
        mainLayout.setSpacing(15)

        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpenFirst)
        hlayout.addWidget(self.btnOpenSecond)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     File A'), 1, 1)
        glayout.addWidget(self.firstNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.firstSummaryTextBox, 2, 2)
        glayout.addWidget(QLabel('     File B'), 3, 1)
        glayout.addWidget(self.secondNameBox, 3, 2)
        glayout.addWidget(QLabel('     Summary'), 4, 1)
        glayout.addWidget(self.secondSummaryTextBox, 4, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setVerticalSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the variable to compare'), 1, 1)
        glayout.addWidget(self.varBox, 1, 2)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.setAlignment(glayout, Qt.AlignTop | Qt.AlignLeft)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)
        self.setLayout(mainLayout)

    def _reinitFirst(self, filename):
        if not self.frenchButton.isChecked():
            self.first_language = 'en'
        else:
            self.first_language = 'fr'
        self.first_mesh = None
        self.first_filename = filename
        self.firstNameBox.setText(filename)
        self.firstSummaryTextBox.clear()
        self.first_header = None
        self.varBox.clear()

    def _reinitSecond(self, filename):
        if not self.frenchButton.isChecked():
            self.second_language = 'en'
        else:
            self.second_language = 'fr'
        self.second_header = None
        self.second_mesh = None
        self.second_filename = filename
        self.secondNameBox.setText(filename)
        self.secondSummaryTextBox.clear()
        self.varBox.clear()

    def _resetDefaultOptions(self):
        if self.second_header is not None:
            common_vars = [(var_ID, var_names) for var_ID, var_names
                            in zip(self.first_header.var_IDs, self.first_header.var_names)
                            if var_ID in self.first_header.var_IDs]
            if not common_vars:
                self._reinitSecond(self.second_filename)
            else:
                for var_ID, var_name in common_vars:
                    self.varBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())

    def btnOpenFirstEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitFirst(filename)

        with Serafin.Read(self.first_filename, self.first_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # record the mesh
            self.parent.inDialog()
            meshLoader = LoadMeshDialog('comparison', resin.header)
            self.first_mesh = meshLoader.run()
            self.parent.outDialog()
            if meshLoader.thread.canceled:
                return

            # update the file summary
            self.firstSummaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.first_header = resin.header.copy()
            self.first_time = resin.time[:]

        self.btnOpenSecond.setEnabled(True)
        self._resetDefaultOptions()

    def btnOpenSecondEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        self._reinitSecond(filename)

        with Serafin.Read(self.second_filename, self.second_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # record the mesh
            self.parent.inDialog()
            meshLoader = LoadMeshDialog('comparison', resin.header)
            self.second_mesh = meshLoader.run()
            self.parent.outDialog()
            if meshLoader.thread.canceled:
                return
            # 
            # # check if the mesh is identical to the reference
            # if not np.all(self.ref_header.x == resin.header.x) or \
            #    not np.all(self.ref_header.y == resin.header.y) or \
            #    not np.all(self.ref_header.ikle == resin.header.ikle):
            #     QMessageBox.critical(self, 'Error', 'The mesh is not identical to the reference.',
            #                          QMessageBox.Ok)
            #     return

            # check if the test file has common variables with the reference file
            common_vars = [(var_ID, var_names) for var_ID, var_names
                           in zip(self.first_header.var_IDs, self.first_header.var_names)
                           if var_ID in resin.header.var_IDs]
            if not common_vars:
                QMessageBox.critical(self, 'Error', 'No common variable with file A.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # update the file summary
            self.secondSummaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.second_header = resin.header.copy()
            self.second_time = resin.time[:]

        for var_ID, var_name in common_vars:
            self.varBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())


class ComputeDifferenceGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Compute the difference between two meshes')

        self.tab = QTabWidget()
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 150px; }')

        self.input = InputTab(self)

        self.tab.addTab(self.input, 'Input')
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
    widget = ComputeDifferenceGUI()
    widget.show()
    app.exec_()



