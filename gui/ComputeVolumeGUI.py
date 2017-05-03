import sys
import os
import copy
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from slf import Serafin
from slf.volume import *
from geom import BlueKenue


class ComputeVolumeGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.header = None
        self.time = []
        self.polygons = []

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setFixedSize(600, 350)
        self.setWindowTitle('Compute and visualize volumes inside polygons')

    def _initWidgets(self):
        # create the button open Serafin
        self.btnOpenSerafin = QPushButton('Load Serafin', self)
        self.btnOpenSerafin.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSerafin.setFixedSize(105, 50)

        # create the button open Polygon
        self.btnOpenPolygon = QPushButton('Load Polygons', self)
        self.btnOpenPolygon.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolygon.setFixedSize(105, 50)


        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedSize(600, 30)
        self.polygonNameBox = QLineEdit()
        self.polygonNameBox.setReadOnly(True)
        self.polygonNameBox.setFixedSize(600, 30)

        # create combo box widgets for choosing variables
        self.firstVarBox = QComboBox()
        self.firstVarBox.setFixedSize(300, 30)
        self.secondVarBox = QComboBox()
        self.secondVarBox.setFixedSize(300, 30)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self)
        self.btnSubmit.setFixedSize(105, 50)

        # create the check for selecting superior volume
        self.supVolumeBox = QCheckBox('Compute positive volumes (slow)', self)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)

    def _setLayout(self):
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpenSerafin)
        hlayout.addWidget(self.serafinNameBox)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpenPolygon)
        hlayout.addWidget(self.polygonNameBox)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        lb = QLabel('     Select the principal variable')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addWidget(self.firstVarBox)
        hlayout.setAlignment(self.firstVarBox, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        lb = QLabel('     Select a variable to subtract (optional)')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addWidget(self.secondVarBox)
        hlayout.setAlignment(self.secondVarBox, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.supVolumeBox)
        hlayout.setAlignment(self.supVolumeBox, Qt.AlignHCenter)
        hlayout.addWidget(self.btnSubmit)
        hlayout.setAlignment(self.btnSubmit, Qt.AlignHCenter)
        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)

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

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return
        self.filename = filename
        self.serafinNameBox.setText(filename)
        self.header = None
        self.time = []


        with Serafin.Read(self.filename, 'fr') as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return
            # record the time series
            resin.get_time()

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        for var_ID in self.header.var_IDs:
            self.firstVarBox.addItem(var_ID)


    def btnOpenPolygonEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return

        if filename[-4:] != '.i2s':
            QMessageBox.critical(self, 'Error', 'Only .i2s file format is currently supported.',
                                 QMessageBox.Ok)
            return

        self.polygonNameBox.clear()
        self.polygonNameBox.setText(filename)
        self.polygons = []

        with BlueKenue.Read(filename) as f:
            f.read_header()
            for poly_name, poly in f:
                self.polygons.append(poly)

    def btnSubmitEvent(self):
        if not self.polygons or self.header is None:
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

        var_ID = self.firstVarBox.currentText()
        self.setEnabled(False)
        names = [str(i+1) for i in range(len(self.polygons))]
        with Serafin.Read(self.filename, 'fr') as f:
            f.header = self.header
            f.time = self.time
            with open(filename, 'w') as f2:
                if self.supVolumeBox.isChecked():
                    volume_superior(var_ID, f, f2, names, self.polygons)
                else:
                    volume_net(var_ID, f, f2, names, self.polygons)
        self.setEnabled(True)


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
