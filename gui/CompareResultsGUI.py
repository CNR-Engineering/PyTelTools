import sys
import os
import logging
import copy
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import numpy as np

from gui.util import PlotViewer
from slf import Serafin
from slf.mesh2D import ReferenceMesh


class SimpleTimeSelection(QWidget):
    def __init__(self):
        super().__init__()
        self.refIndex = QLineEdit('', self)
        self.refIndex.setMaximumWidth(60)
        self.refSlider = TimeSlider(self.refIndex)
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Reference frame index'), 1, 1)
        glayout.addWidget(self.refIndex, 1, 2)
        glayout.addWidget(self.refSlider, 1, 3)
        glayout.setSpacing(10)
        self.setLayout(glayout)
        self.refIndex.returnPressed.connect(self.refSlider.enterIndexEvent)

    def initRef(self, nb_frames):
        self.refSlider.reinit(nb_frames, 0)
        self.refIndex.setText(str(1))

    def clearText(self):
        self.refIndex.clear()


class DoubleTimeSelection(QWidget):
    def __init__(self):
        super().__init__()
        self.refIndex = QLineEdit('', self)
        self.refIndex.setMaximumWidth(60)
        self.testIndex = QLineEdit('', self)
        self.testIndex.setMaximumWidth(60)

        self.refSlider = TimeSlider(self.refIndex)
        self.testSlider = TimeSlider(self.testIndex)
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Reference frame index'), 1, 1)
        glayout.addWidget(self.refIndex, 1, 2)
        glayout.addWidget(self.refSlider, 1, 3)
        glayout.addWidget(QLabel('Test frame index'), 2, 1)
        glayout.addWidget(self.testIndex, 2, 2)
        glayout.addWidget(self.testSlider, 2, 3)
        glayout.setSpacing(10)
        self.setLayout(glayout)

        self.refIndex.returnPressed.connect(self.refSlider.enterIndexEvent)
        self.testIndex.returnPressed.connect(self.testSlider.enterIndexEvent)

    def initRef(self, nb_frames):
        self.refSlider.reinit(nb_frames, 0)
        self.refIndex.setText(str(1))

    def initTest(self, nb_frames):
        self.testSlider.reinit(nb_frames, nb_frames-1)
        self.testIndex.setText(str(nb_frames))

    def clearText(self):
        self.refIndex.clear()
        self.testIndex.clear()


class TimeSlider(QSlider):
    """!
    @brief A slider for choosing the time frame.
    """
    def __init__(self, display):
        super().__init__()
        self.display = display

        self.setOrientation(Qt.Horizontal)
        self.setMinimumWidth(500)

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
        style = QApplication.style()
        rectHandle = style.subControlRect(style.CC_Slider, opt, style.SC_SliderHandle)
        pos = rectHandle.topLeft()
        pos.setX(pos.x())
        pos = self.mapToGlobal(pos)
        QToolTip.showText(pos, str(self.value()+1), self)

        self.update()

    def mouseReleaseEvent(self, event):
        self.display.setText(str(1 + self.value()))

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
            value = int(self.display.text())
        except ValueError:
            self.display.setText(str(self.value()+1))
            return
        if value <= 0 or value > self.nb_frames:
            self.display.setText(str(self.value()+1))
            return
        self.setValue(value-1)


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.ref_language = 'fr'
        self.test_language = 'fr'
        self.ref_filename = None
        self.test_filename = None
        self.ref_header = None
        self.test_header = None
        self.ref_time = []
        self.test_time = []

        self.ref_mesh = None

        self._initWidgets()
        self._setLayout()
        self._bindEvents()
        self.setFixedHeight(500)

    def _initWidgets(self):
        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        self.frenchButton.setChecked(True)

        # create the button open the reference file
        self.btnOpenRef = QPushButton('Load\nReference', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenRef.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenRef.setFixedSize(105, 50)

        # create the button open the test file
        self.btnOpenTest = QPushButton('Load\nTest', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpenTest.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenTest.setFixedSize(105, 50)
        self.btnOpenTest.setEnabled(False)

        # create some text fields displaying the IO files info
        self.refNameBox = QLineEdit()
        self.refNameBox.setReadOnly(True)
        self.refNameBox.setFixedHeight(30)
        self.refNameBox.setMinimumWidth(600)
        self.refSummaryTextBox = QPlainTextEdit()
        self.refSummaryTextBox.setMinimumHeight(40)
        self.refSummaryTextBox.setMaximumHeight(50)
        self.refSummaryTextBox.setMinimumWidth(600)
        self.refSummaryTextBox.setReadOnly(True)
        self.testNameBox = QLineEdit()
        self.testNameBox.setReadOnly(True)
        self.testNameBox.setFixedHeight(30)
        self.testNameBox.setMinimumWidth(600)
        self.testSummaryTextBox = QPlainTextEdit()
        self.testSummaryTextBox.setReadOnly(True)
        self.testSummaryTextBox.setMinimumHeight(40)
        self.testSummaryTextBox.setMaximumHeight(50)
        self.testSummaryTextBox.setMinimumWidth(600)

        # create combo box widgets for choosing the variable
        self.varBox = QComboBox()
        self.varBox.setFixedSize(400, 30)

    def _bindEvents(self):
        self.btnOpenRef.clicked.connect(self.btnOpenRefEvent)
        self.btnOpenTest.clicked.connect(self.btnOpenTestEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpenRef)
        hlayout.addWidget(self.btnOpenTest)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Reference'), 1, 1)
        glayout.addWidget(self.refNameBox, 1, 2)
        glayout.addWidget(QLabel('     Summary'), 2, 1)
        glayout.addWidget(self.refSummaryTextBox, 2, 2)
        glayout.addWidget(QLabel('     Test'), 3, 1)
        glayout.addWidget(self.testNameBox, 3, 2)
        glayout.addWidget(QLabel('     Summary'), 4, 1)
        glayout.addWidget(self.testSummaryTextBox, 4, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setVerticalSpacing(10)

        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the variable to compare'), 1, 1)
        glayout.addWidget(self.varBox, 1, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 15))
        self.setLayout(mainLayout)

    def _reinitRef(self, filename):
        if not self.frenchButton.isChecked():
            self.ref_language = 'en'
        else:
            self.ref_language = 'fr'
        self.ref_mesh = None
        self.ref_filename = filename
        self.refNameBox.setText(filename)
        self.refSummaryTextBox.clear()
        self.ref_header = None

        self.test_header = None
        self.test_filename = None
        self.testSummaryTextBox.clear()
        self.testNameBox.clear()
        self.varBox.clear()
        self.btnOpenTest.setEnabled(False)
        self.parent.reset()

    def _reinitTest(self, filename):
        if not self.frenchButton.isChecked():
            self.test_language = 'en'
        else:
            self.test_language = 'fr'
        self.test_header = None
        self.test_filename = filename
        self.testNameBox.setText(filename)
        self.testSummaryTextBox.clear()
        self.varBox.clear()

    def btnOpenRefEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return

        self._reinitRef(filename)

        with Serafin.Read(self.ref_filename, self.ref_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # update the file summary
            self.refSummaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.ref_header = copy.deepcopy(resin.header)
            self.ref_time = resin.time[:]

        self.ref_mesh = ReferenceMesh(self.ref_header)
        self.parent.add_reference()
        self.btnOpenTest.setEnabled(True)

    def btnOpenTestEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(),
                                                  options=options)
        if not filename:
            return

        self._reinitTest(filename)

        with Serafin.Read(self.test_filename, self.test_language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return

            # check if the mesh is identical to the reference
            if not np.all(self.ref_header.x == resin.header.x) or \
               not np.all(self.ref_header.y == resin.header.y) or \
               not np.all(self.ref_header.ikle == resin.header.ikle):
                QMessageBox.critical(self, 'Error', 'The mesh is not identical to the reference.',
                                     QMessageBox.Ok)
                return

            # check if the test file has common variables with the reference file
            common_vars = [(var_ID, var_names) for var_ID, var_names
                           in zip(self.ref_header.var_IDs, self.ref_header.var_names)
                           if var_ID in resin.header.var_IDs]
            if not common_vars:
                QMessageBox.critical(self, 'Error', 'No common variable with the reference file.',
                                     QMessageBox.Ok)
                return

            # record the time series
            resin.get_time()

            # update the file summary
            self.testSummaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.test_header = copy.deepcopy(resin.header)
            self.test_time = resin.time[:]

        self.parent.add_test()

        for var_ID, var_name in common_vars:
            self.varBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())


class ComputeErrorsTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab
        self.timeSelection = DoubleTimeSelection()
        self.btnCompute = QPushButton('Compute')
        self.btnCompute.setFixedSize(105, 50)
        self.resultTextBox = QPlainTextEdit()

        self.btnCompute.clicked.connect(self.btnComputeEvent)

        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.timeSelection)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnCompute)
        hlayout.setAlignment(self.btnCompute, Qt.AlignTop)
        hlayout.setAlignment(Qt.AlignHCenter)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Result'))
        vlayout.addWidget(self.resultTextBox)
        hlayout.addItem(QSpacerItem(10, 1))
        hlayout.addLayout(vlayout)
        mainLayout.addLayout(hlayout)
        self.setLayout(mainLayout)

        self.template = '=== Comparison between Ref (frame {}) and Test (frame {}) ===\n'\
                        'MSD  (Mean signed deviation)         \t{:<30}\n' \
                        'MAD  (Mean absolute deviation)       \t{:<30}\n' \
                        'RMSD (Root mean square deviation)    \t{:<30}\n'

    def add_reference(self):
        self.timeSelection.initRef(self.input.ref_header.nb_frames)

    def add_test(self):
        self.timeSelection.initTest(self.input.test_header.nb_frames)

    def reset(self):
        self.timeSelection.clearText()
        self.resultTextBox.clear()

    def btnComputeEvent(self):
        ref_time = int(self.timeSelection.refIndex.text()) - 1
        test_time = int(self.timeSelection.testIndex.text()) - 1
        selected_variable = self.input.varBox.currentText().split('(')[0][:-1]

        with Serafin.Read(self.input.ref_filename, self.input.ref_language) as resin:
            resin.header = self.input.ref_header
            resin.time = self.input.ref_time
            ref_values = resin.read_var_in_frame(ref_time, selected_variable)

        with Serafin.Read(self.input.test_filename, self.input.test_language) as resin:
            resin.header = self.input.test_header
            resin.time = self.input.test_time
            test_values = resin.read_var_in_frame(test_time, selected_variable)

        values = test_values - ref_values
        msd = self.input.ref_mesh.mean_signed_deviation(values)
        mad = self.input.ref_mesh.mean_absolute_deviation(values)
        rmsd = self.input.ref_mesh.root_mean_square_deviation(values)
        self.resultTextBox.appendPlainText(self.template.format(ref_time+1, test_time+1, msd, mad, rmsd))


class ErrorEvolutionTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        # set up a custom plot viewer
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)

        # put it in a group box to get a nice border
        gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        gb.setLayout(ly)
        gb.setStyleSheet('QGroupBox { background-color: rgb(255,255,255); '
                         'border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        gb.setMaximumWidth(900)

        # create the reference time selection widget
        self.timeSelection = SimpleTimeSelection()
        self.btnCompute = QPushButton('Compute')

        # create the compute button
        self.btnCompute.setFixedSize(105, 50)
        self.btnCompute.clicked.connect(self.btnComputeEvent)

        # set layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.timeSelection)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnCompute)
        hlayout.addWidget(gb)
        hlayout.setAlignment(self.btnCompute, Qt.AlignTop)
        hlayout.setAlignment(Qt.AlignHCenter)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        self.setLayout(mainLayout)

    def add_reference(self):
        self.timeSelection.initRef(self.input.ref_header.nb_frames)

    def add_test(self):
        pass

    def reset(self):
        self.timeSelection.clearText()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = 'Evolution of MAD (mean absolute deviation)'
        self.plotViewer.current_ylabel = 'MAD'
        self.plotViewer.current_xlabel = 'Time (second)'

    def btnComputeEvent(self):
        ref_time = int(self.timeSelection.refIndex.text()) - 1
        selected_variable = self.input.varBox.currentText().split('(')[0][:-1]

        with Serafin.Read(self.input.ref_filename, self.input.ref_language) as resin:
            resin.header = self.input.ref_header
            resin.time = self.input.ref_time
            ref_values = resin.read_var_in_frame(ref_time, selected_variable)

        mad = []
        with Serafin.Read(self.input.test_filename, self.input.test_language) as resin:
            resin.header = self.input.test_header
            resin.time = self.input.test_time
            for i in range(len(self.input.test_time)):
                values = resin.read_var_in_frame(i, selected_variable) - ref_values
                mad.append(self.input.ref_mesh.mean_absolute_deviation(values))

        self.plotViewer.plot(self.input.test_time, mad)


class ErrorDistributionTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        # set up a custom plot viewer
        self.plotViewer = PlotViewer()
        self.plotViewer.exitAct.setEnabled(False)
        self.plotViewer.menuBar.setVisible(False)
        self.plotViewer.toolBar.addAction(self.plotViewer.xLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.yLabelAct)
        self.plotViewer.toolBar.addSeparator()
        self.plotViewer.toolBar.addAction(self.plotViewer.titleAct)
        # put it in a group box to get a nice border
        gb = QGroupBox()
        ly = QHBoxLayout()
        ly.addWidget(self.plotViewer)
        gb.setLayout(ly)
        gb.setStyleSheet('QGroupBox { background-color: rgb(255,255,255); '
                         'border: 8px solid rgb(108, 122, 137); border-radius: 6px }')
        gb.setMaximumWidth(900)

        # create the reference time selection widget
        self.timeSelection = DoubleTimeSelection()
        self.btnCompute = QPushButton('Compute')

        # create the compute button
        self.btnCompute.setFixedSize(105, 50)
        self.btnCompute.clicked.connect(self.btnComputeEvent)

        # create the stats box
        self.resultBox = QPlainTextEdit()
        self.resultBox.setMaximumWidth(300)
        
        # set layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.timeSelection)
        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.btnCompute)
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(QLabel('Result'))
        vlayout.addWidget(self.resultBox)
        hlayout.addLayout(vlayout)
        hlayout.addWidget(gb)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout)
        self.setLayout(mainLayout)

        # template for text output
        self.template = '=== EWSD distribution between Ref (frame {}) and Test (frame {}) ===\n'\
                        'Mean         \t{:<30}\n' \
                        'Variance     \t{:<30}\n' \
                        'Min          \t{:<30}\n' \
                        'Quartile 25  \t{:<30}\n' \
                        'Median       \t{:<30}\n' \
                        'Quartile 75  \t{:<30}\n' \
                        'Max          \t{:<30}\n'

    def add_reference(self):
        self.timeSelection.initRef(self.input.ref_header.nb_frames)

    def add_test(self):
        self.timeSelection.initTest(self.input.test_header.nb_frames)

    def reset(self):
        self.timeSelection.clearText()
        self.resultBox.clear()
        self.plotViewer.defaultPlot()
        self.plotViewer.current_title = 'Distribution of EWSD (element-wise signed deviation)'
        self.plotViewer.current_ylabel = 'Frequency'
        self.plotViewer.current_xlabel = 'EWSD'

    def btnComputeEvent(self):
        ref_time = int(self.timeSelection.refIndex.text()) - 1
        test_time = int(self.timeSelection.testIndex.text()) - 1
        selected_variable = self.input.varBox.currentText().split('(')[0][:-1]

        with Serafin.Read(self.input.ref_filename, self.input.ref_language) as resin:
            resin.header = self.input.ref_header
            resin.time = self.input.ref_time
            ref_values = resin.read_var_in_frame(ref_time, selected_variable)

        with Serafin.Read(self.input.test_filename, self.input.test_language) as resin:
            resin.header = self.input.test_header
            resin.time = self.input.test_time
            test_values = resin.read_var_in_frame(test_time, selected_variable)

        values = test_values - ref_values
        ewsd = []
        for i, j, k in self.input.ref_mesh.triangles:
            ewsd.append(sum(values[[i, j, k]]) * self.input.ref_mesh.area[i, j, k] / 3.0)
        ewsd = np.array(ewsd)
        ewsd *= self.input.ref_mesh.nb_triangles * self.input.ref_mesh.inverse_total_area

        self.updateStats(ref_time, test_time, ewsd)
        self.updateHistogram(ewsd)

    def updateStats(self, ref_time, test_time, ewsd):
        quantile25, median, quantile75 = np.percentile(ewsd, [25, 50, 75])
        self.resultBox.appendPlainText(self.template.format(ref_time+1, test_time+1,
                                                            np.mean(ewsd), np.var(ewsd, ddof=1),
                                                            np.min(ewsd), quantile25, median,
                                                            quantile75, np.max(ewsd)))

    def updateHistogram(self, ewsd):
        weights = np.ones_like(ewsd) / float(len(ewsd))  # make frequency histogram

        self.plotViewer.canvas.axes.clear()
        self.plotViewer.canvas.axes.hist(ewsd, weights=weights)
        self.plotViewer.canvas.axes.set_xlabel(self.plotViewer.current_xlabel)
        self.plotViewer.canvas.axes.set_ylabel(self.plotViewer.current_ylabel)
        self.plotViewer.canvas.axes.set_title(self.plotViewer.current_title)
        self.plotViewer.canvas.draw()


class CompareResultsGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setMinimumWidth(750)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowTitle('Compare two results on identical meshes')

        self.tab = QTabWidget()
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; width: 180px; }')

        self.input = InputTab(self)
        errorEvolutionTab = ErrorEvolutionTab(self.input)
        computeErrorTab = ComputeErrorsTab(self.input)
        errorDistributionTab = ErrorDistributionTab(self.input)

        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(computeErrorTab, 'Compute MSD/MAD/RMSD')
        self.tab.addTab(errorEvolutionTab, 'MAD evolution')
        self.tab.addTab(errorDistributionTab, 'EWSD distribution')
        for i in range(1, 4):
            self.tab.setTabEnabled(i, False)

        self.resultTabs = [errorEvolutionTab, computeErrorTab, errorDistributionTab]

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def reset(self):
        for i, tab in enumerate(self.resultTabs):
            tab.reset()
            self.tab.setTabEnabled(i+1, False)

    def add_reference(self):
        for tab in self.resultTabs:
            tab.add_reference()

    def add_test(self):
        for i, tab in enumerate(self.resultTabs):
            tab.add_test()
            self.tab.setTabEnabled(i+1, True)


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
    widget = CompareResultsGUI()
    widget.show()
    app.exec_()



