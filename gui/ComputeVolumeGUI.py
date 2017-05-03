import sys

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

class ComputeVolumeGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

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
        self.polygonNameBox = QLineEdit()
        self.polygonNameBox.setReadOnly(True)



        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.btnOpenSerafin)
        vlayout.addWidget(self.btnOpenPolygon)
        self.setLayout(vlayout)

        self.setFixedSize(800, 750)
        self.setWindowTitle('Compute and visualize volumes inside polygons')

    def closeEvent(self, event):
        if self.parent is not None:
            self.parent.closeVolume()
        event.accept()

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return
        self.serafinNameBox.clear()
        self.serafinNameBox.setText(filename)

    def btnOpenPolygonEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return
        self.polygonNameBox.clear()
        self.polygonNameBox.setText(filename)


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
    app.exec_()
