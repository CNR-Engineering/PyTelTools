import os
import datetime
import numpy as np
import matplotlib.pyplot as plt
import pandas
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from gui.util import TemporalPlotViewer, PointLabelEditor
from slf.volume import VolumeCalculator


class ConfigureDialog(QDialog):
    def __init__(self, panel, label, check=None):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        if check is None:
            self.check = None
            buttons.accepted.connect(self.accept)
        else:
            self.check = check
            buttons.accepted.connect(self.custom_accept)
        buttons.rejected.connect(self.reject)

        self.message_field = QPlainTextEdit()
        self.message_field.setFixedHeight(50)

        layout = QVBoxLayout()
        layout.addWidget(panel)
        layout.addStretch()
        layout.addWidget(self.message_field)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Configure %s' % label)
        self.resize(500, 400)

    def custom_accept(self):
        value = self.check()
        if value == 2:
            self.accept()
        elif value == 1:
            return
        else:
            self.reject()


class OutputOptionPanel(QWidget):
    def __init__(self, old_options):
        super().__init__()
        folder_box = QGroupBox('Select output folder')
        self.source_folder_button = QRadioButton('Input folder')
        self.another_folder_button = QRadioButton('Another folder')
        self.open_button = QPushButton('Open')
        self.open_button.setEnabled(False)
        self.folder_text = QLineEdit()
        self.folder_text.setReadOnly(True)
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.source_folder_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.another_folder_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.open_button)
        hlayout.addWidget(self.folder_text)
        vlayout.addLayout(hlayout)
        folder_box.setLayout(vlayout)
        self.source_folder_button.toggled.connect(self._toggle_folder)
        self.open_button.clicked.connect(self._open)

        name_box = QGroupBox('Select output name')
        self.suffix_box = QLineEdit()
        self.simple_name_button = QRadioButton('input_name + suffix')
        self.double_name_button = QRadioButton('input_name + job_id + suffix')
        self.simple_name_button.setChecked(True)
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Suffix'))
        hlayout.addWidget(self.suffix_box)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.simple_name_button)
        hlayout.addWidget(self.double_name_button)
        vlayout.addLayout(hlayout)
        name_box.setLayout(vlayout)

        overwrite_box = QGroupBox('Overwrite if file already exists')
        self.overwrite_button = QRadioButton('Yes')
        self.no_button = QRadioButton('No')
        self.no_button.setChecked(True)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.overwrite_button)
        hlayout.addWidget(self.no_button)
        overwrite_box.setLayout(hlayout)

        vlayout = QVBoxLayout()
        vlayout.addWidget(folder_box)
        vlayout.addWidget(name_box)
        vlayout.addWidget(overwrite_box)
        vlayout.addStretch()
        self.setLayout(vlayout)

        self.success = True
        self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = old_options
        self.suffix_box.setText(self.suffix)
        self.folder_text.setText(self.dir_path)
        if not self.in_source_folder:
            self.another_folder_button.setChecked(True)
        else:
            self.source_folder_button.setChecked(True)
        if self.double_name:
            self.double_name_button.setChecked(True)
        if self.overwrite:
            self.overwrite_button.setChecked(True)

    def _toggle_folder(self, source_folder):
        if not source_folder:
            self.double_name_button.setChecked(True)
            self.simple_name_button.setEnabled(False)
            self.open_button.setEnabled(True)
            self.success = False
        else:
            self.simple_name_button.setEnabled(True)
            self.folder_text.clear()
            self.success = True

    def _open(self):
        self.success = False
        w = QFileDialog()
        w.setWindowTitle('Choose the output folder')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            self.dir_path = os.path.join(current_dir, name)
            break
        if not self.dir_path:
            QMessageBox.critical(None, 'Error', 'Choose a folder !',
                                 QMessageBox.Ok)
            return
        self.folder_text.setText(self.dir_path)
        self.success = True

    def check(self):
        if not self.success:
            return 0
        suffix = self.suffix_box.text()
        if len(suffix) < 1:
            QMessageBox.critical(None, 'Error', 'The suffix cannot be empty!',
                                 QMessageBox.Ok)
            return 1
        if not all(c.isalnum() or c == '_' for c in suffix):
            QMessageBox.critical(None, 'Error', 'The suffix should only contain letters, numbers and underscores.',
                                 QMessageBox.Ok)
            return 1
        self.suffix = suffix
        self.in_source_folder = self.source_folder_button.isChecked()
        self.double_name = self.double_name_button.isChecked()
        self.overwrite = self.overwrite_button.isChecked()
        return 2

    def get_options(self):
        return self.suffix, self.in_source_folder, \
               self.dir_path, self.double_name, self.overwrite


class MultiSaveDialog(QDialog):
    def __init__(self, old_options):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        self.panel = OutputOptionPanel(old_options)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.panel)
        layout.addStretch()
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Save multiple files')
        self.resize(500, 400)

    def check(self):
        success_code = self.panel.check()
        if success_code == 2:
            self.accept()
            return
        elif success_code == 1:
            return
        self.reject()


class MultiLoadDialog(QDialog):
    def __init__(self, extension, old_options):
        super().__init__()
        self.extension = extension
        self.dir_paths = []
        self.slf_name = ''
        self.job_ids = []
        self.nb_files = 0

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        self.file_box = QComboBox()
        self.file_box.setFixedHeight(30)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['Folder', 'Job ID'])

        self.open_button = QPushButton('Open', None, icon=QWidget().style().standardIcon(QStyle.SP_DialogOpenButton))
        self.open_button.setFixedSize(100, 50)
        self.open_button.clicked.connect(self._open)

        self.success = False

        if old_options:
            self.dir_paths, self.slf_name, self.job_ids = old_options
            self.nb_files = len(self.dir_paths)
            self.file_box.addItem(self.slf_name)
            self.table.setRowCount(self.nb_files)
            for i, (path, job_id) in enumerate(zip(self.dir_paths, self.job_ids)):
                name = os.path.basename(path)
                name_item, id_item = QTableWidgetItem(name), QTableWidgetItem(job_id)
                name_item.setFlags(Qt.NoItemFlags)
                self.table.setItem(i, 0, name_item)
                self.table.setItem(i, 1, id_item)
            all_slfs = set()
            for path in self.dir_paths:
                slfs = set()
                for f in os.listdir(path):
                    if os.path.isfile(os.path.join(path, f)) and f[-4:] == self.extension:
                        slfs.add(f)
                if not all_slfs:
                    all_slfs = slfs.copy()
                else:
                    all_slfs.intersection_update(slfs)
            all_slfs = list(all_slfs)
            for slf in all_slfs:
                self.file_box.addItem(slf)
            self.file_box.setCurrentIndex(all_slfs.index(self.slf_name))
            self.success = True

        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.open_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Select %s file name' % self.extension[1:]))
        hlayout.addWidget(self.file_box, Qt.AlignRight)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.table)
        vlayout.addWidget(QLabel('Click on the cells to modify Job ID.'), Qt.AlignRight)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Select input files')

    def check(self):
        if not self.success:
            self.reject()
            return
        self.slf_name = self.file_box.currentText()
        self.job_ids = []
        for row in range(self.table.rowCount()):
            job_id = self.table.item(row, 1).text()
            if not job_id:
                QMessageBox.critical(None, 'Error', 'Job ID cannot be empty.',
                                     QMessageBox.Ok)
                return

            if not all(c.isalnum() or c == '_' for c in job_id):
                QMessageBox.critical(None, 'Error', 'Job ID should only contain letters, numbers and underscores.',
                                     QMessageBox.Ok)
                return
            self.job_ids.append(job_id)
        if len(set(self.job_ids)) != len(self.job_ids):
            QMessageBox.critical(None, 'Error', 'Each Job ID must be different!',
                                 QMessageBox.Ok)
            return
        self.accept()

    def _open(self):
        if self.dir_paths:
            msg = QMessageBox.warning(None, 'Confirm load',
                                      'Do you want to re-open source folders?\n(Your current selection will be cleared)',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                return
        self.success = False
        w = QFileDialog()
        w.setWindowTitle('Choose one or more folders')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionMode(QAbstractItemView.MultiSelection)
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        dir_names = []
        self.dir_paths = []
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            dir_names.append(name)
            if os.path.exists(os.path.join(current_dir, name)):
                self.dir_paths.append(os.path.join(current_dir, name))
            else:
                self.dir_paths = [current_dir]
                break
        if not self.dir_paths:
            QMessageBox.critical(None, 'Error', 'Choose at least one folder.',
                                 QMessageBox.Ok)
            return
        all_slfs = set()
        for name, path in zip(dir_names, self.dir_paths):
            slfs = set()
            for f in os.listdir(path):
                if os.path.isfile(os.path.join(path, f)) and f[-4:] == self.extension:
                    slfs.add(f)
            if not slfs:
                QMessageBox.critical(None, 'Error', "The folder %s doesn't have any %s file!" % (name, self.extension),
                                     QMessageBox.Ok)
                self.dir_paths = []
                return
            if not all_slfs:
                all_slfs = slfs.copy()
            else:
                all_slfs.intersection_update(slfs)
            if not all_slfs:
                QMessageBox.critical(None, 'Error',
                                     'These folder do not share identical %s file names!' % self.extension,
                                     QMessageBox.Ok)
                self.dir_paths = []
                return
        self.nb_files = len(dir_names)

        self.file_box.clear()
        for slf in all_slfs:
            self.file_box.addItem(slf)

        self.table.setRowCount(self.nb_files)
        for i, name in enumerate(dir_names):
            filtered_name = ''.join(c for c in name if c.isalnum() or c == '_')
            if not filtered_name:   # please do not name a directory with only special letters :D
                filtered_name = 'default__'
            name_item, id_item = QTableWidgetItem(name), QTableWidgetItem(filtered_name)
            name_item.setFlags(Qt.NoItemFlags)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, id_item)
        self.success = True


class MultiLoadSerafinDialog(MultiLoadDialog):
    def __init__(self, old_options):
        super().__init__('.slf', old_options)


class MultiLoadCSVDialog(MultiLoadDialog):
    def __init__(self, old_options):
        super().__init__('.csv', old_options)


class LoadSerafinDialog(QDialog):
    def __init__(self, old_options):
        super().__init__()
        self.dir_path = ''
        self.slf_name = ''
        self.job_id = ''

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        self.file_box = QComboBox()
        self.file_box.setFixedHeight(30)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['Folder', 'Job ID'])

        self.open_button = QPushButton('Open', None, icon=QWidget().style().standardIcon(QStyle.SP_DialogOpenButton))
        self.open_button.setFixedSize(100, 50)
        self.open_button.clicked.connect(self._open)

        self.success = False

        if old_options[0]:
            self.dir_path, self.slf_name, self.job_id = old_options
            self.table.setRowCount(1)
            name = os.path.basename(self.dir_path)
            name_item, id_item = QTableWidgetItem(name), QTableWidgetItem(self.job_id)
            name_item.setFlags(Qt.NoItemFlags)
            self.table.setItem(0, 0, name_item)
            self.table.setItem(0, 1, id_item)

            slfs = set()
            for f in os.listdir(self.dir_path):
                if os.path.isfile(os.path.join(self.dir_path, f)) and f[-4:] == '.slf':
                    slfs.add(f)

            slfs = list(slfs)
            for slf in slfs:
                self.file_box.addItem(slf)
            self.file_box.setCurrentIndex(slfs.index(self.slf_name))
            self.success = True

        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.open_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Select .slf file name'))
        hlayout.addWidget(self.file_box, Qt.AlignRight)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.table)
        vlayout.addWidget(QLabel('Click on the cells to modify Job ID.'), Qt.AlignRight)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Select input file')

    def check(self):
        if not self.success:
            self.reject()
            return
        self.slf_name = self.file_box.currentText()
        job_id = self.table.item(0, 1).text()
        if not job_id:
            QMessageBox.critical(None, 'Error', 'Job ID cannot be empty.',
                                 QMessageBox.Ok)
            return
        if not all(c.isalnum() or c == '_' for c in job_id):
            QMessageBox.critical(None, 'Error', 'Job ID should only contain letters, numbers and underscores.',
                                 QMessageBox.Ok)
            return
        self.job_id = job_id
        self.accept()

    def _open(self):
        if self.dir_path:
            msg = QMessageBox.warning(None, 'Confirm load',
                                      'Do you want to re-open source folder?\n(Your current selection will be cleared)',
                                      QMessageBox.Ok | QMessageBox.Cancel,
                                      QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                return
        self.success = False
        w = QFileDialog()
        w.setWindowTitle('Choose one or more folders')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        dir_name = ''
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            dir_name = name
            if os.path.exists(os.path.join(current_dir, name)):
                self.dir_path = os.path.join(current_dir, name)
            else:
                self.dir_path = current_dir
            break
        if not self.dir_path:
            QMessageBox.critical(None, 'Error', 'Choose a folder !',
                                 QMessageBox.Ok)
            self.dir_path = ''
            return

        slfs = set()
        for f in os.listdir(self.dir_path):
            if os.path.isfile(os.path.join(self.dir_path, f)) and f[-4:] == '.slf':
                slfs.add(f)
        if not slfs:
            QMessageBox.critical(None, 'Error', "The folder %s doesn't have any .slf file!" % name,
                                 QMessageBox.Ok)
            self.dir_path = ''
            return

        self.file_box.clear()
        for slf in slfs:
            self.file_box.addItem(slf)

        self.table.setRowCount(1)
        filtered_name = ''.join(c for c in dir_name if c.isalnum() or c == '_')
        name_item, id_item = QTableWidgetItem(dir_name), QTableWidgetItem(filtered_name)
        name_item.setFlags(Qt.NoItemFlags)
        self.table.setItem(0, 0, name_item)
        self.table.setItem(0, 1, id_item)
        self.success = True


class VolumePlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('polygon')
        self.csv_separator = ''
        self.var_ID = None
        self.second_var_ID = None
        self.language = 'fr'
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))

        self.current_columns = ('Polygon 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.poly_menu = QMenu('&Polygons', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)
        self.menuBar.addMenu(self.poly_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

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

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        self.data['time'] = np.array(self.data['time'])

        self.start_time = csv_data.metadata['start time']
        self.current_columns = ('Polygon 1',)

        self.var_ID = csv_data.metadata['var']
        self.second_var_ID = csv_data.metadata['second var']

        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = list(self.data)[1:]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSaveVolumeDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                    self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                    self.start_time)
        dlg.exec_()


class FluxPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('section')
        self.csv_separator = ''
        self.language = 'fr'
        self.flux_title = ''
        self.var_IDs = []
        self.cumulative = False
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.cumulative_flux_act = QAction('Show\ncumulative flux', self, checkable=True,
                                           icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.cumulative_flux_act.toggled.connect(self.changeFluxType)

        self.current_columns = ('Section 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.cumulative_flux_act)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.poly_menu = QMenu('&Sections', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)
        self.menuBar.addMenu(self.poly_menu)
        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

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

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        for item in header:
            self.data[item] = np.array(self.data[item])

        self.flux_title = csv_data.metadata['flux title']
        self.start_time = csv_data.metadata['start time']
        self.current_columns = ('Section 1',)

        self.var_IDs = csv_data.metadata['var IDs']
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = list(self.data)[1:]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self.flux_title
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSaveFluxDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                  self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                  self.start_time, self.cumulative)
        dlg.exec_()


class PointPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.csv_separator = ''
        self.language = 'en'
        self.var_IDs = []
        self.current_var = ''
        self.points = None
        self.indices = []
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.select_variable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.current_columns = ('Point 1',)
        self.toolBar.addAction(self.select_variable)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.data_menu = QMenu('&Data', self)
        self.data_menu.addAction(self.select_variable)
        self.data_menu.addSeparator()
        self.data_menu.addAction(self.selectColumnsAct)
        self.data_menu.addAction(self.editColumnNamesAct)
        self.data_menu.addAction(self.editColumColorAct)
        self.menuBar.addMenu(self.data_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

    def _to_column(self, point):
        point_index = int(point.split()[1]) - 1
        x, y = self.points.points[point_index]
        return '%s (%.4f, %.4f)' % (self.current_var, x, y)

    def editColumns(self):
        msg = PointLabelEditor(self.column_labels, self.column_name,
                               self.points.points, [True if i in self.indices else False
                                                    for i in range(len(self.points.points))],
                               self.points.fields_name,
                               self.points.attributes_decoded)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLabels(self.column_labels)
        self.replot()

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

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        for item in header:
            self.data[item] = np.array(self.data[item])

        self.var_IDs = csv_data.metadata['var IDs']
        self.current_var = self.var_IDs[0]
        self.points = csv_data.metadata['points']

        self.start_time = csv_data.metadata['start time']
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.indices = csv_data.metadata['point indices']
        self.columns = ['Point %d' % (i+1) for i in self.indices]
        self.current_columns = self.columns[0:1]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSavePointDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                   self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                   self.start_time, [self._to_column(p) for p in self.current_columns])
        dlg.exec_()


class MultiSaveTemporalPlotDialog(QDialog):
    def __init__(self, name, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time):
        super().__init__()
        self.name = name
        self.separator = separator
        self.filenames = []
        self.dir_paths = []
        self.csv_name = ''
        self.job_ids = []
        self.data = []
        self.out_names = []

        self.current_columns = current_columns
        self.column_labels = column_labels
        self.column_colors = column_colors
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.title = title
        self.time_format = time_format
        self.start_time = start_time

        self.stack = QStackedLayout()
        self.stack.addWidget(self.build_first_page())
        self.stack.addWidget(self.build_second_page())
        self.stack.addWidget(self.build_third_page())
        self.setLayout(self.stack)
        self.setWindowTitle('Save figures for multiple CSV results of %s' % self.name)

    def build_first_page(self):
        first_page = QWidget()
        source_box = QGroupBox('Where are the CSV results of %s' % self.name)
        self.same_button = QRadioButton('In the same folder')
        self.different_button = QRadioButton('In different folder under the same name')
        self.different_button.setChecked(True)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.same_button)
        vlayout.addWidget(self.different_button)
        source_box.setLayout(vlayout)
        next_button = QPushButton('Next')
        cancel_button = QPushButton('Cancel')
        for bt in (next_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(next_button)
        hlayout.addWidget(cancel_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(source_box)
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        first_page.setLayout(vlayout)

        next_button.clicked.connect(self.turn_page)
        cancel_button.clicked.connect(self.reject)
        return first_page

    def build_second_page(self):
        second_page = QWidget()
        back_button = QPushButton('Back')
        ok_button = QPushButton('OK')
        for bt in (back_button, ok_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(back_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('All figures will have the same names as the CSV files'))
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        second_page.setLayout(vlayout)

        back_button.clicked.connect(self.back)
        ok_button.clicked.connect(self.run)
        return second_page

    def build_third_page(self):
        third_page = QWidget()
        self.output_panel = OutputOptionPanel(['_plot', True, '', '', True])
        self.output_panel.no_button.setEnabled(False)
        back_button = QPushButton('Back')
        ok_button = QPushButton('OK')
        for bt in (back_button, ok_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(back_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.output_panel)
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        third_page.setLayout(vlayout)

        back_button.clicked.connect(self.back)
        ok_button.clicked.connect(self.run)
        return third_page

    def back(self):
        self.stack.setCurrentIndex(0)

    def turn_page(self):
        if self.same_button.isChecked():
            filenames, _ = QFileDialog.getOpenFileNames(None, 'Open CSV files', '', 'CSV Files (*.csv)',
                                                        options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
            if not filenames:
                self.reject()
            self.filenames = filenames
            for csv_name in self.filenames:
                success, data = self.read(csv_name)
                if not success:
                    QMessageBox.critical(None, 'Error', 'The file %s is not valid.' % os.path.split(csv_name)[1],
                                         QMessageBox.Ok)
                    return
                self.data.append(data)
                self.out_names.append(csv_name[:-4] + '.png')
            self.stack.setCurrentIndex(1)
        else:
            dlg = MultiLoadCSVDialog([])
            if dlg.exec_() == QDialog.Accepted:
                self.dir_paths, self.csv_name, self.job_ids = dlg.dir_paths, dlg.slf_name, dlg.job_ids
            else:
                self.reject()
            for path in self.dir_paths:
                success, data = self.read(os.path.join(path, self.csv_name))
                if not success:
                    QMessageBox.critical(None, 'Error', 'The file in %s is not valid.' % os.path.basename(path),
                                         QMessageBox.Ok)
                    return
                self.data.append(data)
            self.stack.setCurrentIndex(2)

    def run(self):
        if not self.out_names:
            suffix, in_source_folder, dir_path, double_name, _ = self.output_panel.get_options()

            for path, job_id in zip(self.dir_paths, self.job_ids):
                if double_name:
                    output_name = self.csv_name[:-4] + '_' + job_id + suffix + '.png'
                else:
                    output_name = self.csv_name[:-4] + suffix + '.png'
                if in_source_folder:
                    filename = os.path.join(path, output_name)
                else:
                    filename = os.path.join(dir_path, output_name)
                self.out_names.append(filename)

        self.plot()
        QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                QMessageBox.Ok)
        self.accept()

    def read(self, csv_file):
        try:
            data = pandas.read_csv(csv_file, header=0, sep=self.separator)
            if 'time' not in list(data):
                return False, []
            if not all(p in list(data) for p in self.current_columns):
                return False, []
            value_datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), data['time']))
            str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), value_datetime))
            str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), value_datetime))
            time = [data['time'], data['time'], data['time'],
                    data['time'] / 60, data['time'] / 3600, data['time'] / 86400]
            return True, [data, time, str_datetime, str_datetime_bis]
        except:
            return False, []

    def plot(self):
        pass


class MultiSaveVolumeDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time):
        super().__init__('Compute Volume', separator, current_columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for column in self.current_columns:
                axes.plot(time[self.time_format], data[column], '-', color=self.column_colors[column],
                          linewidth=2, label=self.column_labels[column])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)


class MultiSaveFluxDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, cumulative):
        super().__init__('Compute Flux', separator, current_columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.cumulative = cumulative

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for column in self.current_columns:
                if not self.cumulative:
                    axes.plot(time[self.time_format], data[column], '-',
                              color=self.column_colors[column], linewidth=2, label=self.column_labels[column])
                else:
                    axes.plot(time[self.time_format], np.cumsum(data[column]), '-',
                              color=self.column_colors[column], linewidth=2, label=self.column_labels[column])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)


class MultiSavePointDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, columns):
        super().__init__('Interpolate on Points', separator, columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.current_points = current_columns

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for point, column in zip(self.current_points, self.current_columns):
                axes.plot(time[self.time_format], data[column], '-',
                          color=self.column_colors[point], linewidth=2, label=self.column_labels[point])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)


class MultiPlotDialog(QDialog):
    def __init__(self, parent, name, tasks, input_options, output_options, compute_options):
        super().__init__()
        self.parent = parent
        self.compute_options = compute_options

        self.table = QTableWidget()
        self.table.setRowCount(len(input_options[0]))
        self.table.setColumnCount(len(tasks)+1)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['Job'] + tasks)

        self.red = QColor(255, 160, 160, 255)
        self.green = QColor(180, 250, 165, 255)
        yellow = QColor(245, 255, 207, 255)

        for i, path in enumerate(input_options[0]):
            name = os.path.basename(path)
            self.table.setItem(i, 0, QTableWidgetItem(name))
            for j in range(1, 4):
                self.table.setItem(i, j, QTableWidgetItem(''))
                self.table.item(i, j).setBackground(yellow)

        self.btnClose = QPushButton('Close', None)
        self.btnClose.setEnabled(False)
        self.btnClose.setFixedSize(120, 30)
        self.btnClose.clicked.connect(self.accept)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Wait until all yellow cells turn green'))
        vlayout.addWidget(self.table)
        vlayout.addStretch()
        vlayout.addWidget(self.btnClose, Qt.AlignRight)
        self.setLayout(vlayout)
        self.resize(500, 300)
        self.setWindowTitle('Multi-Save %s' % name)
        self.show()
        QApplication.processEvents()
        self.btnClose.setEnabled(True)

        # process IO options
        self.dir_paths, self.slf_name, self.job_ids = input_options
        self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = output_options
        self.png_names = []
        for path, job_id in zip(self.dir_paths, self.job_ids):
            if self.double_name:
                output_name = self.slf_name[:-4] + '_' + job_id + self.suffix + '.png'
            else:
                output_name = self.slf_name[:-4] + self.suffix + '.png'
            if self.in_source_folder:
                filename = os.path.join(path, output_name)
            else:
                filename = os.path.join(self.dir_path, output_name)
            self.png_names.append(filename)

    def fail(self, i, j):
        self.table.item(i, j).setBackground(self.red)
        QApplication.processEvents()

    def success(self, i, j):
        self.table.item(i, j).setBackground(self.green)
        QApplication.processEvents()


class MultiSaveMultiVarLinePlotDialog(MultiPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'MultiVar Line Plot', ['Load Serafin', 'Interpolation', 'Export PNG'],
                         input_options, output_options, compute_options)

    def run(self):
        line_id, time_index, current_vars = self.compute_options
        nb_success = 0
        for i, (dir_path, job_id, png_name) in enumerate(zip(self.dir_paths, self.job_ids, self.png_names)):
            # Load Serafin
            input_name = os.path.join(dir_path, self.slf_name)
            input_data = self.parent.open(job_id, input_name)
            if input_data is None:
                self.fail(i, 1)
                continue
            # check time
            if time_index >= len(input_data.time):
                self.fail(i, 1)
                continue
            # check variables
            failed = False
            for var in current_vars:
                if var not in input_data.header.var_IDs:
                    self.fail(i, 1)
                    failed = True
            if failed:
                continue
            self.success(i, 1)

            # Interpolation
            success, line_interpolators, line_interpolators_internal = self.parent.interpolate(input_data)
            if not success:
                self.fail(i, 2)
                continue
            self.success(i, 2)

            # Export PNG
            line_interpolator, distances = line_interpolators[line_id]
            line_interpolator_internal, distances_internal = line_interpolators_internal[line_id]

            values, values_internal = self.parent.compute(time_index, input_data,
                                                          line_interpolator, line_interpolator_internal, current_vars)
            self.parent.plot(values, distances, values_internal, distances_internal, current_vars, png_name)
            self.success(i, 3)
            nb_success += 1

        if nb_success == len(self.dir_paths):
            QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                    QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Failed', 'Failed to produce all figures.',
                                    QMessageBox.Ok)
        self.btnClose.setEnabled(True)


class MultiSaveMultiFrameLinePlotDialog(MultiPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'MultiVar Frame Plot', ['Load Serafin', 'Interpolation', 'Export PNG'],
                         input_options, output_options, compute_options)

    def run(self):
        line_id, current_var, time_indices = self.compute_options
        nb_success = 0
        for i, (dir_path, job_id, png_name) in enumerate(zip(self.dir_paths, self.job_ids, self.png_names)):
            # Load Serafin
            input_name = os.path.join(dir_path, self.slf_name)
            input_data = self.parent.open(job_id, input_name)
            if input_data is None:
                self.fail(i, 1)
                continue
            # check variable
            if current_var not in input_data.header.var_IDs:
                self.fail(i, 1)
                continue
            # check time
            failed = False
            for time_index in time_indices:
                if time_index not in input_data.selected_time_indices:
                    self.fail(i, 1)
                    failed = True
            if failed:
                continue
            self.success(i, 1)

            # Interpolation
            success, line_interpolators, line_interpolators_internal = self.parent.interpolate(input_data)
            if not success:
                self.fail(i, 2)
                continue
            self.success(i, 2)

            # Export PNG
            line_interpolator, distances = line_interpolators[line_id]
            line_interpolator_internal, distances_internal = line_interpolators_internal[line_id]

            values, values_internal = self.parent.compute(input_data, line_interpolator, line_interpolator_internal,
                                                          current_var, time_indices)
            self.parent.plot(values, distances, values_internal, distances_internal, time_indices, png_name)
            self.success(i, 3)
            nb_success += 1

        if nb_success == len(self.dir_paths):
            QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                    QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Failed', 'Failed to produce all figures.',
                                    QMessageBox.Ok)
        self.btnClose.setEnabled(True)


class MultiSaveProjectLinesDialog(MultiPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'Project Lines', ['Load Serafin', 'Interpolation', 'Export PNG'],
                         input_options, output_options, compute_options)

    def run(self):
        reference, max_distance, time_index, current_vars = self.compute_options
        nb_success = 0
        for i, (dir_path, job_id, png_name) in enumerate(zip(self.dir_paths, self.job_ids, self.png_names)):
            # Load Serafin
            input_name = os.path.join(dir_path, self.slf_name)

            input_data = self.parent.open(job_id, input_name)
            if input_data is None:
                self.fail(i, 1)
                continue
             # check time
            if time_index >= len(input_data.time):
                self.fail(i, 1)
                continue
            # check variables
            failed = False
            for line_id, variables in current_vars.items():
                for var in variables:
                    if var not in input_data.header.var_IDs:
                        self.fail(i, 1)
                        failed = True
            if failed:
                continue
            self.success(i, 1)

            # Interpolation
            success, all_lines, all_lines_internal = self.parent.interpolate(input_data)
            if not success:
                self.fail(i, 2)
                continue
            self.success(i, 2)

            # Export PNG
            distances, values, distances_internal, values_internal = self.parent.compute(reference, max_distance,
                                                                                         time_index, input_data,
                                                                                         all_lines, all_lines_internal)
            self.parent.plot(values, distances, values_internal, distances_internal, current_vars, png_name)
            self.success(i, 3)
            nb_success += 1

        if nb_success == len(self.dir_paths):
            QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                    QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Failed', 'Failed to produce all figures.',
                                    QMessageBox.Ok)
        self.btnClose.setEnabled(True)


class VerticalProfilePlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.data = None
        self.current_var = ''
        self.points = []

        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.select_variable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.current_columns = ('Point 1',)
        self.toolBar.addAction(self.select_variable)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.data_menu = QMenu('&Data', self)
        self.data_menu.addAction(self.select_variable)
        self.data_menu.addAction(self.selectColumnsAct)
        self.menuBar.addMenu(self.data_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

    def _defaultTitle(self):
        word = {'fr': 'de', 'en': 'of'}[self.data.header.language]
        return 'Values %s %s' % (word, self.current_var)

    def _defaultYLabel(self):
        return {'fr': 'Cote Z', 'en': 'Elevation Z'}[self.data.header.language]

    def selectVariableEvent(self):
        msg = QDialog()
        combo = QComboBox()
        for var in self.data.header.var_IDs:
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
        pass

    def multi_save(self):
        pass

    def get_data(self, data, points):
        pass
