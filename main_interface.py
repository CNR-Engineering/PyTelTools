import sys

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from gui.ExtractVariablesGUI import ExtractVariablesGUI
from gui.MaxMinMeanGUI import MaxMinMeanGUI

from gui.PointsGUI import PointsGUI
from gui.LinesGUI import LinesGUI
from gui.ProjectLinesGUI import ProjectLinesGUI
from gui.ComputeVolumeGUI import ComputeVolumeGUI
from gui.CompareResultsGUI import CompareResultsGUI
from gui.ComputeFluxGUI import ComputeFluxGUI
from gui.ProjectMeshGUI import ProjectMeshGUI
from gui.ConfigTransformation import TransformationMap
from gui.GeometryConverterGUI import FileConverterGUI


class MainPanel(QWidget):
    def __init__(self, parent):
        super().__init__()
        extract = ExtractVariablesGUI(parent)
        maxmin = MaxMinMeanGUI(parent)
        points = PointsGUI(parent)
        lines = LinesGUI(parent)
        project = ProjectLinesGUI(parent)
        mesh = ProjectMeshGUI(parent)
        volume = ComputeVolumeGUI(parent)
        compare = CompareResultsGUI(parent)
        flux = ComputeFluxGUI(parent)

        trans = TransformationMap()
        conv = FileConverterGUI(parent)

        self.stackLayout = QStackedLayout()
        self.stackLayout.addWidget(QLabel('Hello! This is the start page (TODO)'))
        self.stackLayout.addWidget(extract)
        self.stackLayout.addWidget(maxmin)
        self.stackLayout.addWidget(points)
        self.stackLayout.addWidget(lines)
        self.stackLayout.addWidget(project)
        self.stackLayout.addWidget(mesh)
        self.stackLayout.addWidget(volume)
        self.stackLayout.addWidget(flux)
        self.stackLayout.addWidget(compare)
        self.stackLayout.addWidget(trans)
        self.stackLayout.addWidget(conv)
        self.setLayout(self.stackLayout)

        self.stackLayout.currentChanged.connect(parent.autoResize)


class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.panel = MainPanel(self)

        pageList = QListWidget()
        pageList.setMaximumWidth(200)
        for name in ['Start', 'Extract variables', 'Max/Min/Mean/Arrival/Duration', 'Interpolate on points',
                     'Interpolate along lines', 'Project along lines', 'Project mesh',
                     'Compute volume', 'Compute flux', 'Compare two results',
                     'Transform coordinate systems', 'Convert geom file formats']:
            pageList.addItem('\n' + name + '\n')
        pageList.setFlow(QListView.TopToBottom)
        pageList.currentRowChanged.connect(self.panel.layout().setCurrentIndex)

        pageList.setCurrentRow(0)

        splitter = QSplitter()
        splitter.addWidget(pageList)
        splitter.addWidget(self.panel)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        self.setWindowTitle('Main window')
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.frameGeom = self.frameGeometry()
        self.move(self.frameGeom.center())
        self.show()

    def autoResize(self, index):
        if not self.isMaximized():
            self.resize(self.panel.stackLayout.widget(index).sizeHint())

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

