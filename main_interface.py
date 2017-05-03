import sys

from PyQt5.QtWidgets import *

from gui.ExtractVariablesGUI import ExtractVariablesGUI
from gui.ComputeVolumeGUI import ComputeVolumeGUI


class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.btnOpenConverter = QPushButton('Format Converter')
        self.btnOpenConverter.setToolTip('<b>Convert</b> between geometrical file formats')
        self.btnOpenConverter.setFixedHeight(50)
        self.btnOpenSerafin = QPushButton('Extract variables')
        self.btnOpenSerafin.setToolTip('<b>Extract</b> variables and frames from Serafin file')
        self.btnOpenSerafin.setFixedHeight(50)
        self.btnOpenVolume = QPushButton('Compute volumes')
        self.btnOpenVolume.setToolTip('<b>Compute</b> and <b>visualize</b> volumes inside polygons')

        self.btnOpenVolume.setFixedHeight(50)

        self.slf = ExtractVariablesGUI(self)
        self.volume = ComputeVolumeGUI(self)

        self.btnOpenSerafin.clicked.connect(self.openSerafin)
        self.btnOpenVolume.clicked.connect(self.openVolume)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.btnOpenConverter)
        hline = QFrame()
        hline.setFrameShape(QFrame.HLine)
        vlayout.addWidget(hline)
        vlayout.addWidget(self.btnOpenSerafin)
        hline = QFrame()
        hline.setFrameShape(QFrame.HLine)
        vlayout.addWidget(hline)
        vlayout.addWidget(self.btnOpenVolume)

        self.setLayout(vlayout)

        self.setWindowTitle('Main window')
        self.resize(300, 300)

        self.frameGeom = self.frameGeometry()
        self.move(self.frameGeom.center())
        self.show()

    def openSerafin(self):
        self.slf.show()
        self.btnOpenSerafin.setEnabled(False)

    def closeSerafin(self):
        self.slf.hide()
        self.btnOpenSerafin.setEnabled(True)

    def openVolume(self):
        self.volume.show()
        self.btnOpenVolume.setEnabled(False)

    def closeVolume(self):
        self.volume.hide()
        self.btnOpenVolume.setEnabled(True)


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
    window = MyMainWindow()
    app.exec_()

