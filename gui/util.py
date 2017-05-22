import sys
import os
import logging

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import datetime
import shapely

import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.collections import PatchCollection
from descartes import PolygonPatch
from matplotlib import cm
import matplotlib.tri as tri
import matplotlib.lines as mlines

from matplotlib.colors import Normalize, colorConverter
from mpl_toolkits.axes_grid1 import make_axes_locatable
from rtree.index import Index

from slf.volume import TruncatedTriangularPrisms
from slf.flux import TriangularVectorField
from slf.comparison import ReferenceMesh
from slf.interpolation import MeshInterpolator


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


class OutputProgressDialog(QProgressDialog):
    def __init__(self, message='Output in progress', title='Writing the output...', parent=None):
        super().__init__(message, 'OK', 0, 100, parent)

        self.cancelButton = QPushButton('OK')
        self.setCancelButton(self.cancelButton)
        self.cancelButton.setEnabled(False)

        self.setAutoReset(False)
        self.setAutoClose(False)

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setFixedSize(300, 150)

        self.open()
        self.setValue(0)
        QApplication.processEvents()

    def connectToThread(self, thread):
        thread.tick.connect(self.setValue)


class ConstructIndexThread(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, mesh_type, input_header):
        super().__init__()
        self.input_header = input_header

        if mesh_type == 'volume':
            self.mesh = TruncatedTriangularPrisms(input_header, False)
        elif mesh_type == 'flux':
            self.mesh = TriangularVectorField(input_header, False)
        elif mesh_type == 'comparison':
            self.mesh = ReferenceMesh(input_header, False)
        else:
            self.mesh = MeshInterpolator(input_header, False)

    def run(self):
        self.mesh.index = Index()

        # emit a signal for every five percent of triangles processed
        five_percent = 0.05 * self.mesh.nb_triangles
        nb_processed = 0
        current_percent = 0

        for i, j, k in self.mesh.ikle:
            t = shapely.geometry.Polygon([self.mesh.points[i], self.mesh.points[j], self.mesh.points[k]])
            self.mesh.triangles[i, j, k] = t
            self.mesh.index.insert(i, t.bounds, obj=(i, j, k))

            nb_processed += 1
            if nb_processed > five_percent:
                nb_processed = 0
                current_percent += 5
                self.tick.emit(current_percent)
                QApplication.processEvents()
        return self.mesh


class LoadMeshDialog(OutputProgressDialog):
    def __init__(self, mesh_type, input_header):
        super().__init__('Processing the mesh. Please wait.', 'Processing the mesh...')
        self.thread = ConstructIndexThread(mesh_type, input_header)
        self.connectToThread(self.thread)

    def run(self):
        self.thread.run()
        self.setValue(100)
        self.cancelButton.setEnabled(True)
        self.exec_()
        return self.thread.mesh


class PlotColumnsSelector(QDialog):
    def __init__(self, columns, current_columns, name):
        super().__init__()
        self.name = name
        self.plural = str(''.join([name, 's']))

        self.list = QListWidget()
        for name in columns:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if name in current_columns:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)

        self.selection = tuple([])

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkSelection)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('  Select up to 8 %s to plot' % self.plural))
        vlayout.addWidget(self.list)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setWindowTitle('Select %s to plot' % self.plural)
        self.resize(self.sizeHint())
        self.setMinimumWidth(300)

    def getSelection(self):
        selection = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() == Qt.Checked:
                selection.append(item.text())
        return tuple(selection)

    def checkSelection(self):
        self.selection = self.getSelection()
        if not self.selection:
            QMessageBox.critical(self, 'Error', 'Select at least one %s to plot.' % self.name,
                                 QMessageBox.Ok)
            return
        if len(self.selection) > 8:
            QMessageBox.critical(self, 'Error', 'Select up to 8 %s.' % self.plural,
                                 QMessageBox.Ok)
            return
        self.accept()


class ColumnLabelEditor(QDialog):
    def __init__(self, column_labels, selected_columns, name):
        super().__init__()

        self.table = QTableWidget()
        self.table .setColumnCount(2)
        self.table .setHorizontalHeaderLabels([name, 'Label'])
        row = 0
        for column in selected_columns:
            label = column_labels[column]
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(label)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Click on the label to modify'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setWindowTitle('Change %s labels' % name)
        self.resize(self.sizeHint())
        self.setMinimumWidth(300)

    def getLabels(self, old_labels):
        for row in range(self.table.rowCount()):
            column = self.table.item(row, 0).text()
            label = self.table.item(row, 1).text()
            old_labels[column] = label


class ColorTable(QTableWidget):
    def __init__(self, column_name):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([column_name, 'Color'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.last_drop_row = None

    def dropMimeData(self, row, col, mimeData, action):
        self.last_drop_row = row
        return True

    def getselectedRow(self):
        for item in self.selectedItems():
            return item.row()

    def dropEvent(self, event):
        sender = event.source()
        super().dropEvent(event)
        dropRow = self.last_drop_row
        if dropRow > self.rowCount()-1:
            return

        if self != sender:
            selectedRows = sender.getselectedRowsFast()
            selectedRow = selectedRows[0]

            item = sender.item(selectedRow, 0)
            source = QTableWidgetItem(item)
            self.setItem(dropRow, 1, source)
        else:
            selectedRow = self.getselectedRow()
            source = self.item(selectedRow, 1).text()
            self.item(selectedRow, 1).setText(self.item(dropRow, 1).text())
            self.item(dropRow, 1).setText(source)
        event.accept()


class ColumnColorEditor(QDialog):
    def __init__(self, parent):
        super().__init__()

        self.table = ColorTable(parent.column_name)
        self.table.setFixedHeight(300)
        self.table.setMaximumWidth(300)
        self.table.setMaximumWidth(500)
        used_colors = []
        row = 0
        for column in parent.current_columns:
            label = parent.column_labels[column]
            color = parent.colorToName[parent.column_colors[column]]
            used_colors.append(color)
            self.table.insertRow(row)
            lab = QTableWidgetItem(label)
            col = QTableWidgetItem(color)
            self.table.setItem(row, 0, lab)
            self.table.setItem(row, 1, col)
            row += 1
        self.available_colors = TableWidgetDragRows()
        self.available_colors.setSelectionMode(QAbstractItemView.SingleSelection)
        self.available_colors.setColumnCount(1)
        self.available_colors.setHorizontalHeaderLabels(['Available colors'])
        self.available_colors.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_colors.setAcceptDrops(False)
        self.available_colors.setFixedHeight(300)
        self.available_colors.setMinimumWidth(150)
        self.available_colors.setMaximumWidth(300)
        self.available_colors.horizontalHeader().setDefaultSectionSize(150)
        row = 0
        for color in parent.defaultColors:
            color_name = parent.colorToName[color]
            self.available_colors.insertRow(row)
            col = QTableWidgetItem(color_name)
            self.available_colors.setItem(row, 0, col)
            row += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Drag and drop colors on the %ss' % parent.column_name))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.available_colors)
        hlayout.addWidget(self.table)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(500, 400)
        self.setWindowTitle('Change %s color' % parent.column_name)

    def getColors(self, old_colors, column_labels, name_to_color):
        label_to_column = {b: a for a, b, in column_labels.items()}
        for row in range(self.table.rowCount()):
            label = self.table.item(row, 0).text()
            color = self.table.item(row, 1).text()
            old_colors[label_to_column[label]] = name_to_color[color]


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


class MapCanvas(FigureCanvas):
    def __init__(self, width=10, height=10, dpi=100):
        self.BLACK = '#a9a9a9'

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)

        FigureCanvas.__init__(self, self.fig)
        self.setParent(None)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def initFigure(self, mesh):
        self.axes.clear()
        self.axes.triplot(mesh.x, mesh.y, mesh.ikle, '--', color=self.BLACK, alpha=0.5, lw=0.3)
        self.axes.set_aspect('equal', adjustable='box')
        self.draw()


class PolygonMapCanvas(MapCanvas):
    def __init__(self):
        super().__init__()
        self.PINK = '#fcabbd'

    def reinitFigure(self, mesh, polygons, polynames):
        # draw the mesh
        self.initFigure(mesh)

        # add the polygons to the map
        patches = []
        for p in polygons:
            patches.append(PolygonPatch(p.polyline().buffer(0), fc=self.PINK, ec=self.BLACK, alpha=0.5, zorder=1))
        self.axes.add_collection(PatchCollection(patches, match_original=True))

        # add polygon labels
        for p, name in zip(polygons, polynames):
            center = p.polyline().centroid
            cx, cy = center.x, center.y
            self.axes.annotate(name, (cx, cy), color='k', weight='bold',
                               fontsize=8, ha='center', va='center')
        self.draw()


class LineMapCanvas(MapCanvas):
    def __init__(self):
        super().__init__()

    def reinitFigure(self, mesh, lines, line_names, line_colors):
        # draw the mesh
        self.initFigure(mesh)

        # add polyline labels
        for p, name, color in zip(lines, line_names, line_colors):
            x, y = p.polyline().xy
            line = mlines.Line2D(x, y, color=color, lw=1)
            self.axes.add_line(line)

            center = p.polyline().centroid
            cx, cy = center.x, center.y
            self.axes.annotate(name, (cx, cy), color=color, weight='bold',
                               fontsize=8, ha='center', va='center')
        self.draw()


class ColorMapCanvas(MapCanvas):
    def __init__(self):
        super().__init__(12, 12, 110)
        self.TRANSPARENT = colorConverter.to_rgba('black', alpha=0.01)

    def reinitFigure(self, mesh, values, limits=None, polygon=None):
        self.fig.clear()   # remove the old color bar
        self.axes = self.fig.add_subplot(111)

        if limits is None:
            maxval = max(np.abs(list(values.values())))
            xmin, xmax = -maxval, maxval
        else:
            xmin, xmax = limits

        self.axes.set_aspect('equal', adjustable='box')
        self.axes.triplot(mesh.x, mesh.y, mesh.ikle, '--', color=self.BLACK, alpha=0.5, lw=0.3)

        if polygon is not None:
            # show only the zone in the polygon
            coords = list(polygon.coords())[:-1]
            x, y = list(zip(*coords))
            minx, maxx, miny, maxy = min(x), max(x), min(y), max(y)
            w, h = maxx - minx, maxy - miny
            self.axes.set_xlim(minx - 0.05 * w, maxx + 0.05 * w)
            self.axes.set_ylim(miny - 0.05 * h, maxy + 0.05 * h)

            # the color value for each triangles inside the polygon
            colors = []
            for i, j, k in mesh.triangles:
                if (i, j, k) in values:
                    colors.append(values[i, j, k])
                else:
                    colors.append(0)
            colors = np.array(colors)
        else:
            colors = np.array([values[i, j, k] for i, j, k in mesh.triangles])

        self.axes.tripcolor(mesh.x, mesh.y, mesh.ikle, facecolors=colors,
                            cmap='coolwarm', vmin=xmin, vmax=xmax,
                            norm=Normalize(xmin, xmax))

        if polygon is not None:  # add the contour of the polygon
            patches = [PolygonPatch(polygon.polyline().buffer(0), fc=self.TRANSPARENT, ec='black', zorder=1)]
            self.axes.add_collection(PatchCollection(patches, match_original=True))

        # add colorbar
        divider = make_axes_locatable(self.axes)
        cax = divider.append_axes('right', size='5%', pad=0.2)
        cmap = cm.ScalarMappable(cmap='coolwarm', norm=Normalize(xmin, xmax))
        cmap.set_array(np.linspace(xmin, xmax, 1000))
        self.fig.colorbar(cmap, cax=cax)

        self.draw()


class MapViewer(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas

        # add the the tool bar
        self.toolBar = NavigationToolbar2QT(self.canvas, self)
        self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.canvas)

        self._setLayout()
        self.resize(800, 700)

    def _setLayout(self):
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.toolBar)
        vlayout.addWidget(self.scrollArea)
        vlayout.setSpacing(0)
        vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vlayout)

        self.setWindowTitle('Map Viewer')
        self.resize(self.sizeHint())


class PlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self._initWidgets()
        self._setLayout()

    def _initWidgets(self):
        self.canvas = PlotCanvas(self)
        self.current_xlabel = 'X'
        self.current_ylabel = 'Y'
        self.current_title = 'Default plot'

        # add a default plot
        self.defaultPlot()

        # add the menu bar, the tool bar and the status bar
        self.menuBar = QMenuBar()
        self.toolBar = QToolBar()
        self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.canvas)

        self.statusbar = QStatusBar()

        self.createActions()
        self.createMenus()
        self.createTools()

    def _setLayout(self):
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.menuBar)
        vlayout.addWidget(self.toolBar)
        vlayout.addWidget(self.scrollArea)
        vlayout.addWidget(self.statusbar)
        vlayout.setSpacing(0)
        vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vlayout)

        self.setWindowTitle('Plot Viewer')
        self.resize(self.sizeHint())

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
        x = [0]
        y = [0]
        self.current_xlabel = 'X'
        self.current_ylabel = 'Y'
        self.current_title = 'Default plot'
        self.plot(x, y)

    def mouseMove(self, event):
        if event.xdata is None or event.ydata is None:
            self.statusbar.clearMessage()
        msg = 'Time: %s \t Value: %s' % (str(event.xdata), str(event.ydata))
        self.statusbar.showMessage(msg)

    def plot(self, x, y):
        """!
        Default plotting behaviour
        """
        self.canvas.axes.clear()
        self.canvas.axes.plot(x, y, 'b-', linewidth=2)
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        self.canvas.draw()


class TemporalPlotViewer(PlotViewer):
    def __init__(self, column_name='Column'):
        super().__init__()
        self.data = None
        self.columns = []
        self.setMinimumWidth(600)
        self.canvas.figure.canvas.mpl_connect('motion_notify_event', self.mouseMove)
        self.column_name = column_name

        # initialize graphical parameters
        self.time = []
        self.current_columns = []
        self.column_labels = {}
        self.column_colors = {}
        self.start_time = None
        self.datetime = []
        self.str_datetime = []
        self.str_datetime_bis = []
        self.defaultColors = ['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']
        name = ['Blue', 'Red', 'Green', 'Yellow', 'Black', 'Cyan', 'Pink', 'Magenta']
        self.colorToName = {c: n for c, n in zip(self.defaultColors, name)}
        self.nameToColor = {n: c for c, n in zip(self.defaultColors, name)}
        self.timeFormat = 0   # 0: second, 1: date, 2: date (alternative), 3: minutes, 4: hours, 5: days


        self.selectColumnsAct = QAction('Select\n%s' % self.column_name,
                                        self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.selectColumns)
        self.editColumnNamesAct = QAction('Edit %s\nlabels' % self.column_name, self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                          triggered=self.editColumns)
        self.editColumColorAct = QAction('Edit %s\ncolors' % self.column_name, self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                         triggered=self.editColor)
        self.convertTimeAct = QAction('Toggle date/time\nformat', self, checkable=True,
                                      icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.changeDateAct = QAction('Edit\nstart date', self, triggered=self.changeDate,
                                     icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.convertTimeAct.toggled.connect(self.convertTime)

        self.timeMenu = QMenu('&Date/&Time', self)
        self.timeMenu.addAction(self.convertTimeAct)
        self.timeMenu.addAction(self.changeDateAct)
        self.menuBar.addMenu(self.timeMenu)

    def _defaultXLabel(self, language):
        if language == 'fr':
            return 'Temps ({})'.format(['seconde', '', '', 'minute', 'heure', 'jour'][self.timeFormat])
        return 'Time ({})'.format(['second', '', '', 'minute', 'hour', 'day'][self.timeFormat])

    def selectColumns(self):
        msg = PlotColumnsSelector(self.columns, self.current_columns, self.column_name)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        self.current_columns = msg.selection
        self.replot()

    def editColumns(self):
        msg = ColumnLabelEditor(self.column_labels, self.current_columns, self.column_name)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLabels(self.column_labels)
        self.replot()

    def editColor(self):
        msg = ColumnColorEditor(self)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.column_colors, self.column_labels, self.nameToColor)
        self.replot()

    def replot(self):
        pass

    def reset(self):
        # reinitialize old graphical parameters and clear data
        self.time = []
        self.timeFormat = 0
        self.current_title = ''
        self.column_labels = {}
        self.column_colors = {}

    def mouseMove(self, event):
        current_time = event.xdata
        if current_time is None:
            self.statusbar.clearMessage()
            return
        if self.timeFormat == 1:
            current_time = self.start_time + datetime.timedelta(seconds=current_time)
            current_time = current_time.strftime('%Y/%m/%d %H:%M')
        elif self.timeFormat == 2:
            current_time = self.start_time + datetime.timedelta(seconds=current_time)
            current_time = current_time.strftime('%d/%m/%y %H:%M')
        elif self.timeFormat == 3:
            current_time /= 60
        elif self.timeFormat == 4:
            current_time /= 3600
        elif self.timeFormat == 5:
            current_time /= 86400
        current_time = str(current_time)
        msg = 'Time: %s \t Value: %s' % (current_time, str(event.ydata))
        self.statusbar.showMessage(msg)

    def changeDate(self):
        value, ok = QInputDialog.getText(self, 'Change start date',
                                         'Enter the start date',
                                         text=self.start_time.strftime('%Y-%m-%d %X'))
        if not ok:
            return
        try:
            self.start_time = datetime.datetime.strptime(value, '%Y-%m-%d %X')
        except ValueError:
            QMessageBox.critical(self, 'Error', 'Invalid input.',
                                 QMessageBox.Ok)
            return
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))
        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))
        self.replot()

    def convertTime(self):
        self.timeFormat = (1 + self.timeFormat) % 6
        self.current_xlabel = self._defaultXLabel(self.input.language)
        self.xLabelAct.setEnabled(self.timeFormat not in [1, 2])
        self.replot()


def handleOverwrite(filename):
    """!
    @brief Handle manually the overwrite option when saving output file
    """
    if os.path.exists(filename):
        msg = QMessageBox.warning(None, 'Confirm overwrite',
                                  'The file already exists. Do you want to replace it?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return None
        try:
            with open(filename, 'w') as f:
                pass
        except PermissionError:
            QMessageBox.critical(None, 'Permission denied',
                                 'Permission denied. (Is the file opened by another application?).',
                                 QMessageBox.Ok, QMessageBox.Ok)
            return None
        return True
    return False


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
    widget = PlotViewer()
    widget.show()
    sys.exit(app.exec_())