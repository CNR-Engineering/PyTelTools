import datetime
import logging
import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import shapely
import struct
import os

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.collections import PatchCollection
from descartes import PolygonPatch
from matplotlib import cm
from matplotlib.colors import Normalize, colorConverter
import matplotlib.lines as mlines
from mpl_toolkits.axes_grid1 import make_axes_locatable

from conf.settings import CSV_SEPARATOR, DIGITS, LANG, LOGGING_LEVEL, MAP_SIZE, MAP_OUT_DPI, NB_COLOR_LEVELS, \
    SERAFIN_EXT, X_AXIS_LABEL, Y_AXIS_LABEL
from geom import BlueKenue, Shapefile
from slf.comparison import ReferenceMesh
from slf.datatypes import SerafinData
from slf.flux import TriangularVectorField
from slf.interpolation import MeshInterpolator
import slf.misc as operations
from slf import Serafin
from slf.volume import TruncatedTriangularPrisms, VolumeCalculator


def test_open(filename):
    try:
        with open(filename, 'rb') as f:
            pass
    except PermissionError:
        QMessageBox.critical(None, 'Permission denied',
                             'Permission denied. (Is the file opened by another application?).',
                             QMessageBox.Ok, QMessageBox.Ok)
        return False
    return True


def handle_overwrite(filename):
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
        try:
            os.remove(filename)
        except PermissionError:
            pass
        return True
    return False


def read_csv(filename, separator):
    data = {}
    with open(filename, 'r') as f:
        headers = f.readline().rstrip().split(separator)
        for header in headers:
            data[header] = []
        for line in f.readlines():
            items = line.rstrip().split(separator)
            for header, item in zip(headers, items):
                data[header].append(float(item))
        for header in headers:
            data[header] = np.array(data[header])
    return data, headers


def open_polygons():
    filename, _ = QFileDialog.getOpenFileName(None, 'Open a .i2s or .shp file', '', 'Line sets (*.i2s *.shp)',
                                              options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
    if not filename:
        return False, '', []
    if not test_open(filename):
        return False, '', []

    is_i2s = filename[-4:] == '.i2s'

    polygons = []
    if is_i2s:
        with BlueKenue.Read(filename) as f:
            f.read_header()
            for poly in f.get_polygons():
                polygons.append(poly)
    else:
        try:
            for polygon in Shapefile.get_polygons(filename):
                polygons.append(polygon)
        except struct.error:
            QMessageBox.critical(None, 'Error', 'Inconsistent bytes.', QMessageBox.Ok)
            return False, '', []
    if not polygons:
        QMessageBox.critical(None, 'Error', 'The file does not contain any polygon.',
                             QMessageBox.Ok)
        return False, '', []
    return True, filename, polygons


def open_polylines():
    filename, _ = QFileDialog.getOpenFileName(None, 'Open a .i2s or .shp file', '', 'Line sets (*.i2s *.shp)',
                                              options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
    if not filename:
        return False, '', []
    if not test_open(filename):
        return False, '', []

    is_i2s = filename[-4:] == '.i2s'

    polylines = []
    if is_i2s:
        with BlueKenue.Read(filename) as f:
            f.read_header()
            for polyline in f.get_open_polylines():
                polylines.append(polyline)
    else:
        try:
            for polyline in Shapefile.get_open_polylines(filename):
                polylines.append(polyline)
        except struct.error:
            QMessageBox.critical(None, 'Error', 'Inconsistent bytes.', QMessageBox.Ok)
            return False, '', []
    if not polylines:
        QMessageBox.critical(None, 'Error', 'The file does not contain any open polyline.',
                             QMessageBox.Ok)
        return False, '', []
    return True, filename, polylines


def open_points():
    filename, _ = QFileDialog.getOpenFileName(None, 'Open a .shp file', '', 'Point sets (*.shp)',
                                              options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
    if not filename:
        return False, '', [], [], []
    if not test_open(filename):
        return False, '', [], [], []

    fields, indices = Shapefile.get_attribute_names(filename)
    points = []
    attributes = []
    try:
        for point, attribute in Shapefile.get_points(filename, indices):
            points.append(point)
            attributes.append(attribute)
    except struct.error:
        QMessageBox.critical(None, 'Error', 'Inconsistent bytes.', QMessageBox.Ok)
        return False, '', [], [], []

    if not points:
        QMessageBox.critical(None, 'Error', 'The file does not contain any point.',
                             QMessageBox.Ok)
        return False, '', [], [], []
    return True, filename, points, attributes, fields


def save_dialog(file_format, input_name='', input_names=None):
    # create the save file dialog
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    options |= QFileDialog.DontConfirmOverwrite
    if file_format == 'Serafin':
        extensions = SERAFIN_EXT
        file_filter = 'Serafin Files (%s)' % ' '.join(['*%s' % extension for extension in SERAFIN_EXT])
    elif file_format == 'CSV':
        extensions = ['.csv']
        file_filter = 'CSV Files (*.csv)'
    else:
        raise NotImplementedError('File format %s is not supported' % file_format)
    filename, _ = QFileDialog.getSaveFileName(None, 'Choose the output file name', '', file_filter, options=options)

    # check the file name consistency
    if not filename:
        return True, ''

    # add default extension (taken as first) if missing
    if os.path.splitext(filename)[1] not in extensions:
        filename += extensions[0]

    # overwrite to the input file is forbidden
    if input_name:
        if filename == input_name:
            QMessageBox.critical(None, 'Error', 'Cannot overwrite to the input file.', QMessageBox.Ok)
            return True, ''
    elif input_names:
        for name in input_names:
            if filename == name:
                QMessageBox.critical(None, 'Error', 'Cannot overwrite to the input file.', QMessageBox.Ok)
                return True, ''

    # handle overwrite manually
    overwrite = handle_overwrite(filename)
    if overwrite is None:
        return True, ''

    return False, filename


class SerafinInputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        # create the button open
        self.btnOpen = QPushButton('Open', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a Serafin file')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)

        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        self.englishButton = QRadioButton('English')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(self.englishButton)
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        if self.parent.language == 'fr':
            self.frenchButton.setChecked(True)
        else:
            self.englishButton.setChecked(True)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(self.parent.logging_level)

        self.input_layout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        self.input_layout.addLayout(hlayout)
        self.input_layout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Input file'), 1, 1)
        glayout.addWidget(self.inNameBox, 1, 2)
        glayout.addWidget(QLabel('Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        self.input_layout.addLayout(glayout)

    def current_language(self):
        if self.frenchButton.isChecked():
            return 'fr'
        return 'en'

    def reset(self):
        self.inNameBox.clear()
        self.summaryTextBox.clear()

    def open_event(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a Serafin file', '', 'Serafin Files (%s)' %
                                                  ' '.join(['*%s' % extension for extension in SERAFIN_EXT]),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return True, ''

        if not test_open(filename):
            return True, ''

        return False, filename

    def read(self, filename):
        self.inNameBox.setText(filename)
        data = SerafinData('', filename, self.current_language())
        try:
            data.read()
        except PermissionError:
            QMessageBox.critical(None, 'Permission denied',
                                 'Permission denied. (Is the file opened by another application?).',
                                 QMessageBox.Ok, QMessageBox.Ok)
            return False, None
        self.summaryTextBox.appendPlainText(data.header.summary())
        logging.info('Finished reading the input file')
        return True, data

    def read_2d(self, filename, update=True):
        if update:
            self.inNameBox.setText(filename)
        data = SerafinData('', filename, self.current_language())

        try:
            is_2d = data.read()
        except PermissionError:
            QMessageBox.critical(None, 'Permission denied',
                                 'Permission denied. (Is the file opened by another application?).',
                                 QMessageBox.Ok, QMessageBox.Ok)
            return False, None

        if not is_2d:
            QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                 QMessageBox.Ok)
            return False, None
        if update:
            self.summaryTextBox.appendPlainText(data.header.summary())
        logging.info('Finished reading the input file')
        return True, data


class TelToolWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.input = None
        if parent is None:
            self.language = LANG
            self.csv_separator = CSV_SEPARATOR
            self.digits = DIGITS
            self.logging_level = LOGGING_LEVEL
        else:
            self.language = parent.language
            self.csv_separator = parent.csv_separator
            self.digits = parent.digits
            self.logging_level = parent.logging_level
        self.setMinimumWidth(600)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

    def switch_language(self, language):
        if language == 'fr':
            self.input.frenchButton.setChecked(True)
        else:
            self.input.englishButton.setChecked(True)


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

        self.index.setMaximumWidth(50)
        self.value.setMaximumWidth(100)
        self.date.setMaximumWidth(150)

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
            start_index = self.info.parent.time.index(start_value) + 1
            end_index = self.info.parent.time.index(end_value) + 1
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


class VariableTable(TableWidgetDragRows):
    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
        vh = self.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(20)
        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(110)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setMaximumHeight(800)

    def fill(self, header):
        for i, (var_id, name, unit) in enumerate(zip(header.var_IDs, header.var_names, header.var_units)):
            self.insertRow(self.rowCount())
            id_item = QTableWidgetItem(var_id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.setItem(i, 0, id_item)
            self.setItem(i, 1, name_item)
            self.setItem(i, 2, unit_item)

    def get_selected(self):
        selected = []
        for i in range(self.rowCount()):
            selected.append(self.item(i, 0).text())
        return selected

    def get_selected_all(self):
        selected = []
        for i in range(self.rowCount()):
            selected.append((self.item(i, 0).text(),
                            bytes(self.item(i, 1).text(), 'utf-8').ljust(16),
                            bytes(self.item(i, 2).text(), 'utf-8').ljust(16)))
        return selected


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


class SettlingVelocityMessage(QDialog):
    """!
    @brief Message dialog for adding settling velocities
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

        self.buttonAdd = QPushButton('Add a settling velocity', self)
        self.buttonAdd.clicked.connect(self.btnAddEvent)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Double click on the cells to edit name'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(self.buttonAdd)
        vlayout.addItem(QSpacerItem(10, 20))
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(350, 400)
        self.setWindowTitle('Add settling velocities')

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

        self.threshold = QLineEdit()
        self.threshold.setFixedSize(150, 30)

        self.condition = ([], '', '', 0.0)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Help</b>: use <b>Add</b> button to add variables to the expression.<br>'
                                    'You can also enter operators, parentheses and numbers.<br>'
                                    'Supported operators: <tt>+ - * / ^ sqrt</tt>.</p>'))

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
        glayout.addWidget(self.threshold, 2, 3)
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
        return operations.is_valid_expression(expression, self.var_IDs) and operations.is_valid_postfix(expression)

    def addButtonEvent(self):
        var_ID = self.varBox.currentText().split(' (')[0]
        self.expressionBox.insertHtml('<span style=\" font-size:8pt; '
                                      'font-weight:600; color:#554DF7;\" '
                                      '>[%s]</span>' % var_ID)
        self.expressionBox.setCurrentCharFormat(self.old_format)

    def checkCondition(self):
        literal_expression = self.expressionBox.toPlainText()
        comparator = self.comparatorBox.currentText()
        threshold = self.threshold.text()
        self.condition = ([], '', '', 0.0)

        try:
            threshold = float(threshold)
        except ValueError:
            QMessageBox.critical(None, 'Error', 'The threshold is not a number!', QMessageBox.Ok)
            return
        expression = self._processExpression(literal_expression)

        if not self._validateExpression(expression):
            QMessageBox.critical(None, 'Error', 'Invalid expression.', QMessageBox.Ok)
            return
        self.condition = operations.Condition(expression, literal_expression, comparator, threshold)
        self.accept()


class PlotColumnsSelector(QDialog):
    def __init__(self, columns, current_columns, name, unique_selection):
        super().__init__()
        self.name = name
        self.plural = str(''.join([name, 's']))
        self.unique = unique_selection

        self.list = QListWidget()
        for name in columns:
            item = QListWidgetItem('    ' + name)
            if not self.unique:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if name in current_columns:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
            if self.unique:
                self.list.setItemWidget(item, QRadioButton())
                if name in current_columns:
                    self.list.itemWidget(item).setChecked(True)

        self.selection = tuple([])

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkSelection)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('  Select up to 10 %s to plot' % self.plural if not self.unique else
                                 '  Select a single %s to plot' % self.name))
        vlayout.addWidget(self.list)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setWindowTitle('Select %s to plot' % (self.name if self.unique else self.plural))
        self.resize(self.sizeHint())
        self.setMinimumWidth(300)

    def getSelection(self):
        selection = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if not self.unique:
                if item.checkState() == Qt.Checked:
                    selection.append(item.text().strip())
            else:
                if self.list.itemWidget(item).isChecked():
                    selection.append(item.text().strip())
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

        options.text = ''
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
            color_display = '<span style=\"color:%s;\">%s</span> ' % (color, u'\u2B1B')
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
            color_display = '<span style=\"color:%s;\">%s</span> ' % (color, u'\u2B1B')
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
    def __init__(self, width=MAP_SIZE[0], height=MAP_SIZE[1], dpi=MAP_OUT_DPI):
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
        self.axes.set_xlabel(X_AXIS_LABEL)
        self.axes.set_ylabel(Y_AXIS_LABEL)
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
        super().__init__()
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
        cmap.set_array(np.linspace(xmin, xmax, NB_COLOR_LEVELS))
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

        self.canvas = PlotCanvas(self)
        self.current_xlabel = X_AXIS_LABEL
        self.current_ylabel = Y_AXIS_LABEL
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
        self.fileMenu = QMenu('&File', self)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.editMenu = QMenu('&Edit', self)
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
        self.current_xlabel = X_AXIS_LABEL
        self.current_ylabel = Y_AXIS_LABEL
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
        self.language = 'fr'

        # initialize graphical parameters
        self.time_seconds = []
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
        self.selectColumnsAct_short = QAction('Select %s' % self.column_name,
                                              self, icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                              triggered=self.selectColumns)
        self.editColumnNamesAct_short = QAction('Edit %s labels' % self.column_name, self,
                                                icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                                triggered=self.editColumns)
        self.editColumColorAct_short = QAction('Edit %s colors' % self.column_name, self,
                                               icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                               triggered=self.editColor)

        self.convertTimeAct = QAction('Toggle date/time\nformat', self, checkable=True,
                                      icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        convertTimeAct_short = QAction('Toggle date/time format', self, checkable=True,
                                       icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.changeDateAct = QAction('Edit\nstart date', self, triggered=self.changeDate,
                                     icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        changeDateAct_short = QAction('Edit start date', self, triggered=self.changeDate,
                                      icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.convertTimeAct.toggled.connect(self.convertTime)
        convertTimeAct_short.toggled.connect(self.convertTime)

        timeMenu = QMenu('&Date/&Time', self)
        timeMenu.addAction(convertTimeAct_short)
        timeMenu.addAction(changeDateAct_short)
        self.menuBar.addMenu(timeMenu)

    def _defaultXLabel(self):
        if self.language == 'fr':
            return 'Temps ({})'.format(['seconde', '', '', 'minute', 'heure', 'jour'][self.timeFormat])
        return 'Time ({})'.format(['second', '', '', 'minute', 'hour', 'day'][self.timeFormat])

    def selectColumns(self, unique_selection=False):
        msg = PlotColumnsSelector(self.columns, self.current_columns, self.column_name, unique_selection)
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
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.time_seconds))
        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))
        self.replot()

    def convertTime(self):
        self.timeFormat = (1 + self.timeFormat) % 6
        self.current_xlabel = self._defaultXLabel()
        self.xLabelAct.setEnabled(self.timeFormat not in [1, 2])
        self.replot()


class PointAttributeTable(QTableWidget):
    def __init__(self):
        super().__init__()
        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(100)
        self.resize(850, 600)
        self.setWindowTitle('Attribute table')

    def getData(self, points, is_inside, fields, all_attributes):
        self.setRowCount(0)
        true_false = {True: 'Yes', False: 'No'}

        if is_inside:
            self.setColumnCount(3 + len(fields))
            self.setHorizontalHeaderLabels(['x', 'y', 'IsInside'] + fields)
        else:
            self.setColumnCount(2 + len(fields))
            self.setHorizontalHeaderLabels(['x', 'y'] + fields)

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        i = 0
        if is_inside:
            for (x, y), inside, attributes in zip(points, is_inside, all_attributes):
                self.insertRow(i)
                self.setItem(i, 0, QTableWidgetItem('%.4f' % x))
                self.setItem(i, 1, QTableWidgetItem('%.4f' % y))
                self.setItem(i, 2, QTableWidgetItem(true_false[inside]))
                for j, a in enumerate(attributes):
                    self.setItem(i, j+3, QTableWidgetItem(str(a)))
                i += 1
        else:
            for (x, y), attributes in zip(points, all_attributes):
                self.insertRow(i)
                self.setItem(i, 0, QTableWidgetItem('%.4f' % x))
                self.setItem(i, 1, QTableWidgetItem('%.4f' % y))
                for j, a in enumerate(attributes):
                    self.setItem(i, j+2, QTableWidgetItem(str(a)))
                i += 1


class PointAttributeDialog(QDialog):
    def __init__(self, attribute_table):
        super().__init__()
        self.attribute_table = attribute_table
        self.attribute_table.setSelectionBehavior(QAbstractItemView.SelectColumns)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.checkSelection)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.attribute_table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Select an attribute as labels')
        self.resize(850, 500)
        self.selection = []

    def checkSelection(self):
        column = self.attribute_table.currentColumn()
        if column == -1:
            QMessageBox.critical(self, 'Error', 'Select at least one attribute.',
                                 QMessageBox.Ok)
            return
        self.selection = []
        for i in range(self.attribute_table.rowCount()):
            self.selection.append(self.attribute_table.item(i, column).text())
        self.accept()


class VolumePlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('polygon')
        self.csv_separator = ''
        self.var_ID = None
        self.second_var_ID = None
        self.language = 'fr'

        self.current_columns = ('Polygon 1',)

        self.setWindowTitle('Visualize the temporal evolution of volumes')

        self.poly_menu = QMenu('&Polygons', self)
        self.poly_menu.addAction(self.selectColumnsAct_short)
        self.poly_menu.addAction(self.editColumnNamesAct_short)
        self.poly_menu.addAction(self.editColumColorAct_short)

    def _defaultYLabel(self):
        word = {'fr': 'de', 'en': 'of'}[self.language]
        if self.second_var_ID == VolumeCalculator.INIT_VALUE:
            return 'Volume %s (%s - %s$_0$)' % (word, self.var_ID, self.var_ID)
        elif self.second_var_ID is None:
            return 'Volume %s %s' % (word, self.var_ID)
        return 'Volume %s (%s - %s)' % (word, self.var_ID, self.second_var_ID)

    def replot(self):
        self.canvas.axes.clear()
        for column in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[column], '-', color=self.column_colors[column],
                                  linewidth=2, label=self.column_labels[column])
        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()


class FluxPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('section')
        self.setWindowTitle('Visualize the temporal evolution of flux')
        self.csv_separator = ''
        self.flux_title = ''
        self.var_IDs = []
        self.cumulative = False
        self.cumulative_flux_act = QAction('Show\ncumulative flux', self, checkable=True,
                                           icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.cumulative_flux_act.toggled.connect(self.changeFluxType)

        self.current_columns = ('Section 1',)
        self.poly_menu = QMenu('&Sections', self)
        self.poly_menu.addAction(self.selectColumnsAct_short)
        self.poly_menu.addAction(self.editColumnNamesAct_short)
        self.poly_menu.addAction(self.editColumColorAct_short)

    def changeFluxType(self):
        self.cumulative = not self.cumulative
        self.current_ylabel = 'Cumulative ' + self.flux_title
        self.replot()

    def replot(self):
        self.canvas.axes.clear()
        for column in self.current_columns:
            if not self.cumulative:
                self.canvas.axes.plot(self.time[self.timeFormat], self.data[column], '-',
                                      color=self.column_colors[column],
                                      linewidth=2, label=self.column_labels[column])
            else:
                self.canvas.axes.plot(self.time[self.timeFormat], np.cumsum(self.data[column]), '-',
                                      color=self.column_colors[column],
                                      linewidth=2, label=self.column_labels[column])

        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()


class PointPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.setWindowTitle('Visualize the temporal evolution of values on points')
        self.var_IDs = []
        self.current_var = ''
        self.points = None
        self.select_variable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.select_variable_short = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                             icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))

        self.current_columns = ('Point 1',)
        self.poly_menu = QMenu('&Sections', self)
        self.poly_menu.addAction(self.selectColumnsAct_short)
        self.poly_menu.addAction(self.editColumnNamesAct_short)
        self.poly_menu.addAction(self.editColumColorAct_short)

    def _to_column(self, point):
        point_index = int(point.split()[1]) - 1
        x, y = self.points.points[point_index]
        return 'Point %d %s (%.4f|%.4f)' % (point_index+1, self.current_var, x, y)

    def _defaultYLabel(self):
        word = {'fr': 'de', 'en': 'of'}[self.language]
        return 'Values %s %s' % (word, self.current_var)

    def selectVariableEvent(self):
        msg = QDialog()
        combo = QComboBox()
        for var in self.var_IDs:
            combo.addItem(var)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(combo)
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText()
        self.current_ylabel = self._defaultYLabel()
        self.replot()

    def replot(self):
        self.canvas.axes.clear()
        for point in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[self._to_column(point)], '-',
                                  color=self.column_colors[point],
                                  linewidth=2, label=self.column_labels[point])
        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()


class PointLabelEditor(QDialog):
    def __init__(self, column_labels, name, points, is_inside, fields, all_attributes):
        super().__init__()
        attribute_table = PointAttributeTable()
        attribute_table.getData(points, is_inside, fields, all_attributes)
        self.attribute_dialog = PointAttributeDialog(attribute_table)

        self.btnAttribute = QPushButton('Use attributes')
        self.btnAttribute.setFixedSize(105, 50)
        self.btnAttribute.clicked.connect(self.btnAttributeEvent)

        self.btnDefault = QPushButton('Default')
        self.btnDefault.setFixedSize(105, 50)
        self.btnDefault.clicked.connect(self.btnDefaultEvent)

        self.column_labels = column_labels
        self.table = QTableWidget()
        self.table .setColumnCount(2)
        self.table .setHorizontalHeaderLabels([name, 'Label'])
        row = 0
        for column, label in column_labels.items():
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
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnAttribute)
        hlayout.addWidget(self.btnDefault)
        hlayout.setSpacing(10)
        vlayout.addLayout(hlayout, Qt.AlignHCenter)
        vlayout.addItem(QSpacerItem(1, 15))
        vlayout.addWidget(QLabel('Click on the label to modify'))
        vlayout.addWidget(self.table)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setWindowTitle('Change %s labels' % name)
        self.resize(self.sizeHint())
        self.setMinimumWidth(300)

    def btnDefaultEvent(self):
        self.table.setRowCount(0)
        row = 0
        for column in self.column_labels.keys():
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(column)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

    def btnAttributeEvent(self):
        value = self.attribute_dialog.exec_()
        if value == QDialog.Rejected:
            return
        selected_labels = self.attribute_dialog.selection
        self.table.setRowCount(0)
        row = 0
        for column, label in zip(self.column_labels.keys(), selected_labels):
            self.table.insertRow(row)
            c = QTableWidgetItem(column)
            l = QTableWidgetItem(label)
            self.table.setItem(row, 0, c)
            self.table.setItem(row, 1, l)
            self.table.item(row, 0).setFlags(Qt.ItemIsEditable)
            row += 1

    def getLabels(self, old_labels):
        for row in range(self.table.rowCount()):
            column = self.table.item(row, 0).text()
            label = self.table.item(row, 1).text()
            old_labels[column] = label


class LineStyleEditor(QDialog):
    def __init__(self, all_linestyles, current_linestyles):
        super().__init__()
        self.table = TableWidgetDropRows()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(['Variable', 'Line style'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table.setFixedHeight(300)
        self.table.setMaximumWidth(300)
        row = 0
        for var, style in current_linestyles.items():
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(var))
            self.table.setItem(row, 1, QTableWidgetItem(style))
            row += 1

        self.available_linestyles = TableWidgetDragRows()
        self.available_linestyles.setSelectionMode(QAbstractItemView.SingleSelection)
        self.available_linestyles.setColumnCount(1)
        self.available_linestyles.setHorizontalHeaderLabels(['Available styles'])
        self.available_linestyles.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_linestyles.setAcceptDrops(False)
        self.available_linestyles.setFixedHeight(300)
        self.available_linestyles.setMinimumWidth(150)
        self.available_linestyles.setMaximumWidth(300)
        self.available_linestyles.horizontalHeader().setDefaultSectionSize(150)
        row = 0
        for style in all_linestyles:
            self.available_linestyles.insertRow(row)
            self.available_linestyles.setItem(row, 0, QTableWidgetItem(style))
            row += 1

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Drag and drop line styles on the %s variables'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.available_linestyles)
        hlayout.addWidget(self.table)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.setFixedSize(500, 400)
        self.setWindowTitle('Change variable line styles')

    def getLineStyles(self, old_linestyles):
        for row in range(self.table.rowCount()):
            label = self.table.item(row, 0).text()
            style = self.table.item(row, 1).text()
            old_linestyles[label] = style


class MultiVarControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.timeSelection = SimpleTimeDateSelection()

        # create widgets plot options
        self.lineBox = QComboBox()
        self.lineBox.setFixedHeight(30)
        self.lineBox.setMaximumWidth(200)
        self.intersection = QCheckBox('Add intersection points')
        self.intersection.setChecked(True)
        self.addInternal = QCheckBox('Mark original points in plot')

        self.unitBox = QComboBox()
        self.unitBox.setFixedHeight(30)
        self.unitBox.setMaximumWidth(200)
        self.varList = QListWidget()
        self.varList.setMaximumWidth(200)

        # create the compute button
        self.btnCompute = QPushButton('Compute', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCompute.setFixedSize(105, 50)

        # set layout
        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(self.timeSelection)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a polyline'))
        hlayout.addWidget(self.lineBox)
        hlayout.setAlignment(self.lineBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.intersection)
        hlayout.setAlignment(self.intersection, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.addInternal)
        hlayout.setAlignment(self.addInternal, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        vlayout2 = QVBoxLayout()
        vlayout2.addWidget(self.unitBox)
        vlayout2.addWidget(self.varList)
        vlayout2.setSpacing(10)
        hlayout.addLayout(vlayout2)
        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignRight | Qt.AlignTop)
        hlayout.setSpacing(10)
        vlayout.addItem(hlayout)

        self.setLayout(vlayout)


class MultiVarLinePlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.filename = ''
        self.header = None
        self.time = []
        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []

        self.var_table = {}
        self.current_vars = []
        self.var_colors = {}

        # set up a custom plot viewer
        self.editVarColorAct = QAction('Edit variable colors', self,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                       triggered=self.editColor)
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.editVarColorAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        self.plotViewer.canvas.figure.canvas.mpl_connect('motion_notify_event', self.plotViewer.mouseMove)

        # put it in a group box to get a nice border
        self.gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        self.gb.setLayout(ly)
        self.gb.setStyleSheet('QGroupBox {border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        self.gb.setMinimumWidth(600)

        self.control = MultiVarControlPanel()
        self.control.btnCompute.clicked.connect(self.btnComputeEvent)
        self.control.unitBox.currentTextChanged.connect(self._updateList)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.control)
        self.splitter.addWidget(self.gb)
        handle = self.splitter.handle(1)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        handle.setLayout(layout)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(self.splitter)
        self.setLayout(mainLayout)

    def _updateList(self, text):
        self.control.varList.clear()
        unit = text.split(': ')[1]
        unit = '' if unit == 'None' else unit
        for var_ID in self.var_table[unit]:
            item = QListWidgetItem(var_ID)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            item.setCheckState(Qt.Unchecked)
            self.control.varList.addItem(item)

    def getSelection(self):
        selection = []
        for row in range(self.control.varList.count()):
            item = self.control.varList.item(row)
            if item.checkState() == Qt.Checked:
                selection.append(item.text().split(' (')[0])
        return selection

    def editColor(self):
        var_labels = {var: var for var in self.var_colors}
        msg = ColumnColorEditor('Variable', self.getSelection(),
                                var_labels, self.var_colors,
                                self.plotViewer.defaultColors, self.plotViewer.colorToName)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.var_colors, var_labels, self.plotViewer.nameToColor)
        self.btnComputeEvent()

    def _compute(self, time_index, line_interpolator):
        values = []
        with Serafin.Read(self.filename, self.header.language) as input_stream:
            input_stream.header = self.header
            input_stream.time = self.time
            for var in self.current_vars:
                line_var_values = []
                var_values = input_stream.read_var_in_frame(time_index, var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)
        return values

    def btnComputeEvent(self):
        self.current_vars = self.getSelection()
        if not self.current_vars:
            QMessageBox.critical(None, 'Error', 'Select at least one variable to plot.',
                                 QMessageBox.Ok)
            return

        self.plotViewer.current_title = 'Values of variables along line %s' \
                                         % self.control.lineBox.currentText().split()[1]
        self.plotViewer.current_ylabel = 'Value (%s)' \
                                         % self.control.unitBox.currentText().split(': ')[1]

        line_id = int(self.control.lineBox.currentText().split()[1]) - 1
        if self.control.intersection.isChecked():
            line_interpolator, distances = self.line_interpolators[line_id]
        else:
            line_interpolator, distances = self.line_interpolators_internal[line_id]

        time_index = int(self.control.timeSelection.index.text()) - 1
        values = self._compute(time_index, line_interpolator)

        self.plotViewer.canvas.axes.clear()

        if self.control.addInternal.isChecked():
            if self.control.intersection.isChecked():
                line_interpolator_internal, distances_internal = self.line_interpolators_internal[line_id]
                values_internal = self._compute(time_index, line_interpolator_internal)

                for i, var in enumerate(self.current_vars):
                    self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2, label=var,
                                                     color=self.var_colors[var])
                    self.plotViewer.canvas.axes.plot(distances_internal, values_internal[i],
                                                     'o', color=self.var_colors[var])

            else:
                for i, var in enumerate(self.current_vars):
                    self.plotViewer.canvas.axes.plot(distances, values[i], 'o-', linewidth=2, label=var,
                                                     color=self.var_colors[var])

        else:
            for i, var in enumerate(self.current_vars):
                self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2, label=var,
                                                 color=self.var_colors[var])

        self.plotViewer.canvas.axes.legend()
        self.plotViewer.canvas.axes.grid(linestyle='dotted')
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()

    def reset(self):
        self.control.addInternal.setChecked(False)
        self.control.intersection.setChecked(True)
        self.control.lineBox.clear()
        self.var_table = {}
        self.current_vars = []
        self.var_colors = {}
        self.control.varList.clear()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = ''
        self.plotViewer.current_xlabel = 'Cumulative distance (M)'
        self.plotViewer.current_ylabel = ''
        self.control.timeSelection.clearText()

    def getInput(self, input_data, lines, line_interpolators, line_interpolators_internal):
        self.filename = input_data.filename
        self.header = input_data.header
        self.time = input_data.time
        self.lines = lines
        self.line_interpolators = line_interpolators
        self.line_interpolators_internal = line_interpolators_internal

        if self.header.date is not None:
            year, month, day, hour, minute, second = self.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        frames = list(map(lambda x: start_time + datetime.timedelta(seconds=x), self.time))
        self.control.timeSelection.initTime(self.time, frames)

        for i in range(len(self.lines)):
            id_line = str(i+1)
            if self.line_interpolators[i][0]:
                self.control.lineBox.addItem('Line %s' % id_line)

        self.var_table = {}
        for var_ID, var_name, var_unit in zip(self.header.var_IDs, self.header.var_names,
                                              self.header.var_units):
            var_unit = var_unit.decode('utf-8').strip()
            var_name = var_name.decode('utf-8').strip()
            if var_unit in self.var_table:
                self.var_table[var_unit].append('%s (%s)' % (var_ID, var_name))
            else:
                self.var_table[var_unit] = ['%s (%s)' % (var_ID, var_name)]

        for var_unit in self.var_table:
            if not var_unit:
                self.control.unitBox.addItem('Unit: None')
            else:
                self.control.unitBox.addItem('Unit: %s' % var_unit)
        if 'M' in self.var_table:
            self.control.unitBox.setCurrentIndex(list(self.var_table.keys()).index('M'))
        self._updateList(self.control.unitBox.currentText())

        # initialize default variable colors
        j = 0
        for var_ID in self.header.var_IDs:
            j %= len(self.plotViewer.defaultColors)
            self.var_colors[var_ID] = self.plotViewer.defaultColors[j]
            j += 1


class MultiFrameControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        # create widgets plot options
        self.lineBox = QComboBox()
        self.lineBox.setFixedHeight(30)
        self.lineBox.setMaximumWidth(200)
        self.varBox = QComboBox()
        self.varBox.setMaximumWidth(200)
        self.varBox.setFixedHeight(30)

        self.timeTable = QTableWidget()
        self.timeTable.setColumnCount(3)
        self.timeTable.setHorizontalHeaderLabels(['Index', 'Time (s)', 'Date'])
        vh = self.timeTable.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(20)
        hh = self.timeTable.horizontalHeader()
        hh.setDefaultSectionSize(110)
        self.timeTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.timeTable.setSelectionMode(QAbstractItemView.NoSelection)
        self.timeTable.setMinimumHeight(300)
        self.timeTable.setMaximumWidth(400)

        # create the compute button
        self.btnCompute = QPushButton('Compute', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCompute.setFixedSize(105, 50)
        self.intersection = QCheckBox('Add intersection points')
        self.intersection.setChecked(True)
        self.addInternal = QCheckBox('Mark original points in plot')

        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a polyline'))
        hlayout.addWidget(self.lineBox)
        hlayout.setAlignment(self.lineBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Select a variable'))
        hlayout.addWidget(self.varBox)
        hlayout.setAlignment(self.varBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.intersection)
        hlayout.setAlignment(self.intersection, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.addInternal)
        hlayout.setAlignment(self.addInternal, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.timeTable)

        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignRight | Qt.AlignTop)
        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)


class MultiFrameLinePlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.filename = ''
        self.header = None
        self.time = []
        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []

        # set up a custom plot viewer
        self.editFrameColorAct = QAction('Edit frame colors', self,
                                         icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                         triggered=self.editColor)
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.editFrameColorAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        self.plotViewer.canvas.figure.canvas.mpl_connect('motion_notify_event', self.plotViewer.mouseMove)

        self.frame_colors = {}

        # put it in a group box to get a nice border
        self.gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        self.gb.setLayout(ly)
        self.gb.setStyleSheet('QGroupBox {border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        self.gb.setMinimumWidth(600)

        self.control = MultiFrameControlPanel()
        self.splitter = QSplitter()
        self.splitter.addWidget(self.control)
        self.splitter.addWidget(self.gb)
        handle = self.splitter.handle(1)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        handle.setLayout(layout)

        mainLayout = QHBoxLayout()

        mainLayout.addWidget(self.splitter)
        self.setLayout(mainLayout)
        self.control.btnCompute.clicked.connect(self.btnComputeEvent)

    def getTime(self):
        time_indices = []
        for row in range(self.control.timeTable.rowCount()):
            if self.control.timeTable.item(row, 0).checkState() == Qt.Checked:
                time_indices.append(int(self.control.timeTable.item(row, 0).text()) - 1)
        return time_indices

    def _compute(self, time_indices, line_interpolator, current_var):
        values = []
        with Serafin.Read(self.filename, self.header.language) as input_stream:
            input_stream.header = self.header
            input_stream.time = self.time
            for index in time_indices:
                line_var_values = []
                var_values = input_stream.read_var_in_frame(index, current_var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)
        return values

    def editColor(self):
        frame_labels = {i: 'Frame %d' % (i+1) for i in self.frame_colors}
        msg = ColumnColorEditor('Frame', self.getTime(),
                                frame_labels, self.frame_colors,
                                self.plotViewer.defaultColors, self.plotViewer.colorToName)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.frame_colors, frame_labels, self.plotViewer.nameToColor)
        self.btnComputeEvent()

    def btnComputeEvent(self):
        time_indices = self.getTime()
        if not time_indices:
            QMessageBox.critical(None, 'Error', 'Select at least one frame to plot.',
                                 QMessageBox.Ok)
            return

        current_var = self.control.varBox.currentText().split(' (')[0]
        self.plotViewer.current_title = 'Values of %s along line %s' % (current_var,
                                                                        self.control.lineBox.currentText().split()[1])
        var_index = self.header.var_IDs.index(current_var)
        self.plotViewer.current_ylabel = '%s (%s)' % (self.header.var_names[var_index].decode('utf-8').strip(),
                                                      self.header.var_units[var_index].decode('utf-8').strip())

        line_id = int(self.control.lineBox.currentText().split()[1]) - 1
        if self.control.intersection.isChecked():
            line_interpolator, distances = self.line_interpolators[line_id]
        else:
            line_interpolator, distances = self.line_interpolators_internal[line_id]

        values = self._compute(time_indices, line_interpolator, current_var)

        self.plotViewer.canvas.axes.clear()

        if self.control.addInternal.isChecked():
            if self.control.intersection.isChecked():
                line_interpolator_internal, distances_internal = self.line_interpolators_internal[line_id]
                values_internal = self._compute(time_indices, line_interpolator_internal, current_var)

                for i, index in enumerate(time_indices):
                    self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2,
                                                     label='Frame %d' % (index+1), color=self.frame_colors[index])
                    self.plotViewer.canvas.axes.plot(distances_internal, values_internal[i],
                                                     'o', color=self.frame_colors[index])

            else:
                for i, index in enumerate(time_indices):
                    self.plotViewer.canvas.axes.plot(distances, values[i], 'o-', linewidth=2,
                                                     label='Frame %d' % (index+1), color=self.frame_colors[index])

        else:
            for i, index in enumerate(time_indices):
                self.plotViewer.canvas.axes.plot(distances, values[i], '-', linewidth=2,
                                                 label='Frame %d' % (index+1), color=self.frame_colors[index])

        self.plotViewer.canvas.axes.legend()
        self.plotViewer.canvas.axes.grid(linestyle='dotted')
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()

    def reset(self):
        self.control.addInternal.setChecked(False)
        self.control.intersection.setChecked(True)
        self.control.lineBox.clear()
        self.control.varBox.clear()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = ''
        self.plotViewer.current_xlabel = 'Cumulative distance (M)'
        self.plotViewer.current_ylabel = ''
        self.control.timeTable.setRowCount(0)
        self.frame_colors = {}

    def getInput(self, input_data, lines, line_interpolators, line_interpolators_internal):
        self.filename = input_data.filename
        self.header = input_data.header
        self.time = input_data.time
        self.lines = lines
        self.line_interpolators = line_interpolators
        self.line_interpolators_internal = line_interpolators_internal

        if self.header.date is not None:
            year, month, day, hour, minute, second = self.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        frames = list(map(lambda x: start_time + datetime.timedelta(seconds=x), self.time))

        j = 0
        for index, value, date in zip(range(len(self.time)), self.time, frames):
            index_item = QTableWidgetItem(str(1+index))
            value_item = QTableWidgetItem(str(value))
            date_item = QTableWidgetItem(str(date))
            index_item.setCheckState(Qt.Unchecked)
            self.control.timeTable.insertRow(index)
            self.control.timeTable.setItem(index, 0, index_item)
            self.control.timeTable.setItem(index, 1, value_item)
            self.control.timeTable.setItem(index, 2, date_item)

            # initialize default frame colors
            j %= len(self.plotViewer.defaultColors)
            self.frame_colors[index] = self.plotViewer.defaultColors[j]
            j += 1

        for i in range(len(self.lines)):
            id_line = str(i+1)
            if self.line_interpolators[i][0]:
                self.control.lineBox.addItem('Line %s' % id_line)
        for var_ID, var_name in zip(self.header.var_IDs, self.header.var_names):
            var_name = var_name.decode('utf-8').strip()
            self.control.varBox.addItem('%s (%s)' % (var_ID, var_name))


class ProjectLinesImageControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.timeSelection = SimpleTimeDateSelection()

        # create widgets plot options
        self.lineBox = QComboBox()
        self.lineBox.setFixedHeight(30)
        self.lineBox.setMaximumWidth(200)
        self.intersection = QCheckBox()
        self.intersection.setChecked(True)
        self.addInternal = QCheckBox()

        # create line-var table
        self.unitBox = QComboBox()
        self.unitBox.setFixedHeight(30)
        self.unitBox.setMaximumWidth(200)

        self.varTable = QTableWidget()
        vh = self.varTable.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(20)
        hh = self.varTable.horizontalHeader()
        hh.setDefaultSectionSize(30)
        self.varTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.varTable.setSelectionMode(QAbstractItemView.NoSelection)
        self.varTable.setMinimumHeight(300)
        self.varTable.setMaximumWidth(400)

        # create the compute button
        self.btnCompute = QPushButton('Compute', icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCompute.setFixedSize(105, 50)

        # set layout
        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(self.timeSelection)
        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Reference line'))
        hlayout.addWidget(self.lineBox)
        hlayout.setAlignment(self.lineBox, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        vlayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.intersection)
        lb = QLabel('Add intersection points')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(10, 10))
        hlayout.addWidget(self.addInternal)
        lb = QLabel('Mark original points in plot')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignLeft)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addItem(QSpacerItem(10, 15))

        hlayout = QHBoxLayout()
        vlayout2 = QVBoxLayout()
        vlayout2.addWidget(self.unitBox)
        vlayout2.addWidget(self.varTable)
        vlayout2.setSpacing(10)
        hlayout.addLayout(vlayout2)
        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignRight | Qt.AlignTop)
        hlayout.setSpacing(10)
        vlayout.addItem(hlayout)

        self.setLayout(vlayout)


class ProjectLinesPlotViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.filename = ''
        self.language = 'fr'
        self.header = None
        self.time = []
        self.lines = []
        self.line_interpolators = []
        self.line_interpolators_internal = []

        self.var_table = {}
        self.current_vars = {}
        self.line_colors = {}
        self.current_linestyles = {}

        self.lineStyles = ['solid', 'dashed', 'dashdot', 'dotted']

        # set up a custom plot viewer
        self.editLineColorAct = QAction('Edit line colors', self,
                                        icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.editColor)
        self.editLineStyleAct = QAction('Edit line type', self,
                                        icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.editLineStyle)
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.editLineColorAct)
        self.plotViewer.toolBar.addAction(self.editLineStyleAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        self.plotViewer.canvas.figure.canvas.mpl_connect('motion_notify_event', self.plotViewer.mouseMove)

        # put it in a group box to get a nice border
        self.gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        self.gb.setLayout(ly)
        self.gb.setStyleSheet('QGroupBox {border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        self.gb.setMinimumWidth(600)

        self.control = ProjectLinesImageControlPanel()
        self.control.btnCompute.clicked.connect(self.btnComputeEvent)
        self.control.unitBox.currentTextChanged.connect(self._updateTable)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.control)
        self.splitter.addWidget(self.gb)
        handle = self.splitter.handle(1)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        handle.setLayout(layout)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(self.splitter)
        self.setLayout(mainLayout)
        self.setWindowTitle('Project Lines')

    def editColor(self):
        line_labels = {i: 'Line %d' % (i+1) for i in self.line_colors}
        msg = ColumnColorEditor('Line', list(self.getSelection().keys()),
                                line_labels, self.line_colors,
                                self.plotViewer.defaultColors, self.plotViewer.colorToName)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getColors(self.line_colors, line_labels, self.plotViewer.nameToColor)
        self.btnComputeEvent()

    def editLineStyle(self):
        msg = LineStyleEditor(self.lineStyles, self.current_linestyles)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLineStyles(self.current_linestyles)
        self.btnComputeEvent()

    def getSelection(self):
        self.current_vars = {}
        unit = self.control.unitBox.currentText().split(': ')[1]
        unit = '' if unit == 'None' else unit
        variables = self.var_table[unit]
        for row in range(self.control.varTable.rowCount()):
            for j in range(len(variables)):
                if self.control.varTable.item(row, j+1).checkState() == Qt.Checked:
                    line_id = int(self.control.varTable.item(row, 0).text()) - 1
                    if line_id not in self.current_vars:
                        self.current_vars[line_id] = [variables[j]]
                    else:
                        self.current_vars[line_id].append(variables[j])
        return self.current_vars

    def _updateTable(self, text):
        self.current_linestyles = {}
        self.control.varTable.setRowCount(0)
        unit = text.split(': ')[1]
        unit = '' if unit == 'None' else unit
        vars = self.var_table[unit]

        # initialize default linestyles
        j = 0
        for var in vars:
            j %= len(self.lineStyles)
            self.current_linestyles[var] = self.lineStyles[j]
            j += 1

        nb_vars = len(vars)
        self.control.varTable.setColumnCount(nb_vars + 1)
        self.control.varTable.setHorizontalHeaderLabels(['Line'] + vars)

        for i in range(len(self.lines)):
            id_line = str(i+1)
            if self.line_interpolators[i][0]:
                offset = self.control.varTable.rowCount()
                self.control.varTable.insertRow(offset)
                self.control.varTable.setItem(offset, 0, QTableWidgetItem(id_line))
                for j, var in enumerate(vars):
                    var_item = QTableWidgetItem('')
                    var_item.setCheckState(Qt.Unchecked)
                    self.control.varTable.setItem(offset, j+1, var_item)

    def _compute(self, time_index, line_interpolators, reference, max_distance):
        distances = {}
        values = {}
        with Serafin.Read(self.filename, self.language) as input_stream:
            input_stream.header = self.header
            input_stream.time = self.time
            for line_id in self.current_vars:
                distances[line_id] = []
                values[line_id] = {}

                for var in self.current_vars[line_id]:
                    values[line_id][var] = []

                for x, y, (i, j, k), interpolator in line_interpolators[line_id]:
                    d = reference.project(x, y)
                    if d <= 0 or d >= max_distance:
                        continue
                    distances[line_id].append(d)

                    for var in self.current_vars[line_id]:
                        all_values = input_stream.read_var_in_frame(time_index, var)
                        values[line_id][var].append(interpolator.dot(all_values[[i, j, k]]))
                distances[line_id] = np.array(distances[line_id])
        return distances, values

    def btnComputeEvent(self):
        self.current_vars = self.getSelection()
        if not self.current_vars:
            QMessageBox.critical(self, 'Error', 'Select at least one variable to plot.',
                                 QMessageBox.Ok)
            return
        ref_id = int(self.control.lineBox.currentText().split()[1]) - 1
        self.plotViewer.current_title = 'Values of variables along line %d' \
                                        % (ref_id+1)
        self.plotViewer.current_ylabel = 'Value (%s)' \
                                         % (self.control.unitBox.currentText().split(': ')[1])

        line_interpolators = {}
        if self.control.intersection.isChecked():
            for line_id in self.current_vars:
                line_interpolator, distances = self.line_interpolators[line_id]
                line_interpolators[line_id] = line_interpolator
        else:
            for line_id in self.current_vars:
                line_interpolator, distances = self.line_interpolators_internal[line_id]
                line_interpolators[line_id] = line_interpolator

        reference = self.lines[ref_id]
        max_distance = reference.length()
        time_index = int(self.control.timeSelection.index.text()) - 1
        distances, values = self._compute(time_index, line_interpolators, reference, max_distance)

        self.plotViewer.canvas.axes.clear()

        if self.control.addInternal.isChecked():
            if self.control.intersection.isChecked():
                line_interpolators_internal = {}
                for line_id in self.current_vars:
                    line_interpolator, _ = self.line_interpolators_internal[line_id]
                    line_interpolators_internal[line_id] = line_interpolator
                distances_internal, values_internal = self._compute(time_index,
                                                                    line_interpolators_internal,
                                                                    reference, max_distance)
                for line_id, variables in self.current_vars.items():
                    for var in variables:
                        self.plotViewer.canvas.axes.plot(distances[line_id], values[line_id][var],
                                                         linestyle=self.current_linestyles[var],
                                                         color=self.line_colors[line_id],
                                                         linewidth=2, label='%s$_%d$' % (var, line_id+1))

                        self.plotViewer.canvas.axes.plot(distances_internal[line_id],
                                                         values_internal[line_id][var], 'o',
                                                         color=self.line_colors[line_id])
            else:
                for line_id, variables in self.current_vars.items():
                    for var in variables:
                        self.plotViewer.canvas.axes.plot(distances[line_id], values[line_id][var],
                                                         marker='o', linestyle=self.current_linestyles[var],
                                                         color=self.line_colors[line_id], linewidth=2,
                                                         label='%s$_%d$' % (var, line_id+1))

        else:
            for line_id, variables in self.current_vars.items():
                for var in variables:
                    self.plotViewer.canvas.axes.plot(distances[line_id], values[line_id][var],
                                                     linestyle=self.current_linestyles[var],
                                                     color=self.line_colors[line_id], linewidth=2,
                                                     label='%s$_%d$' % (var, line_id+1))

        self.plotViewer.canvas.axes.legend()
        self.plotViewer.canvas.axes.grid(linestyle='dotted')
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()

    def reset(self):
        self.control.intersection.setChecked(True)
        self.control.addInternal.setChecked(False)
        self.control.lineBox.clear()
        self.control.varTable.setRowCount(0)
        self.current_vars = {}
        self.line_colors = {}
        self.current_linestyles = {}
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = ''
        self.plotViewer.current_xlabel = 'Cumulative distance (M)'
        self.plotViewer.current_ylabel = ''
        self.control.timeSelection.clearText()

    def getInput(self, input_data, lines, line_interpolators, line_interpolators_internal):
        self.filename = input_data.filename
        self.header = input_data.header
        self.time = input_data.time
        self.lines = lines
        self.line_interpolators = line_interpolators
        self.line_interpolators_internal = line_interpolators_internal

        if self.header.date is not None:
            year, month, day, hour, minute, second = self.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        frames = list(map(lambda x: start_time + datetime.timedelta(seconds=x), self.time))
        self.control.timeSelection.initTime(self.time, frames)

        self.var_table = {}
        for var_ID, var_name, var_unit in zip(self.header.var_IDs, self.header.var_names,
                                              self.header.var_units):
            var_unit = var_unit.decode('utf-8').strip()
            if var_unit in self.var_table:
                self.var_table[var_unit].append(var_ID)
            else:
                self.var_table[var_unit] = [var_ID]

        for var_unit in self.var_table:
            if not var_unit:
                self.control.unitBox.addItem('Unit: None')
            else:
                self.control.unitBox.addItem('Unit: %s' % var_unit)
        if 'M' in self.var_table:
            self.control.unitBox.setCurrentIndex(list(self.var_table.keys()).index('M'))
        self._updateTable(self.control.unitBox.currentText())

        j = 0
        for i in range(len(self.lines)):
            id_line = str(i+1)
            if self.line_interpolators[i][0]:
                j %= len(self.plotViewer.defaultColors)
                self.control.lineBox.addItem('Line %s' % id_line)
                self.line_colors[i] = self.plotViewer.defaultColors[j]   # initialize default line colors
                j += 1
