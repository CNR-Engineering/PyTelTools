import sys
import os
import logging
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure



class QPlainTextEditLogger(logging.Handler):
    """!
    @brief A text edit box displaying the message logs
    """
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)


class TableWidgetDragRows(QTableWidget):
    """!
    @brief Table widget enabling drag-and-drop of rows
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragDropOverwriteMode(False)
        self.last_drop_row = None

    # Override this method to get the correct row index for insertion
    def dropMimeData(self, row, col, mimeData, action):
        self.last_drop_row = row
        return True

    def dropEvent(self, event):
        # The QTableWidget from which selected rows will be moved
        sender = event.source()

        # Default dropEvent method fires dropMimeData with appropriate parameters (we're interested in the row index).
        super().dropEvent(event)
        # Now we know where to insert selected row(s)
        dropRow = self.last_drop_row

        selectedRows = sender.getselectedRowsFast()

        # Allocate space for transfer
        for _ in selectedRows:
            self.insertRow(dropRow)

        # if sender == receiver (self), after creating new empty rows selected rows might change their locations
        sel_rows_offsets = [0 if self != sender or srow < dropRow else len(selectedRows) for srow in selectedRows]
        selectedRows = [row + offset for row, offset in zip(selectedRows, sel_rows_offsets)]

        # copy content of selected rows into empty ones
        for i, srow in enumerate(selectedRows):
            for j in range(self.columnCount()):
                item = sender.item(srow, j)
                if item:
                    source = QTableWidgetItem(item)
                    self.setItem(dropRow + i, j, source)

        # delete selected rows
        for srow in reversed(selectedRows):
            sender.removeRow(srow)

        event.accept()

    def getselectedRowsFast(self):
        selectedRows = []
        for item in self.selectedItems():
            if item.row() not in selectedRows:
                selectedRows.append(item.row())
        selectedRows.sort()
        return selectedRows


class PlotCanvas(FigureCanvas):
    def __init__(self, parent):
        self.parent = parent
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.axes = self.figure.add_subplot(111)

        FigureCanvas.__init__(self, self.figure)
        self.setParent(None)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)


class PlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = PlotCanvas(self)
        self.current_xlabel = 'X'
        self.current_ylabel = 'Y'
        self.current_title = 'Default plot'

        # add a default plot
        self.defaultPlot()

        # add the menu bar and the tool bar
        self.menuBar = QMenuBar()
        self.toolBar = QToolBar()
        self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.canvas)

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
        self.resize(850, 700)

    def save(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, 'Save image', '',
                                                  'PNG Files (*.png)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.png':
            filename += '.png'

        self.canvas.print_png(filename)

    def createActions(self):
        icons = self.style().standardIcon
        self.saveAct = QAction('Save', self, shortcut='Ctrl+S',
                               triggered=self.save, icon=icons(QStyle.SP_DialogSaveButton))
        self.exitAct = QAction('Exit', self,
                               triggered=self.close, icon=icons(QStyle.SP_DialogCloseButton))
        self.titleAct = QAction('Modify title', self, triggered=self.changeTitle)
        self.xLabelAct = QAction('Modify X label', self, triggered=self.changeXLabel)
        self.yLabelAct = QAction('Modify Y label', self, triggered=self.changeYLabel)

    def changeTitle(self):
        value, ok = QInputDialog.getText(self, 'Change title',
                                         'Enter a new title', text=self.canvas.axes.get_title())
        if not ok:
            return
        self.canvas.axes.set_title(value)
        self.canvas.draw()
        self.current_title = value

    def changeXLabel(self):
        value, ok = QInputDialog.getText(self, 'Change X label',
                                         'Enter a new X label', text=self.canvas.axes.get_xlabel())
        if not ok:
            return
        self.canvas.axes.set_xlabel(value)
        self.canvas.draw()
        self.current_xlabel = value

    def changeYLabel(self):
        value, ok = QInputDialog.getText(self, 'Change X label',
                                         'Enter a new X label', text=self.canvas.axes.get_ylabel())
        if not ok:
            return
        self.canvas.axes.set_ylabel(value)
        self.canvas.draw()
        self.current_ylabel = value

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.editMenu = QMenu("&Edit", self)
        self.editMenu.addAction(self.titleAct)
        self.editMenu.addAction(self.xLabelAct)
        self.editMenu.addAction(self.yLabelAct)

        self.menuBar.addMenu(self.fileMenu)
        self.menuBar.addMenu(self.editMenu)

    def createTools(self):
        self.toolBar.addAction(self.saveAct)
        self.toolBar.addSeparator()

    def defaultPlot(self):
        x = np.linspace(0, 30, 100)
        y = np.sin(x)
        self.current_xlabel = 'X'
        self.current_ylabel = 'Y'
        self.current_title = 'Default plot'
        self.plot(x, y)

    def plot(self, x, y):
        """!
        Default plotting behaviour
        """
        self.canvas.axes.clear()
        self.canvas.axes.plot(x, y, 'b-', linewidth=2)
        self.canvas.axes.grid()
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        self.canvas.draw()


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