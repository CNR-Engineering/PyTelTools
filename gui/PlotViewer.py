import sys
import os
from shutil import copyfile
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from time import gmtime, strftime


class PlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.scaleFactor = 0.0
        self.figName = '.tmp_%s.png' % strftime("%Y_%m_%d_%H_%M_%S", gmtime())
        self.defaultColors = ['b', 'r', 'g', 'y', 'k']

        self.imageLabel = QLabel()
        self.imageLabel.setBackgroundRole(QPalette.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Ignored,
                                      QSizePolicy.Ignored)
        self.imageLabel.setScaledContents(True)

        self.menuBar = QMenuBar()
        self.toolBar = QToolBar()

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.imageLabel)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.menuBar)
        vlayout.addWidget(self.toolBar)
        vlayout.addWidget(self.scrollArea)
        vlayout.setSpacing(0)
        vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vlayout)

        self.createActions()
        self.createMenus()
        self.createTools()

        self.setWindowTitle('Plot Viewer')
        self.resize(600, 600)

    def save(self):
        if not os.path.exists(self.figName):
            return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, 'Save image', '',
                                                  'PNG Files (*.png)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.png':
            filename += '.png'

        # simply move the temporary file to the desired location
        copyfile(self.figName, filename)

    def openImage(self, image):
        self.imageLabel.setPixmap(QPixmap.fromImage(image))

        self.titleAct.setEnabled(True)
        self.xLabelAct.setEnabled(True)
        self.yLabelAct.setEnabled(True)
        self.scaleFactor = 1.0
        self.zoomInAct.setEnabled(True)
        self.zoomOutAct.setEnabled(True)
        self.normalSizeAct.setEnabled(True)
        self.imageLabel.adjustSize()

    def createActions(self):
        icons = self.style().standardIcon
        self.saveAct = QAction('Save', self, shortcut='Ctrl+S',
                               triggered=self.save, icon=icons(QStyle.SP_DialogSaveButton))
        self.exitAct = QAction('Exit', self,
                               triggered=self.close, icon=icons(QStyle.SP_DialogCloseButton))
        self.titleAct = QAction('Modify title', self, enabled=False, triggered=self.changeTitle)
        self.xLabelAct = QAction('Modify X label', self, enabled=False, triggered=self.changeXLabel)
        self.yLabelAct = QAction('Modify Y label', self, enabled=False, triggered=self.changeYLabel)

        self.zoomInAct = QAction('Zoom In (25%)', self, shortcut='Ctrl++',
                                 enabled=False, triggered=self.zoomIn)
        self.zoomOutAct = QAction('Zoom Out (25%)', self, shortcut='Ctrl+-',
                                  enabled=False, triggered=self.zoomOut)
        self.normalSizeAct = QAction('Normal Size', self, enabled=False, triggered=self.normalSize)

    def changeTitle(self):
        pass

    def changeXLabel(self):
        pass

    def changeYLabel(self):
        pass

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.imageLabel.adjustSize()
        self.scaleFactor = 1.0

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.editMenu = QMenu("&Edit", self)
        self.editMenu.addAction(self.titleAct)
        self.editMenu.addAction(self.xLabelAct)
        self.editMenu.addAction(self.yLabelAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)

        self.menuBar.addMenu(self.fileMenu)
        self.menuBar.addMenu(self.editMenu)
        self.menuBar.addMenu(self.viewMenu)

    def createTools(self):
        self.toolBar.addAction(self.saveAct)
        self.toolBar.addSeparator()

    def scaleImage(self, factor):
        self.scaleFactor *= factor
        self.imageLabel.resize(self.scaleFactor * self.imageLabel.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                           + ((factor - 1) * scrollBar.pageStep() / 2)))


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
    widget = PlotViewer()
    widget.show()
    sys.exit(app.exec_())