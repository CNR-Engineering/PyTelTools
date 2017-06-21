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

from slf.volume import TruncatedTriangularPrisms
from slf.flux import TriangularVectorField
from slf.comparison import ReferenceMesh
from slf.interpolation import MeshInterpolator
import slf.misc as operations


class TimeSlider(QSlider):
    """!
    @brief A slider for choosing the time frame.
    """
    def __init__(self, display):
        super().__init__()
        self.display = display

        self.setOrientation(Qt.Horizontal)
        self.setMaximumWidth(800)

        self.start_time = None
        self.time_frames = None
        self.nb_frames = 1000

        self.setMinimum(0)
        self.setMaximum(self.nb_frames-1)
        self._value = 0
        self.setTickPosition(QSlider.TicksBelow)

        self.pressed_control = QStyle.SC_None
        self.hover_control = QStyle.SC_None
        self.click_offset = 0

    def reinit(self, nb_frames, init_value):
        self.nb_frames = nb_frames
        self.setMinimum(0)
        self.setMaximum(self.nb_frames-1)
        self._value = init_value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        style = QApplication.style()

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        opt.subControls = QStyle.SC_SliderHandle

        if self.tickPosition() != self.NoTicks:
            opt.subControls |= QStyle.SC_SliderTickmarks

        if self.pressed_control:
            opt.activeSubControls = self.pressed_control
            opt.state |= QStyle.State_Sunken
        else:
            opt.activeSubControls = self.hover_control

        opt.sliderPosition = self.value()
        opt.sliderValue = self.value()
        style.drawComplexControl(QStyle.CC_Slider, opt, painter, self)

    def mousePressEvent(self, event):
        event.accept()
        style = QApplication.style()
        button = event.button()
        if button:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)

            opt.sliderPosition = self.value()
            hit = style.hitTestComplexControl(style.CC_Slider, opt, event.pos(), self)
            if hit == style.SC_SliderHandle:
                self.pressed_control = hit
                self.triggerAction(self.SliderMove)
                self.setRepeatAction(self.SliderNoAction)
                self.setSliderDown(True)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self.pressed_control != QStyle.SC_SliderHandle:
            event.ignore()
            return

        event.accept()
        new_pos = self.__pixelPosToRangeValue(self.__pick(event.pos()))
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        self._value = new_pos
        self.click_offset = new_pos

        # update the tip
        pos = self.mapToGlobal(event.pos())
        QToolTip.showText(pos, str(self.display.dates[self.value()]), self)

        self.update()

    def mouseReleaseEvent(self, event):
        self.display.index.setText(str(1 + self.value()))
        self.display.updateSelection()

    def __pick(self, pt):
        return pt.x()

    def __pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = QApplication.style()

        gr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderGroove, self)
        sr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderHandle, self)

        slider_length = sr.width()
        slider_min = gr.x()
        slider_max = gr.right() - slider_length + 1

        return style.sliderValueFromPosition(self.minimum(), self.maximum(),
                                             pos-slider_min, slider_max-slider_min,
                                             opt.upsideDown)

    def enterIndexEvent(self):
        try:
            value = int(self.display.index.text())
        except ValueError:
            self.display.index.setText(str(self.value()+1))
            return
        if value <= 0 or value > self.nb_frames:
            self.display.index.setText(str(self.value()+1))
            return
        self.setValue(value-1)
        self.display.updateSelection()


class TimeSliderIndexOnly(TimeSlider):
    def __init__(self, display):
        super().__init__(display)

    def __pick(self, pt):
        return pt.x()

    def __pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = QApplication.style()

        gr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderGroove, self)
        sr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderHandle, self)

        slider_length = sr.width()
        slider_min = gr.x()
        slider_max = gr.right() - slider_length + 1

        return style.sliderValueFromPosition(self.minimum(), self.maximum(),
                                             pos-slider_min, slider_max-slider_min,
                                             opt.upsideDown)

    def mouseMoveEvent(self, event):
        if self.pressed_control != QStyle.SC_SliderHandle:
            event.ignore()
            return

        event.accept()
        new_pos = self.__pixelPosToRangeValue(self.__pick(event.pos()))
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        self._value = new_pos
        self.click_offset = new_pos

        # update the tip
        pos = self.mapToGlobal(event.pos())
        QToolTip.showText(pos, str(1 + self.value()), self)

        self.update()

    def mouseReleaseEvent(self, event):
        self.display.setText(str(1 + self.value()))

    def enterIndexEvent(self):
        try:
            value = int(self.display.text())
        except ValueError:
            self.display.index.setText(str(self.value()+1))
            return
        if value <= 0 or value > self.nb_frames:
            self.display.index.setText(str(self.value()+1))
            return
        self.setValue(value-1)


class SimpleTimeDateSelection(QWidget):
    def __init__(self):
        super().__init__()

        self.frames = []
        self.dates = []

        self.index = QLineEdit('', self)
        self.slider = TimeSlider(self)
        self.value = QLineEdit('', self)
        self.date = QLineEdit('', self)

        self.value.setReadOnly(True)
        self.date.setReadOnly(True)

        self.index.setMaximumWidth(30)
        self.value.setMaximumWidth(80)
        self.date.setMaximumWidth(120)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.slider)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Frame index'))
        hlayout.addWidget(self.index)
        hlayout.addWidget(QLabel('value'))
        hlayout.addWidget(self.value)
        hlayout.addWidget(QLabel('date'))
        hlayout.addWidget(self.date)
        hlayout.addStretch()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        self.setLayout(mainLayout)
        self.index.editingFinished.connect(self.slider.enterIndexEvent)

    def updateSelection(self):
        index = int(self.index.text()) - 1
        self.value.setText(str(self.frames[index]))
        self.date.setText(str(self.dates[index]))

    def initTime(self, frames, dates):
        self.frames = frames
        self.dates = dates
        self.slider.reinit(len(frames), 0)
        self.index.setText(str(1))
        self.updateSelection()

    def clearText(self):
        self.index.clear()
        self.value.clear()
        self.date.clear()


class TimeRangeSlider(QSlider):
    """!
    @brief A slider for ranges.
        This class provides a dual-slider for ranges, where there is a defined
        maximum and minimum, as is a normal slider, but instead of having a
        single slider value, there are 2 slider values.
    """
    def __init__(self):
        super().__init__()
        self.setOrientation(Qt.Horizontal)

        self.start_time = None
        self.time_frames = None
        self.nb_frames = 1000

        self.setMinimum(0)
        self.setMaximum(self.nb_frames-1)
        self._low = 0
        self._high = self.nb_frames-1
        self.setTickPosition(QSlider.TicksBelow)

        self.pressed_control = QStyle.SC_None
        self.hover_control = QStyle.SC_None
        self.click_offset = 0

        # 0 for the low, 1 for the high, -1 for both
        self.active_slider = 0

        self.info = None

    def reinit(self, start_time, time_frames, info_text):
        self.start_time = start_time
        self.time_frames = time_frames
        self.nb_frames = len(time_frames)
        self.setMinimum(0)
        self.setMaximum(self.nb_frames-1)
        self._low = 0
        self._high = self.nb_frames-1
        self.click_offset = 0
        self.info = info_text
        self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                             self._high, self.time_frames[self._high].total_seconds(), self.high())

    def low(self):
        return self.start_time + self.time_frames[self._low]

    def setLow(self, low):
        self._low = low
        self.update()

    def high(self):
        return self.start_time + self.time_frames[self._high]

    def setHigh(self, high):
        self._high = high
        self.update()

    def paintEvent(self, event):
        # based on http://qt.gitorious.org/qt/qt/blobs/master/src/gui/widgets/qslider.cpp

        painter = QPainter(self)
        style = QApplication.style()

        for i, position in enumerate([self._low, self._high]):
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)

            # Only draw the groove for the first slider so it doesn't get drawn
            # on top of the existing ones every time
            if i == 0:
                opt.subControls = QStyle.SC_SliderHandle
            else:
                opt.subControls = QStyle.SC_SliderHandle

            if self.tickPosition() != self.NoTicks:
                opt.subControls |= QStyle.SC_SliderTickmarks

            if self.pressed_control:
                opt.activeSubControls = self.pressed_control
                opt.state |= QStyle.State_Sunken
            else:
                opt.activeSubControls = self.hover_control

            opt.sliderPosition = position
            opt.sliderValue = position
            style.drawComplexControl(QStyle.CC_Slider, opt, painter, self)

    def mousePressEvent(self, event):
        event.accept()

        style = QApplication.style()
        button = event.button()

        # In a normal slider control, when the user clicks on a point in the
        # slider's total range, but not on the slider part of the control the
        # control would jump the slider value to where the user clicked.
        # For this control, clicks which are not direct hits will slide both
        # slider parts

        if button:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)

            self.active_slider = -1

            for i, value in enumerate([self._low, self._high]):
                opt.sliderPosition = value
                hit = style.hitTestComplexControl(style.CC_Slider, opt, event.pos(), self)
                if hit == style.SC_SliderHandle:
                    self.active_slider = i
                    self.pressed_control = hit

                    self.triggerAction(self.SliderMove)
                    self.setRepeatAction(self.SliderNoAction)
                    self.setSliderDown(True)
                    break

            if self.active_slider < 0:
                self.pressed_control = QStyle.SC_SliderHandle
                self.click_offset = self.__pixelPosToRangeValue(self.__pick(event.pos()))
                self.triggerAction(self.SliderMove)
                self.setRepeatAction(self.SliderNoAction)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self.pressed_control != QStyle.SC_SliderHandle:
            event.ignore()
            return

        event.accept()
        new_pos = self.__pixelPosToRangeValue(self.__pick(event.pos()))
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        if self.active_slider < 0:
            offset = new_pos - self.click_offset
            self._high += offset
            self._low += offset
            if self._low < self.minimum():
                diff = self.minimum() - self._low
                self._low += diff
                self._high += diff
            if self._high > self.maximum():
                diff = self.maximum() - self._high
                self._low += diff
                self._high += diff
        elif self.active_slider == 0:
            if new_pos >= self._high:
                new_pos = self._high
            self._low = new_pos
        else:
            if new_pos <= self._low:
                new_pos = self._low
            self._high = new_pos

        self.click_offset = new_pos

         # update the tip
        if self.active_slider == 0:
            pos_low = self.mapToGlobal(event.pos())
            QToolTip.showText(pos_low, str(self.low()), self)
        elif self.active_slider == 1:
            pos_high = self.mapToGlobal(event.pos())

            QToolTip.showText(pos_high, str(self.high()), self)

        self.update()

    def mouseReleaseEvent(self, event):
        self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                             self._high, self.time_frames[self._high].total_seconds(), self.high())

    def __pick(self, pt):
        return pt.x()

    def __pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = QApplication.style()

        gr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderGroove, self)
        sr = style.subControlRect(style.CC_Slider, opt, style.SC_SliderHandle, self)

        slider_length = sr.width()
        slider_min = gr.x()
        slider_max = gr.right() - slider_length + 1

        return style.sliderValueFromPosition(self.minimum(), self.maximum(),
                                             pos-slider_min, slider_max-slider_min,
                                             opt.upsideDown)

    def enterIndexEvent(self):
        try:
            start_index = int(self.info.startIndex.text())
            end_index = int(self.info.endIndex.text())
        except ValueError:
            self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                                 self._high, self.time_frames[self._high].total_seconds(), self.high())
            return
        if start_index <= 0 or end_index > self.nb_frames or start_index > end_index:
            self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                                 self._high, self.time_frames[self._high].total_seconds(), self.high())
            return
        self.setLow(start_index-1)
        self.setHigh(end_index-1)
        self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                             self._high, self.time_frames[self._high].total_seconds(), self.high())

    def enterValueEvent(self):
        try:
            start_value = float(self.info.startValue.text())
            end_value = float(self.info.endValue.text())
            start_index = self.info.parent.input.time.index(start_value) + 1
            end_index = self.info.parent.input.time.index(end_value) + 1
        except ValueError:
            self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                                 self._high, self.time_frames[self._high].total_seconds(), self.high())
            return
        if start_index <= 0 or end_index > self.nb_frames or start_index > end_index:
            self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                                 self._high, self.time_frames[self._high].total_seconds(), self.high())
            return
        self.setLow(start_index-1)
        self.setHigh(end_index-1)
        self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                             self._high, self.time_frames[self._high].total_seconds(), self.high())


class DoubleSliderBox(QWidget):
    """!
    @brief Text fields for time selection display (with slider)
    """
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.visited = False  # avoid redundant text display at initialization

        self.startIndex = QLineEdit('', self)
        self.endIndex = QLineEdit('', self)
        self.startValue = QLineEdit('', self)
        self.endValue = QLineEdit('', self)
        self.startDate = QLineEdit('', self)
        self.endDate = QLineEdit('', self)
        for w in [self.startDate, self.endDate]:
            w.setReadOnly(True)

        self.startIndex.setMinimumWidth(30)
        self.startIndex.setMaximumWidth(50)
        self.endIndex.setMinimumWidth(30)
        self.endIndex.setMaximumWidth(50)
        self.startValue.setMaximumWidth(100)
        self.endValue.setMaximumWidth(100)
        self.startDate.setMinimumWidth(110)
        self.endDate.setMinimumWidth(110)

        self.timeSamplig = QLineEdit('1', self)
        self.timeSamplig.setMinimumWidth(30)
        self.timeSamplig.setMaximumWidth(50)

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Sampling frequency'), 1, 1)
        glayout.addWidget(self.timeSamplig, 1, 2)
        glayout.addWidget(QLabel('Start time index'), 2, 1)
        glayout.addWidget(self.startIndex, 2, 2)
        glayout.addWidget(QLabel('value'), 2, 3)
        glayout.addWidget(self.startValue, 2, 4)
        glayout.addWidget(QLabel('date'), 2, 5)
        glayout.addWidget(self.startDate, 2, 6)

        glayout.addWidget(QLabel('End time index'), 3, 1)
        glayout.addWidget(self.endIndex, 3, 2)
        glayout.addWidget(QLabel('value'), 3, 3)
        glayout.addWidget(self.endValue, 3, 4)
        glayout.addWidget(QLabel('date'), 3, 5)
        glayout.addWidget(self.endDate, 3, 6)

        self.setLayout(glayout)

    def updateText(self, start_index, start_value, start_date, end_index, end_value, end_date):
        self.startIndex.setText(str(start_index+1))
        self.endIndex.setText((str(end_index+1)))
        self.startValue.setText(str(start_value))
        self.endValue.setText(str(end_value))
        self.startDate.setText(str(start_date))
        self.endDate.setText(str(end_date))

    def clearText(self):
        for w in [self.startIndex, self.endIndex, self.startValue, self.endValue]:
            w.clear()
        for w in [self.startDate, self.endDate]:
            w.clear()
            self.visited = False
        self.timeSamplig.setText('1')


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


class TableWidgetDropRows(QTableWidget):
    def __init__(self):
        super().__init__()
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


class OutputThread(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self):
        super().__init__()
        self.canceled = False


class OutputProgressDialog(QProgressDialog):
    def __init__(self, message='Output in progress', title='Writing the output...', parent=None):
        super().__init__(message, 'OK', 0, 100, parent)
        self.setMinimumDuration(0)

        self.cancelButton = QPushButton('Cancel')
        self.setCancelButton(self.cancelButton)
        self.canceled.connect(self.cancel)

        self.setAutoReset(False)
        self.setAutoClose(False)

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setFixedSize(300, 150)
        self.thread = None

        self.open()
        self.setValue(0)
        QApplication.processEvents()

    def outputFinished(self):
        self.setValue(100)
        self.setCancelButtonText('OK')
        logging.info('Finished writing the output.')

    def connectToThread(self, thread):
        self.thread = thread
        thread.tick.connect(self.setValue)

    def cancel(self):
        if self.cancelButton.text() == 'Cancel':
            if not self.thread.canceled:
                self.thread.canceled = True
                logging.info('Output canceled.')


class ConstructIndexThread(OutputThread):
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
        logging.info('Processing the mesh')
        # emit a signal for every five percent of triangles processed
        five_percent = 0.05 * self.mesh.nb_triangles
        nb_processed = 0
        current_percent = 0

        for i, j, k in self.mesh.ikle:
            if self.canceled:
                return

            t = shapely.geometry.Polygon([self.mesh.points[i], self.mesh.points[j], self.mesh.points[k]])
            self.mesh.triangles[i, j, k] = t
            self.mesh.index.insert(i, t.bounds, obj=(i, j, k))

            nb_processed += 1
            if nb_processed > five_percent:
                nb_processed = 0
                current_percent += 5
                self.tick.emit(current_percent)
                QApplication.processEvents()


class LoadMeshDialog(OutputProgressDialog):
    def __init__(self, mesh_type, input_header):
        super().__init__('Processing the mesh. Please wait.', 'Processing the mesh...')
        thread = ConstructIndexThread(mesh_type, input_header)
        self.connectToThread(thread)

    def outputFinished(self):
        self.setValue(100)
        self.setCancelButtonText('OK')
        logging.info('Finished processing the mesh')

    def cancel(self):
        if self.cancelButton.text() == 'Cancel':
            if not self.thread.canceled:
                self.thread.canceled = True
                logging.info('Input canceled.')

    def run(self):
        self.thread.run()
        if not self.thread.canceled:
            self.outputFinished()
        self.exec_()
        return self.thread.mesh


class FrictionLawMessage(QDialog):
    """!
    @brief Message dialog for choosing one of the friction laws
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.chezy = QRadioButton('Chézy')
        self.chezy.setChecked(True)
        self.strickler = QRadioButton('Strickler')
        self.manning = QRadioButton('Manning')
        self.nikuradse = QRadioButton('Nikuradse')
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.chezy)
        hlayout.addWidget(self.strickler)
        hlayout.addWidget(self.manning)
        hlayout.addWidget(self.nikuradse)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.resize(self.sizeHint())
        self.setWindowTitle('Select a friction law')

    def getChoice(self):
        if self.chezy.isChecked():
            return 0
        elif self.strickler.isChecked():
            return 1
        elif self.manning.isChecked():
            return 2
        elif self.nikuradse.isChecked():
            return 3
        return -1


class FallVelocityMessage(QDialog):
    """!
    @brief Message dialog for adding fall velocities
    """
    def __init__(self, old_velocities, old_table=None, parent=None):
        super().__init__(parent)
        self.values = old_velocities[:]
        self.names = []

        self.table = TableWidgetDragRows(self)
        self.table.setDragEnabled(False)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
        vh = self.table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(50)

        if old_table is not None:
            for i in range(len(old_table)):
                nb_row = self.table.rowCount()
                self.table.insertRow(nb_row)
                for j in range(3):
                    item = QTableWidgetItem(old_table[i][j])
                    self.table.setItem(nb_row, j, item)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        self.buttonAdd = QPushButton('Add a fall velocity', self)
        self.buttonAdd.clicked.connect(self.btnAddEvent)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Double click on the cells to edit name'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(self.buttonAdd)
        vlayout.addItem(QSpacerItem(10, 20))
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(350, 400)
        self.setWindowTitle('Add fall velocities')

    def check_name_length(self):
        for name in self.names:
            if len(name) < 2 or len(name) > 16:
                return False
        return True

    def check(self):
        if self.table.rowCount() == 0:
            return
        self.names = []
        for i in range(self.table.rowCount()):
            self.names.append(self.table.item(i, 1).text())

        if not self.check_name_length():
            QMessageBox.critical(self, 'Error', 'The variable names should be between 2 and 16 characters!',
                                 QMessageBox.Ok)
            return
        elif len(set(self.names)) != len(self.names):
            QMessageBox.critical(self, 'Error', 'Two variables cannot share the same name!',
                                 QMessageBox.Ok)
            return
        else:
            self.accept()

    def get_table(self):
        return [[self.table.item(i, j).text() for j in range(3)] for i in range(self.table.rowCount())]

    def btnAddEvent(self):
        value, ok = QInputDialog.getText(self, 'New value',
                                         'Fall velocity value (up to 5 significant figures):', text='1e-5')
        if not ok:
            return
        try:
            value = float(value)
        except ValueError:
            QMessageBox.critical(self, 'Error', 'You must enter a number!',
                             QMessageBox.Ok)
            return
        if value in self.values:
            QMessageBox.critical(self, 'Error', 'The value %.4E is already added!' % value,
                                 QMessageBox.Ok)
            return
        self.values.append(value)
        value_ID = 'ROUSE %.4E' % value
        nb_row = self.table.rowCount()
        self.table.insertRow(nb_row)
        id_item = QTableWidgetItem(value_ID)
        id_item.setFlags(Qt.ItemIsEditable)
        name_item = QTableWidgetItem(value_ID)
        unit_item = QTableWidgetItem('')
        unit_item.setFlags(Qt.ItemIsEditable)
        self.table.setItem(nb_row, 0, id_item)
        self.table.setItem(nb_row, 1, name_item)
        self.table.setItem(nb_row, 2, unit_item)


class ConditionDialog(QDialog):
    def __init__(self, var_IDs, var_names):
        super().__init__()
        self.var_IDs = var_IDs

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkCondition)
        buttons.rejected.connect(self.reject)

        self.expressionBox = QTextEdit()
        self.expressionBox.setFixedSize(150, 30)
        self.old_format = self.expressionBox.currentCharFormat()
        self.expressionBox.cursorPositionChanged.connect(lambda:
                                                         self.expressionBox.setCurrentCharFormat(self.old_format))

        self.addButton = QPushButton('Add')
        self.addButton.setFixedSize(50, 30)
        self.addButton.clicked.connect(self.addButtonEvent)

        self.clearButton = QPushButton('Clear')
        self.clearButton.setFixedSize(50, 30)
        self.clearButton.clicked.connect(self.expressionBox.clear)

        self.varBox = QComboBox()
        self.varBox.setFixedSize(150, 30)

        for var_ID, var_name in zip(var_IDs, var_names):
            var_name = var_name.decode('utf-8').strip()
            self.varBox.addItem('%s (%s)' % (var_ID, var_name))

        self.comparatorBox = QComboBox()
        for comparator in ['>', '<', '>=', '<=']:
            self.comparatorBox.addItem(comparator)
        self.comparatorBox.setFixedSize(50, 30)

        self.threashold = QLineEdit()
        self.threashold.setFixedSize(150, 30)

        self.condition = ([], '', '', 0.0)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Help</b>: use <b>Add</b> button to add variables to the expression.<br>'
                                    'You can also enter operators, parentheses and numbers.<br>'
                                    'Supported operators: <tt>+ - * / ^ sqrt</tt>.'))

        mainLayout.addItem(QSpacerItem(50, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Edit expression'))
        hlayout.addWidget(self.clearButton)
        hlayout.addWidget(self.addButton)
        hlayout.addWidget(self.varBox)
        hlayout.setSpacing(10)
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        mainLayout.setAlignment(hlayout, Qt.AlignHCenter)
        mainLayout.addItem(QSpacerItem(50, 20))
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Expression'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Comparator'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Threshold'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.expressionBox, 2, 1)
        glayout.addWidget(self.comparatorBox, 2, 2)
        glayout.addWidget(self.threashold, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Add new condition')
        self.resize(self.sizeHint())

    def _processExpression(self, expression):
        infix = operations.to_infix(expression)
        return operations.infix_to_postfix(infix)

    def _validateExpression(self, expression):
        for item in expression:
            if item[0] == '[':  # variable ID
                if item[1:-1] not in self.var_IDs:
                    return False
            elif item in operations.OPERATORS:
                continue
            else:  # is number
                try:
                    _ = float(item)
                except ValueError:
                    return False
        return operations.is_valid_postfix(expression)

    def addButtonEvent(self):
        var_ID = self.varBox.currentText().split(' (')[0]
        self.expressionBox.insertHtml("<span style=\" font-size:8pt; "
                                      "font-weight:600; color:#554DF7;\" "
                                      ">[%s]</span>" % var_ID)
        self.expressionBox.setCurrentCharFormat(self.old_format)

    def checkCondition(self):
        literal_expression = self.expressionBox.toPlainText()
        comparator = self.comparatorBox.currentText()
        threshold = self.threashold.text()
        self.condition = ([], '', '', 0.0)

        try:
            threshold = float(threshold)
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The threshold is not a number!',
                                 QMessageBox.Ok)
            return
        expression = self._processExpression(literal_expression)

        if not self._validateExpression(expression):
            QMessageBox.critical(self, 'Error', 'Invalid expression.',
                                 QMessageBox.Ok)
            return
        self.condition = operations.Condition(expression, literal_expression, comparator, threshold)
        self.accept()


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
        vlayout.addWidget(QLabel('  Select up to 10 %s to plot' % self.plural))
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
        if len(self.selection) > 10:
            QMessageBox.critical(self, 'Error', 'Select up to 10 %s.' % self.plural,
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


class HTMLDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        style = QApplication.style() if options.widget is None else options.widget.style()

        doc = QTextDocument()
        doc.setHtml(options.text)

        options.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options,index)

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())
        return QSize(doc.idealWidth(), doc.size().height())


class SelectedColorTable(TableWidgetDropRows):
    def __init__(self, column_name, current_columns, column_labels, column_colors, color_to_name):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([column_name, 'Color'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        delegate = HTMLDelegate()

        self.setFixedHeight(300)
        self.setMaximumWidth(300)
        row = 0
        for column in current_columns:
            label = column_labels[column]
            color = column_colors[column]
            color_name = color_to_name[color]
            color_display = "<span style=\"color:%s;\">%s</span> " % (color, u"\u2B1B")
            self.insertRow(row)
            lab = QTableWidgetItem(label)
            col = QTableWidgetItem(color_display + color_name)
            self.setItem(row, 0, lab)
            self.setItem(row, 1, col)
            row += 1
        self.setItemDelegateForColumn(1, delegate)


class AvailableColorTable(TableWidgetDragRows):
    def __init__(self, colors, color_to_name):
        super().__init__()
        delegate = HTMLDelegate()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['Available colors'])
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(False)
        self.setFixedHeight(300)
        self.setMinimumWidth(150)
        self.setMaximumWidth(300)
        self.horizontalHeader().setDefaultSectionSize(150)
        row = 0
        for color in colors:
            color_name = color_to_name[color]
            color_display = "<span style=\"color:%s;\">%s</span> " % (color, u"\u2B1B")
            self.insertRow(row)
            col = QTableWidgetItem(color_display + color_name)
            self.setItem(row, 0, col)
            row += 1
        self.setItemDelegateForColumn(0, delegate)


class ColumnColorEditor(QDialog):
    def __init__(self, column_name, current_columns, column_labels, column_colors,
                 all_colors, color_to_name):
        super().__init__()
        self.table = SelectedColorTable(column_name, current_columns, column_labels, column_colors, color_to_name)
        self.available_colors = AvailableColorTable(all_colors, color_to_name)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Drag and drop colors on the %ss' % column_name))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.available_colors)
        hlayout.addWidget(self.table)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(500, 400)
        self.setWindowTitle('Change %s color' % column_name)

    def getColors(self, old_colors, column_labels, name_to_color):
        label_to_column = {b: a for a, b, in column_labels.items()}
        for row in range(self.table.rowCount()):
            label = self.table.item(row, 0).text()
            color = self.table.item(row, 1).text().split('> ')[1]
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
        self.defaultColors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2',
                              '#7f7f7f', '#bcbd22', '#17becf']
        name = ['Blue', 'Orange', 'Green', 'Red', 'Purple', 'Brown', 'Pink', 'DarkGray', 'Yellow', 'Cyan']
        self.colorToName = {c: n for c, n in zip(self.defaultColors, name)}
        self.nameToColor = {n: c for c, n in zip(self.defaultColors, name)}

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
        msg = ColumnColorEditor(self.column_name, self.current_columns, self.column_labels, self.column_colors,
                                self.defaultColors, self.colorToName)
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


class TelToolWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setMinimumWidth(600)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)

    def inDialog(self):
        if self.parent is not None:
            self.parent.inDialog()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
            self.setEnabled(False)
            self.show()

    def outDialog(self):
        if self.parent is not None:
            self.parent.outDialog()
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
            self.setEnabled(True)
            self.show()


def testOpen(filename):
    try:
        with open(filename, 'rb') as f:
            pass
    except PermissionError:
        QMessageBox.critical(None, 'Permission denied',
                             'Permission denied. (Is the file opened by another application?).',
                             QMessageBox.Ok, QMessageBox.Ok)
        return False
    return True


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
                                 'Permission denied (Is the file opened by another application?).',
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