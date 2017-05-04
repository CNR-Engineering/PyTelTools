"""!
A GUI for extracting variables and time frames from .slf file
"""

import os
import sys
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import logging
import copy
from slf import Serafin
from slf.variables import get_available_variables, \
    do_calculations_in_frame, get_necessary_equations, get_US_equation, add_US

_YELLOW = QColor(245, 255, 207)
_GREEN = QColor(200, 255, 180)
_BLUE = QColor(200, 230, 250)


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


class FrictionLawMessage(QDialog):
    """!
    @brief Message dialog for choosing one of the friction laws
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.chezy = QRadioButton('Chezy')
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
    def __init__(self, old_velocities, parent=None):
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        self.buttonAdd = QPushButton('Add a fall velocity', self)
        self.buttonAdd.clicked.connect(self.btnAddEvent)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Click on the cell to edit name'))
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
        name_item = QTableWidgetItem(value_ID)
        unit_item = QTableWidgetItem('')
        self.table.setItem(nb_row, 0, QTableWidgetItem(id_item))
        self.table.setItem(nb_row, 1, QTableWidgetItem(name_item))
        self.table.setItem(nb_row, 2, QTableWidgetItem(unit_item))
        self.table.item(nb_row, 0).setFlags(Qt.ItemIsEditable)
        self.table.item(nb_row, 2).setFlags(Qt.ItemIsEditable)


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
        self.setFixedSize(600, 30)

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
        style = QApplication.style()

        rectHandle = style.subControlRect(style.CC_Slider, opt, style.SC_SliderHandle)

        if self.active_slider == 0:
            pos_low = rectHandle.topLeft()
            pos_low.setX(pos_low.x() + self._low)
            pos_low = self.mapToGlobal(pos_low)
            QToolTip.showText(pos_low, str(self.low()), self)
        elif self.active_slider == 1:
            pos_high = rectHandle.topLeft()
            pos_high.setX(pos_high.x() + self._high)
            pos_high = self.mapToGlobal(pos_high)
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
            return
        if start_index <= 0 or end_index > self.nb_frames or start_index > end_index:
            return
        self.setLow(start_index-1)
        self.setHigh(end_index-1)
        self.info.updateText(self._low, self.time_frames[self._low].total_seconds(), self.low(),
                             self._high, self.time_frames[self._high].total_seconds(), self.high())


class SelectedTimeINFO(QWidget):
    """!
    @brief Text fields for time selection display (with slider)
    """
    def __init__(self):
        super().__init__()

        self.startIndex = QLineEdit('', self)
        self.endIndex = QLineEdit('', self)
        self.startValue = QLineEdit('', self)
        self.endValue = QLineEdit('', self)
        self.startDate = QLineEdit('', self)
        self.endDate = QLineEdit('', self)
        for w in [self.startValue, self.endValue, self.startDate, self.endDate]:
            w.setReadOnly(True)

        self.startIndex.setFixedWidth(30)
        self.endIndex.setFixedWidth(30)
        self.startDate.setFixedWidth(110)
        self.endDate.setFixedWidth(110)

        self.timeSamplig = QLineEdit('1', self)
        self.timeSamplig.setFixedWidth(30)

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
        for w in [self.startIndex, self.endIndex, self.startValue, self.endValue, self.startDate, self.endDate]:
            w.clear()


class OutputProgressDialog(QProgressDialog):
    def __init__(self, parent=None):
        super().__init__('Output in progress', 'OK', 0, 100, parent)

        self.cancelButton = QPushButton('OK')
        self.setCancelButton(self.cancelButton)
        self.cancelButton.setEnabled(False)


        self.setAutoReset(False)
        self.setAutoClose(False)

        self.setWindowTitle('Writing the output...')
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setFixedSize(300, 150)

        self.open()
        self.setValue(0)
        QApplication.processEvents()

class ExtractVariablesGUI(QWidget):
    """!
    @brief A graphical interface for extracting and computing variables from .slf file
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.language = None

        # some attributes to store the input file info
        self.header = None
        self.time = []
        self.available_vars = []
        self.us_equation = None
        self.fall_velocities = []

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setFixedWidth(800)
        self.setMaximumHeight(750)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowTitle('Extract variables and frames from Serafin file')
        self._center()

    def closeEvent(self, event):
        if self.parent is not None:
            self.parent.closeSerafin()
        event.accept()

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """
        # create the button open
        self.btnOpen = QPushButton('Open', self)
        self.btnOpen.setToolTip('<b>Open</b> a .slf file')
        self.btnOpen.setFixedSize(85, 50)

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
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.frenchButton.setChecked(True)

        # create two 3-column tables for variables selection
        self.firstTable = TableWidgetDragRows()
        self.secondTable = TableWidgetDragRows()
        for tw in [self.firstTable, self.secondTable]:
            tw.setColumnCount(3)
            tw.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
            hh = tw.horizontalHeader()
            hh.setDefaultSectionSize(110)
            tw.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.secondTable.setFixedHeight(300)

        # create a button for interpreting W from user-defined friction law
        self.btnAddUS = QPushButton('Add US from friction law', self)
        self.btnAddUS.setToolTip('Compute <b>US</b> based on a friction law')
        self.btnAddUS.setEnabled(False)
        self.btnAddUS.setFixedWidth(200)

        # create a button for adding Rouse number from user-defined fall velocity
        self.btnAddWs = QPushButton('Add Rouse from fall velocity', self)
        self.btnAddWs.setToolTip('Compute <b>Rouse</b> for specific fall velocity')
        self.btnAddWs.setEnabled(False)
        self.btnAddWs.setFixedWidth(200)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create a check box for output file format (simple or double precision)
        self.singlePrecisionBox = QCheckBox('Convert to SERAFIN \n(single precision)', self)
        self.singlePrecisionBox.setEnabled(False)

        # create a slider for time selection
        self.timeSlider = TimeRangeSlider()
        self.timeSlider.setEnabled(False)

        # create text boxes for displaying the time selection and sampling
        self.timeSelection = SelectedTimeINFO()
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)

        # create the submit button
        self.btnSubmit = QPushButton('Submit', self)
        self.btnSubmit.setToolTip('<b>Submit</b> to write a .slf output')
        self.btnSubmit.setFixedSize(85, 50)
        self.btnSubmit.setEnabled(False)

    def _bindEvents(self):
        """!
        @brief (Used in __init__) Bind events to widgets
        """
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnAddUS.clicked.connect(self.btnAddUSEvent)
        self.btnAddWs.clicked.connect(self.btnAddWsEvent)
        self.timeSelection.startIndex.returnPressed.connect(self.timeSlider.enterIndexEvent)
        self.timeSelection.endIndex.returnPressed.connect(self.timeSlider.enterIndexEvent)

    def _setLayout(self):
        """
        @brief: (Used in __init__) Set up layout
        """
        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Input file'))
        hlayout.addWidget(self.inNameBox)

        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Summary'))
        hlayout.addWidget(self.summaryTextBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(1, 10))
        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(30, 1))
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.firstTable)
        vlayout.addItem(QSpacerItem(1, 5))
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.btnAddUS)
        hlayout2.addItem(QSpacerItem(30, 1))
        vlayout.addLayout(hlayout2)
        hlayout2 = QHBoxLayout()
        hlayout2.addItem(QSpacerItem(30, 1))
        hlayout2.addWidget(self.btnAddWs)
        hlayout2.addItem(QSpacerItem(30, 1))
        vlayout.addLayout(hlayout2)
        vlayout.addItem(QSpacerItem(1, 5))
        vlayout.setAlignment(Qt.AlignLeft)

        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))

        vlayout = QVBoxLayout()
        lb = QLabel('Output variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.secondTable)

        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(30, 1))

        mainLayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 5))
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.timeSlider)
        hlayout.addItem(QSpacerItem(30, 1))
        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnSubmit)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.singlePrecisionBox)
        hlayout.addLayout(vlayout)

        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.timeSelection)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.setAlignment(Qt.AlignLeft)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(800, 10))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _center(self):
        """!
        @brief (Used in __init__) Center the window with respect to the screen
        """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)

    def _initVarTables(self):
        """!
        @brief (Used in btnOpenEvent) Put available variables ID-name-unit in the table display
        """

        # add original variables to the table
        for i, (id, name, unit) in enumerate(zip(self.header.var_IDs, self.header.var_names, self.header.var_units)):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(id.strip())
            name_item = QTableWidgetItem(name.decode('utf-8').strip())
            unit_item = QTableWidgetItem(unit.decode('utf-8').strip())
            self.firstTable.setItem(i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(i, 2, QTableWidgetItem(unit_item))
        offset = self.firstTable.rowCount()

        # find new computable variables (stored as slf.variables.Variable objects)
        self.available_vars = get_available_variables(self.header.var_IDs)

        # add new variables to the table
        for i, var in enumerate(self.available_vars):
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var.ID())
            name_item = QTableWidgetItem(var.name(self.language))
            unit_item = QTableWidgetItem(var.unit())
            self.firstTable.setItem(offset+i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(offset+i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(offset+i, 2, QTableWidgetItem(unit_item))
            self.firstTable.item(offset+i, 0).setBackground(_YELLOW)  # set new variables colors to yellow
            self.firstTable.item(offset+i, 1).setBackground(_YELLOW)
            self.firstTable.item(offset+i, 2).setBackground(_YELLOW)

    def _reinitInput(self):
        """!
        @brief (Used in btnOpenEvent) Reinitialize input file data before reading a new file
        """
        self.summaryTextBox.clear()
        self.available_vars = []
        self.header = None
        self.time = []
        self.us_equation = None
        self.fall_velocities = []
        self.btnAddUS.setEnabled(False)
        self.btnAddWs.setEnabled(False)
        self.singlePrecisionBox.setChecked(False)
        self.singlePrecisionBox.setEnabled(False)
        self.firstTable.setRowCount(0)
        self.secondTable.setRowCount(0)
        self.timeSlider.setEnabled(False)
        self.timeSelection.clearText()
        self.timeSelection.startIndex.setEnabled(False)
        self.timeSelection.endIndex.setEnabled(False)
        self.timeSelection.timeSamplig.setText('1')
        self.btnSubmit.setEnabled(False)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def _handleOverwrite(self, filename):
        """!
        @brief (Used in btnSubmitEvent) Handle manually the overwrite option when saving output file
        """
        if os.path.exists(filename):
            msg = QMessageBox.warning(self, 'Confirm overwrite',
                                      'The file already exists. Do you want to replace it ?',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                logging.info('Output canceled')
                return None
            return True
        return False

    def _getOutputTime(self):
        start_index = int(self.timeSelection.startIndex.text())
        end_index = int(self.timeSelection.endIndex.text())
        try:
            sampling_frequency = int(self.timeSelection.timeSamplig.text())
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be a number!',
                                 QMessageBox.Ok)
            return []
        if sampling_frequency < 1 or sampling_frequency > end_index:
            QMessageBox.critical(self, 'Error', 'The sampling frequency must be in the range [1; nbFrames]!',
                                 QMessageBox.Ok)
            return []
        return list(range(start_index-1, end_index, sampling_frequency))

    def _getSelectedVariables(self):
        selected = []
        for i in range(self.secondTable.rowCount()):
            selected.append((self.secondTable.item(i, 0).text(),
                            bytes(self.secondTable.item(i, 1).text(), 'utf-8').ljust(16),
                            bytes(self.secondTable.item(i, 2).text(), 'utf-8').ljust(16)))
        return selected

    def _getOutputHeader(self, selected_vars):
        output_header = self.header.copy()
        output_header.nb_var = len(selected_vars)
        output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
        for var_ID, var_name, var_unit in selected_vars:
            output_header.var_IDs.append(var_ID)
            output_header.var_names.append(var_name)
            output_header.var_units.append(var_unit)
        if self.singlePrecisionBox.isChecked():
            output_header.to_single_precision()
        return output_header

    def btnAddUSEvent(self):
        msg = FrictionLawMessage()
        value = msg.exec_()
        if value != QDialog.Accepted:
            return

        friction_law = msg.getChoice()
        self.us_equation = get_US_equation(friction_law)
        add_US(self.available_vars)

        # add US, TAU and DMAX to available variable
        offset = self.firstTable.rowCount()
        for i in range(3):
            var = self.available_vars[-3+i]
            self.firstTable.insertRow(self.firstTable.rowCount())
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.language))
            unit_item = QTableWidgetItem(var.unit())
            self.firstTable.setItem(offset+i, 0, QTableWidgetItem(id_item))
            self.firstTable.setItem(offset+i, 1, QTableWidgetItem(name_item))
            self.firstTable.setItem(offset+i, 2, QTableWidgetItem(unit_item))
            self.firstTable.item(offset+i, 0).setBackground(_GREEN)  # set new US color to green
            self.firstTable.item(offset+i, 1).setBackground(_GREEN)
            self.firstTable.item(offset+i, 2).setBackground(_GREEN)

        # lock the add US button again
        self.btnAddUS.setEnabled(False)

        # unlock add Ws button
        self.btnAddWs.setEnabled(True)

    def btnAddWsEvent(self):
        msg = FallVelocityMessage(self.fall_velocities)
        value = msg.exec_()
        if value != QDialog.Accepted:
            return
        table = msg.get_table()
        offset = self.secondTable.rowCount()
        for i in range(len(table)):
            self.secondTable.insertRow(offset+i)
            for j in range(3):
                item = QTableWidgetItem(table[i][j])
                self.secondTable.setItem(offset+i, j, item)
                self.secondTable.item(offset+i, j).setBackground(_BLUE)
        for i in range(len(table)):
            self.fall_velocities.append(float(table[i][0][6:]))

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', options=options)
        if not filename:
            return

        # reinitialize input file data
        self._reinitInput()

        self.filename = filename
        self.inNameBox.setText(filename)

        with Serafin.Read(self.filename, self.language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # record the time series
            resin.get_time()

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        logging.info('File closed')

        # displaying the available variables
        self._initVarTables()

        # unlock convert to single precision
        if self.header.float_type == 'd':
            self.singlePrecisionBox.setEnabled(True)

        # unlock add US button
        if 'US' not in self.header.var_IDs and 'W' in self.header.var_IDs:
            available_var_IDs = list(map(lambda x: x.ID(), self.available_vars))
            available_var_IDs.extend(self.header.var_IDs)
            if 'H' in available_var_IDs and 'M' in available_var_IDs:
                self.btnAddUS.setEnabled(True)

        # unlock add Ws button
        if 'US' in self.header.var_IDs:
            self.btnAddWs.setEnabled(True)

        # unlock the time slider
        if resin.header.date is not None:
            year, month, day, hour, minute, second = resin.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x), resin.time))
        self.timeSlider.reinit(start_time, time_frames, self.timeSelection)
        if self.header.nb_frames > 1:
            self.timeSlider.setEnabled(True)
            self.timeSelection.startIndex.setEnabled(True)
            self.timeSelection.endIndex.setEnabled(True)

        # finally unlock the submit button
        self.btnSubmit.setEnabled(True)

    def btnSubmitEvent(self):
        output_time_indices = self._getOutputTime()
        if not output_time_indices:
            return

        selected_vars = self._getSelectedVariables()
        if not selected_vars:
            QMessageBox.critical(self, 'Error', 'Choose at least one output variable before submit!',
                                 QMessageBox.Ok)
            return

        # create the save file dialog
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        options |= QFileDialog.DontConfirmOverwrite
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  'Serafin Files (*.slf)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.slf':
            filename += '.slf'

        # handle overwrite manually
        overwrite = self._handleOverwrite(filename)
        if overwrite is None:
            return

        # disable close button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()

        progressBar = OutputProgressDialog()

        # do some calculations
        with Serafin.Read(self.filename, self.language) as resin:
            # instead of re-reading the header and the time, just do a copy
            resin.header = self.header
            resin.time = self.time
            progressBar.setValue(5)
            QApplication.processEvents()

            with Serafin.Write(filename, self.language, overwrite) as resout:
                # deduce header from selected variable IDs and write header
                output_header = self._getOutputHeader(selected_vars)
                logging.info('Writing the output with variables %s' % str(output_header.var_IDs))

                resout.write_header(output_header)

                # do some additional computations
                necessary_equations = get_necessary_equations(self.header.var_IDs, output_header.var_IDs,
                                                              self.us_equation)

                for i in output_time_indices:
                    vals = do_calculations_in_frame(necessary_equations, self.us_equation, resin, i,
                                                    output_header.var_IDs, output_header.np_float_type)
                    resout.write_entire_frame(output_header, self.time[i], vals)
                    progressBar.setValue(5 + int(95 * (i+1) / len(output_time_indices)))

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()

        # enable close button
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()


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
    widget = ExtractVariablesGUI()
    widget.show()
    app.exec_()


