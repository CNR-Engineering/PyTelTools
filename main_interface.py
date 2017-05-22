import sys

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from gui.ExtractVariablesGUI import ExtractVariablesGUI
from gui.PointsGUI import PointsGUI
from gui.LinesGUI import LinesGUI
from gui.ComputeVolumeGUI import ComputeVolumeGUI
from gui.CompareResultsGUI import CompareResultsGUI
from gui.ComputeFluxGUI import ComputeFluxGUI



class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()

        extract = ExtractVariablesGUI(self)
        points = PointsGUI(self)
        lines = LinesGUI(self)
        volume = ComputeVolumeGUI(self)
        compare = CompareResultsGUI(self)
        flux = ComputeFluxGUI(self)

        stackLayout = QStackedLayout()
        stackLayout.addWidget(QLabel('Hello! This is the start page (TODO)'))
        stackLayout.addWidget(extract)
        stackLayout.addWidget(points)
        stackLayout.addWidget(lines)
        stackLayout.addWidget(volume)
        stackLayout.addWidget(flux)
        stackLayout.addWidget(compare)

        pageList = QListWidget()
        pageList.setFixedWidth(200)
        for name in ['Start', 'Extract variables', 'Interpolate on points',
                     'Interpolate along lines', 'Compute volume', 'Compute flux', 'Compare two results']:
            pageList.addItem('\n' + name + '\n')
        pageList.setFlow(QListView.TopToBottom)
        pageList.currentRowChanged.connect(stackLayout.setCurrentIndex)
        pageList.setCurrentRow(0)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(pageList)
        mainLayout.addWidget(vline)
        mainLayout.addLayout(stackLayout)

        self.setLayout(mainLayout)
        self.setWindowTitle('Main window')
        self.resize(300, 300)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.frameGeom = self.frameGeometry()
        self.move(self.frameGeom.center())
        self.show()

    def inDialog(self):
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.setEnabled(False)
        self.show()

    def outDialog(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.setEnabled(True)
        self.show()


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
    window = MyMainWindow()
    app.exec_()

