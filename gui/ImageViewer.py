import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.scaleFactor = 0.0

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

        self.setWindowTitle('Image Viewer')
        self.resize(600, 600)

    def open(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open File',
                                                  QDir.currentPath())
        if not filename:
            return
        image = QImage(filename)
        if image.isNull():
            QMessageBox.information(self, 'Image Viewer',
                                    'Cannot load %s.' % filename)
            return

        self.openImage(image)

    def save(self):
        pass

    def openImage(self, image):
        self.imageLabel.setPixmap(QPixmap.fromImage(image))
        self.scaleFactor = 1.0

        self.zoomInAct.setEnabled(True)
        self.zoomOutAct.setEnabled(True)
        self.normalSizeAct.setEnabled(True)
        self.imageLabel.adjustSize()

    def createActions(self):
        icons = self.style().standardIcon

        self.openAct = QAction('&Open...', self, shortcut='Ctrl+O',
                               triggered=self.open, icon=icons(QStyle.SP_DialogOpenButton))
        
        self.saveAct = QAction('&Save as...', self, shortcut='Ctrl+S',
                               triggered=self.save, icon=icons(QStyle.SP_DialogSaveButton))
        
        self.exitAct = QAction('E&xit', self,
                               triggered=self.close, icon=icons(QStyle.SP_DialogCloseButton))

        self.zoomInAct = QAction('Zoom &In (25%)', self, shortcut='Ctrl++', 
                                 enabled=False, triggered=self.zoomIn)

        self.zoomOutAct = QAction('Zoom &Out (25%)', self, shortcut='Ctrl+-', 
                                  enabled=False, triggered=self.zoomOut)

        self.normalSizeAct = QAction('&Normal Size', self, enabled=False, triggered=self.normalSize)

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.imageLabel.adjustSize()
        self.scaleFactor = 1.0

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)

        self.menuBar.addMenu(self.fileMenu)
        self.menuBar.addMenu(self.viewMenu)

    def createTools(self):
        self.toolBar.addAction(self.openAct)
        self.toolBar.addAction(self.saveAct)

    def scaleImage(self, factor):
        self.scaleFactor *= factor
        self.imageLabel.resize(self.scaleFactor * self.imageLabel.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                                + ((factor - 1) * scrollBar.pageStep()/2)))


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
    imageViewer = ImageViewer()
    imageViewer.show()
    sys.exit(app.exec_())