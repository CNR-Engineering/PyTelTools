import sys
import os
import logging
import copy
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pandas as pd
import matplotlib.pyplot as plt
from slf import Serafin
from slf.volume import VolumeCalculator
from geom import BlueKenue, Shapefile
from gui.util import PlotViewer, QPlainTextEditLogger


class VolumeCalculatorGUI(QThread):
    tick = pyqtSignal(int, name='changed')

    def __init__(self, volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                 time_sampling_frequency=1):
        super().__init__()

        self.calculator = VolumeCalculator(volume_type, var_ID, second_var_ID, input_stream, polynames, polygons,
                                           time_sampling_frequency)

    def run_calculator(self):
        self.tick.emit(6)
        QApplication.processEvents()
        self.calculator.construct_triangles()
        self.tick.emit(15)
        QApplication.processEvents()
        self.calculator.construct_weights()
        self.tick.emit(30)
        QApplication.processEvents()
        logging.info('Finished processing the mesh')

        result = []
        init_values = None
        if self.calculator.second_var_ID == VolumeCalculator.INIT_VALUE:
            init_values = self.calculator.input_stream.read_var_in_frame(0, self.calculator.var_ID)

        for i, i_time in enumerate(self.calculator.time):
            i_result = [str(i_time)]

            values = self.calculator.input_stream.read_var_in_frame(i, self.calculator.var_ID)
            if self.calculator.second_var_ID is not None:
                if self.calculator.second_var_ID == VolumeCalculator.INIT_VALUE:
                    values -= init_values
                else:
                    second_values = self.calculator.input_stream.read_var_in_frame(i, self.calculator.second_var_ID)
                    values -= second_values

            for j in range(len(self.calculator.polygons)):
                weight = self.calculator.weights[j]
                volume = self.calculator.volume_in_frame_in_polygon(weight, values, self.calculator.polygons[j])
                if self.calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append(str(v))
                else:
                    i_result.append(str(volume))
            result.append(i_result)

            self.tick.emit(30 + int(70 * (i+1) / len(self.calculator.time)))
        return result

    def write_csv(self, output_stream):
        result = self.run_calculator()
        self.calculator.write_csv(result, output_stream)


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

    def connectToCalculator(self, thread):
        thread.tick.connect(self.setValue)


class PlotColumnsSelector(QDialog):
    def __init__(self, columns, current_columns):
        super().__init__()

        self.list = QListWidget()
        for name in columns:
            if name == 'time':
                continue
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
        vlayout.addWidget(QLabel('  Select up to 5 columns to plot'))
        vlayout.addWidget(self.list)
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)

        self.resize(self.sizeHint())
        self.setWindowTitle('Select columns to plot')

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
            QMessageBox.critical(self, 'Error', 'Select at least one column to plot.',
                                 QMessageBox.Ok)
            return
        if len(self.selection) > 5:
            QMessageBox.critical(self, 'Error', 'Select up to 5 columns.',
                                 QMessageBox.Ok)
            return
        self.accept()


class VolumePlotViewer(PlotViewer):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Visualize the temporal evolution of volumes')

        self.data = None
        self.datetime = []
        self.var_ID = None
        self.second_var_ID = None

        # initialize graphical parameters
        self.show_date = False
        self.current_columns = ('Polygon 1',)
        self.current_xlabel = None
        self.current_ylabel = None
        self.current_title = ''
        self.current_size = (8.0, 6.0)

        icons = self.style().standardIcon
        self.selectColumnsAct = QAction('Select columns', self, icon=icons(QStyle.SP_FileDialogDetailedView),
                                        triggered=self.selectColumns)

        self.convertTimeAct = QAction('Show date/time', self, checkable=True,
                                      icon=icons(QStyle.SP_DialogApplyButton))
        self.convertTimeAct.changed.connect(self.convertTime)

        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

    def _defaultXLabel(self, language):
        if language == 'fr':
            return 'Temps (seconde)'
        return 'Time (second)'

    def _defaultYLabel(self, language):
        word = {'fr': 'de', 'en': 'of'}[language]
        if self.second_var_ID == VolumeCalculator.INIT_VALUE:
            return 'Volume %s (%s - %s$_0$)' % (word, self.var_ID, self.var_ID)
        elif self.second_var_ID is None:
            return 'Volume %s %s' % (word, self.var_ID)
        return 'Volume %s (%s - %s)' % (word, self.var_ID, self.second_var_ID)

    def getData(self):
        csv_file = self.parent.csvNameBox.text()
        self.data = pd.read_csv(csv_file, header=0, sep=';')
        # put tmp figure in the same folder as the result file
        result_folder, _ = os.path.split(csv_file)
        self.figName = os.path.join(result_folder, self.figName)

        self.var_ID = self.parent.var_ID
        self.second_var_ID = self.parent.second_var_ID
        if self.parent.header.date is not None:
            year, month, day, hour, minute, second = self.parent.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)
        self.datetime = map(lambda x: start_time + datetime.timedelta(seconds=x), self.data['time'])
        self.datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.current_xlabel = self._defaultXLabel(self.parent.language)
        self.current_ylabel = self._defaultYLabel(self.parent.language)

    def selectColumns(self):
        msg = PlotColumnsSelector(list(self.data), self.current_columns)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        selection = msg.selection
        self.updateImage(columns=selection)

    def convertTime(self):
        self.updateImage(show_date=not self.show_date)
        if self.show_date:
            self.xLabelAct.setEnabled(False)
        else:
            self.xLabelAct.setEnabled(True)

    def changeTitle(self):
        value, ok = QInputDialog.getText(self, 'Change title',
                                         'Enter a new title', text=self.current_title)
        if not ok:
            return
        self.updateImage(title=value)

    def changeXLabel(self):
        value, ok = QInputDialog.getText(self, 'Change X label',
                                         'Enter a new X label', text=self.current_xlabel)
        if not ok:
            return
        self.updateImage(xlabel=value)

    def changeYLabel(self):
        value, ok = QInputDialog.getText(self, 'Change Y label',
                                         'Enter a new Y label', text=self.current_ylabel)
        if not ok:
            return
        self.updateImage(ylabel=value)

    def changeSize(self):
        value, ok = QInputDialog.getText(self, 'Change figure size',
                                         'Enter a new figure size (separated by comma)',
                                         text=', '.join(map(str, self.current_size)))
        if not ok:
            return
        try:
            new_size = tuple(map(float, value.split(',')))
        except ValueError:
            QMessageBox.critical(self, 'Error', 'Invalid input.',
                                 QMessageBox.Ok)
            return
        self.updateImage(size=new_size)

    def updateImage(self, show_date=None, columns=None, xlabel=None, ylabel=None, title=None, size=None):
        if columns is None:
            columns = self.current_columns
        if ylabel is None:
            ylabel = self.current_ylabel
        if xlabel is None:
            xlabel = self.current_xlabel
        if title is None:
            title = self.current_title
        if show_date is None:
            show_date = self.show_date
        if size is None:
            size = self.current_size

        fig = plt.gcf()
        ax = plt.gca()
        for color, column in zip(self.defaultColors[:len(columns)], columns):
            plt.plot(self.data['time'], self.data[column], '-', color=color, linewidth=2, label=column)

        plt.ylabel(ylabel)
        if show_date:
            datenames = plt.setp(ax, xticklabels=self.datetime)
            plt.setp(datenames, rotation=45, fontsize=8)
        else:
            plt.xlabel(xlabel)
        plt.title(title)
        plt.legend()
        plt.tight_layout()
        fig.set_size_inches(size[0], size[1])
        plt.savefig(self.figName, dpi=100)
        fig.clear()

        self.show_date = show_date
        self.current_columns = columns
        self.current_xlabel = xlabel
        self.current_ylabel = ylabel
        self.current_title = title
        self.current_size = size
        self.openImage(QImage(self.figName))

    def closeEvent(self, event):
        os.remove(self.figName)
        self.parent.setEnabled(True)
        self.parent.setWindowFlags(self.parent.windowFlags() | Qt.WindowCloseButtonHint)
        self.parent.show()
        event.accept()


class ComputeVolumeGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.header = None
        self.language = 'fr'
        self.time = []
        self.polygons = []
        self.var_ID = None
        self.second_var_ID = None

        self._initWidgets()  # some instance attributes will be set there
        self._setLayout()
        self._bindEvents()

        self.setFixedWidth(750)
        self.setMaximumHeight(750)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowTitle('Compute and visualize volumes inside polygons')

    def _initWidgets(self):
        # create a checkbox for language selection
        self.langBox = QGroupBox('Input language')
        self.langBox.setFixedHeight(50)
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.frenchButton.setChecked(True)

        # create the button open Serafin
        self.btnOpenSerafin = QPushButton('Load Serafin', self)
        self.btnOpenSerafin.setToolTip('<b>Open</b> a .slf file')
        self.btnOpenSerafin.setFixedSize(105, 50)

        # create the button open Polygon
        self.btnOpenPolygon = QPushButton('Load Polygons', self)
        self.btnOpenPolygon.setToolTip('<b>Open</b> a .i2s or .shp file')
        self.btnOpenPolygon.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.serafinNameBox = QLineEdit()
        self.serafinNameBox.setReadOnly(True)
        self.serafinNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.polygonNameBox = QLineEdit()
        self.polygonNameBox.setReadOnly(True)
        self.polygonNameBox.setFixedHeight(30)
        self.csvNameBox = QLineEdit()
        self.csvNameBox.setReadOnly(True)
        self.csvNameBox.setFixedHeight(30)

        # create combo box widgets for choosing variables
        self.firstVarBox = QComboBox()
        self.firstVarBox.setFixedSize(400, 30)
        self.secondVarBox = QComboBox()
        self.secondVarBox.setFixedSize(400, 30)

        # create the check for selecting superior volume
        self.supVolumeBox = QCheckBox('Compute positive volumes (slow)', self)

        # create the submit button
        self.btnSubmit = QPushButton('Submit\n(export to .csv)', self)
        self.btnSubmit.setFixedSize(105, 50)

        # create the button for opening the image viewer
        self.btnImage = QPushButton('Visualize results', self)
        self.btnImage.setFixedSize(135, 50)
        self.btnImage.setEnabled(False)

        # create the image viewer
        self.img = VolumePlotViewer(self)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _bindEvents(self):
        self.btnOpenSerafin.clicked.connect(self.btnOpenSerafinEvent)
        self.btnOpenPolygon.clicked.connect(self.btnOpenPolygonEvent)
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.btnImage.clicked.connect(self.btnImageEvent)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpenSerafin)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Input file'))
        hlayout.addWidget(self.serafinNameBox)

        mainLayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Summary'))
        hlayout.addWidget(self.summaryTextBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 20))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpenPolygon)
        hlayout.addWidget(self.polygonNameBox)
        mainLayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        lb = QLabel('     Select the principal variable')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addWidget(self.firstVarBox)
        hlayout.setAlignment(self.firstVarBox, Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        lb = QLabel('     Select a variable to subtract (optional)')
        hlayout.addWidget(lb)
        hlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addWidget(self.secondVarBox)
        hlayout.setAlignment(self.secondVarBox, Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        mainLayout.addWidget(self.supVolumeBox)
        mainLayout.setAlignment(self.supVolumeBox, Qt.AlignHCenter)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.csvNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addWidget(self.btnImage)
        mainLayout.setAlignment(self.btnImage, Qt.AlignHCenter)
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def closeEvent(self, event):
        if self.parent is not None:
            self.parent.closeVolume()
        event.accept()

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
                return None
            return True
        return False

    def _reinitInput(self, filename):
        self.filename = filename
        self.serafinNameBox.setText(filename)
        self.summaryTextBox.clear()
        self.csvNameBox.clear()
        self.header = None
        self.time = []
        self.firstVarBox.clear()
        self.secondVarBox.clear()
        self.csvNameBox.clear()
        self.btnImage.setEnabled(False)

        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'

    def btnOpenSerafinEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf);;All Files (*)', QDir.currentPath(), options=options)
        if not filename:
            return

        self._reinitInput(filename)

        with Serafin.Read(self.filename, self.language) as resin:
            resin.read_header()

            # check if the file is 2D
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return
            # record the time series
            resin.get_time()

            # update the file summary
            self.summaryTextBox.appendPlainText(resin.get_summary())

            # copy to avoid reading the same data in the future
            self.header = copy.deepcopy(resin.header)
            self.time = resin.time[:]

        self.secondVarBox.addItem('0')
        self.secondVarBox.addItem('Initial values of the first variable')

        for var_ID, var_name in zip(self.header.var_IDs, self.header.var_names):
            self.firstVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())
            self.secondVarBox.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())

    def btnOpenPolygonEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .i2s or .shp file', '',
                                                  'Line sets (*.i2s);;Shapefile (*.shp);;All Files (*)', options=options)
        if not filename:
            return
        is_i2s = filename[-4:] == '.i2s'
        is_shp = filename[-4:] == '.shp'

        if not is_i2s and not is_shp:
            QMessageBox.critical(self, 'Error', 'Only .i2s and .shp file formats are currently supported.',
                                 QMessageBox.Ok)
            return

        self.polygonNameBox.clear()
        self.polygonNameBox.setText(filename)
        self.polygons = []
        self.csvNameBox.clear()
        self.btnImage.setEnabled(False)

        if is_i2s:
            with BlueKenue.Read(filename) as f:
                f.read_header()
                for poly_name, poly in f:
                    self.polygons.append(poly)
        else:
            for polygon in Shapefile.read_shp(filename):
                self.polygons.append(polygon)

        logging.info('Finished reading the polygon file %s' % filename)

    def btnSubmitEvent(self):
        if not self.polygons or self.header is None:
            return

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        options |= QFileDialog.DontConfirmOverwrite
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  'CSV Files (*.csv)', options=options)

        # check the file name consistency
        if not filename:
            return
        if len(filename) < 5 or filename[-4:] != '.csv':
            filename += '.csv'
        overwrite = self._handleOverwrite(filename)
        if overwrite is None:
            return

        self.csvNameBox.setText(filename)
        logging.info('Writing the output to %s' % filename)

        # disable close button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()

        # initialize the progress bar
        progressBar = OutputProgressDialog()

        # do the calculations
        self.var_ID = self.firstVarBox.currentText().split('(')[0][:-1]
        self.second_var_ID = self.secondVarBox.currentText()
        if self.second_var_ID == '0':
            self.second_var_ID = None
        elif '(' in self.second_var_ID:
            self.second_var_ID = self.second_var_ID.split('(')[0][:-1]
        else:
            self.second_var_ID = VolumeCalculator.INIT_VALUE

        names = ['Polygon %d' % (i+1) for i in range(len(self.polygons))]

        with Serafin.Read(self.filename, self.language) as resin:
            resin.header = self.header
            resin.time = self.time
            if self.supVolumeBox.isChecked():
                calculator = VolumeCalculatorGUI(VolumeCalculator.POSITIVE, self.var_ID, self.second_var_ID,
                                                 resin, names, self.polygons)
            else:
                calculator = VolumeCalculatorGUI(VolumeCalculator.NET, self.var_ID, self.second_var_ID,
                                                 resin, names, self.polygons)

            progressBar.setValue(5)
            QApplication.processEvents()
            progressBar.connectToCalculator(calculator)

            with open(filename, 'w') as f2:
                calculator.write_csv(f2)

        logging.info('Finished writing the output')
        progressBar.setValue(100)
        progressBar.cancelButton.setEnabled(True)
        progressBar.exec_()

        # enable close button
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

        # unlock the image viewer
        self.btnImage.setEnabled(True)
        self.img.getData()

    def btnImageEvent(self):
        self.setEnabled(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()
        self.img.updateImage()
        self.img.show()


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
    widget = ComputeVolumeGUI()
    widget.show()
    app.exec_()
