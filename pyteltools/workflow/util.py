import datetime
import numpy as np
import os
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib import cm
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='matplotlib')

from pyteltools.conf import settings
from pyteltools.gui.util import FluxPlotViewer, MapCanvas, PointLabelEditor, PointPlotViewer, PlotViewer, \
    read_csv, SimpleTimeDateSelection, TemporalPlotViewer, VolumePlotViewer
from pyteltools.slf.datatypes import SerafinData
from pyteltools.slf.interpolation import MeshInterpolator
from pyteltools.slf import Serafin
from pyteltools.utils.cli import new_logger


EPS_VALUE = 0.001  # Relative tolerance (of 0.1%) above which min and max are modified to avoid a crash of colormap [#2]


logger = new_logger(__name__)


def build_levels_from_minmax(min_input, max_input):
    """!
    @brief: Build uniform levels and modify min and max values if they are not equal
    @param min_input <float>: minimum value
    @param max_input <float>: maximum value
    @return <numpy.1D-array>
    """
    min_value = min(min_input, max_input * (1 - EPS_VALUE))
    max_value = max(max_input, min_input * (1 + EPS_VALUE))
    # Handle special case where min and max are equal to 0
    if min_value == 0: min_value = -EPS_VALUE
    if max_value == 0: max_value = EPS_VALUE
    return np.linspace(min_value, max_value, settings.NB_COLOR_LEVELS)


def process_output_options(input_file, job_id, extension, suffix, in_source_folder, dir_path, double_name):
    input_path, input_name = os.path.split(input_file)
    input_rootname = os.path.splitext(input_name)[0]
    if double_name:
        output_name = input_rootname + '_' + job_id + suffix + extension
    else:
        output_name = input_rootname + suffix + extension
    if in_source_folder:
        filename = os.path.join(input_path, output_name)
    else:
        filename = os.path.join(dir_path, output_name)
    return filename


def process_geom_output_options(input_file, job_id, extension, suffix, in_source_folder, dir_path, double_name):
    input_path, input_name = os.path.split(input_file)
    input_rootname = os.path.splitext(input_name)[0]
    if double_name:
        output_name = input_rootname + '_' + job_id + suffix + extension
    else:
        output_name = input_rootname + suffix + extension
    if in_source_folder:
        path = os.path.join(input_path, 'gis')
        if not os.path.exists(path):
            os.mkdir(path)
        filename = os.path.join(path, output_name)
    else:
        filename = os.path.join(dir_path, output_name)
    return filename


def process_vtk_output_options(input_file, job_id, time_index, suffix, in_source_folder, dir_path, double_name):
    input_path, input_name = os.path.split(input_file)
    input_rootname = os.path.splitext(input_name)[0]
    if double_name:
        output_name = input_rootname + '_' + job_id + suffix + '_' + str(time_index) + '.vtk'
    else:
        output_name = input_rootname + suffix + '_' + str(time_index) + '.vtk'
    if in_source_folder:
        path = os.path.join(input_path, 'vtk')
        if not os.path.exists(path):
            os.mkdir(path)
        filename = os.path.join(path, output_name)
    else:
        filename = os.path.join(dir_path, output_name)
    return filename


def validate_output_options(options):
    suffix = options[0]
    in_source_folder = bool(int(options[1]))
    dir_path = options[2]
    double_name = bool(int(options[3]))
    overwrite = bool(int(options[4]))
    if not in_source_folder:
        if not os.path.exists(dir_path):
            return False, ('', True, '', False, True)
    return True, (suffix, in_source_folder, dir_path, double_name, overwrite)


def validate_input_options(options):
    filename = options[0]
    if not filename:
        return False, ''
    try:
        with open(filename) as f:
            pass
    except FileNotFoundError:
        return False, ''
    return True, filename


class ConfigureDialog(QDialog):
    """!
    Configuration window for a single node/tool
    """
    def __init__(self, panel, label, check=None):
        """!
        @param panel <PyQt5.QtWidgets.QWidget>: configuration widget
        @param label <str>: tool label for window title
        """
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
        self.resize(550, 400)

    def custom_accept(self):
        value = self.check()
        if value == 2:
            self.accept()
        elif value == 1:
            return
        else:
            self.reject()


class OutputOptionPanel(QWidget):
    """!
    Options panel for output files
    """
    def __init__(self, old_options):
        super().__init__()
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.get_folder_box())
        vlayout.addWidget(self.get_name_box())
        vlayout.addWidget(self.get_overwrite_box())
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

    def get_folder_box(self):
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
        return folder_box

    def get_name_box(self):
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
        return name_box

    def get_overwrite_box(self):
        overwrite_box = QGroupBox('Overwrite if file already exists')
        self.overwrite_button = QRadioButton('Yes')
        self.no_button = QRadioButton('No')
        self.no_button.setChecked(True)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.overwrite_button)
        hlayout.addWidget(self.no_button)
        overwrite_box.setLayout(hlayout)
        return overwrite_box

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


class GeomOutputOptionPanel(OutputOptionPanel):
    def __init__(self, old_options):
        super().__init__(old_options)
        self.source_folder_button.setText('Input_folder/gis')
        self.source_folder_button.setEnabled(True)


class VtkOutputOptionPanel(OutputOptionPanel):
    def __init__(self, old_options):
        super().__init__(old_options)
        self.source_folder_button.setText('Input_folder/vtk')
        self.simple_name_button.setText('input_name + suffix + time')
        self.double_name_button.setText('input_name + job_id + suffix + time')
        for bt in (self.source_folder_button, self.simple_name_button, self.double_name_button):
            bt.setEnabled(True)


class MultiSaveDialog(QDialog):
    def __init__(self, suffix):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        self.panel = OutputOptionPanel([suffix, True, '', False, False])

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


class MultiFigureSaveDialog(MultiSaveDialog):
    def __init__(self, suffix):
        super().__init__(suffix)
        self.panel.overwrite_button.setChecked(True)
        self.panel.no_button.setEnabled(False)


class MultiLoadDialog(QDialog):
    def __init__(self, file_format, extensions, old_options):
        super().__init__()
        self.file_format = file_format
        self.extensions = extensions
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
                    if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1] in self.extensions:
                        slfs.add(f)
                if not all_slfs:
                    all_slfs = slfs.copy()
                else:
                    all_slfs.intersection_update(slfs)
            all_slfs = list(all_slfs)
            all_slfs.sort()
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
        hlayout.addWidget(QLabel('Select %s file name' % self.file_format))
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
                QMessageBox.critical(None, 'Error', 'Job ID cannot be empty.', QMessageBox.Ok)
                return

            if not all(c.isalnum() or c == '_' for c in job_id):
                QMessageBox.critical(None, 'Error', 'Job ID should only contain letters, numbers and underscores.',
                                     QMessageBox.Ok)
                return
            self.job_ids.append(job_id)
        if len(set(self.job_ids)) != len(self.job_ids):
            QMessageBox.critical(None, 'Error', 'Each Job ID must be different!', QMessageBox.Ok)
            return
        self.accept()

    def _open(self):
        if self.dir_paths:
            msg = QMessageBox.warning(None, 'Confirm load',
                                      'Do you want to re-open source folders?\n(Your current selection will be cleared)',
                                      QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok)
            if msg == QMessageBox.Cancel:
                return
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
        self.success = False

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
                if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1] in self.extensions:
                    slfs.add(f)
            if not slfs:
                QMessageBox.critical(None, 'Error', "The folder %s doesn't have any %s file (%s)!"
                                     % (name, self.file_format, ', '.join(self.extensions)), QMessageBox.Ok)
                self.dir_paths = []
                return
            if not all_slfs:
                all_slfs = slfs.copy()
            else:
                all_slfs.intersection_update(slfs)
            if not all_slfs:
                QMessageBox.critical(None, 'Error',
                                     'These folders do not share identical %s file names!' % self.file_format,
                                     QMessageBox.Ok)
                self.dir_paths = []
                return
        self.nb_files = len(dir_names)
        all_slfs = list(all_slfs)
        all_slfs.sort()
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
        super().__init__('Serafin', settings.SERAFIN_EXT, old_options)


class MultiLoadCSVDialog(MultiLoadDialog):
    def __init__(self, old_options):
        super().__init__('CSV', ('.csv',), old_options)


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
        self.table.horizontalHeader().setDefaultSectionSize(150)
        self.table.setHorizontalHeaderLabels(['Folder', 'Job ID'])

        self.message_field = QPlainTextEdit()
        self.message_field.setFixedHeight(50)

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
                if os.path.isfile(os.path.join(self.dir_path, f)) and os.path.splitext(f)[1] in settings.SERAFIN_EXT:
                    slfs.add(f)

            slfs = list(slfs)
            slfs.sort()
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
        hlayout.addWidget(QLabel('Select Serafin file name'))
        hlayout.addWidget(self.file_box, Qt.AlignRight)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.table)
        vlayout.addWidget(QLabel('Click on the cells to modify Job ID.'), Qt.AlignRight)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        vlayout.addStretch()
        vlayout.addWidget(self.message_field)
        self.setLayout(vlayout)
        self.setWindowTitle('Select input file')
        self.resize(350, 350)

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
            if os.path.isfile(os.path.join(self.dir_path, f)) and os.path.splitext(f)[1] in settings.SERAFIN_EXT:
                slfs.add(f)
        if not slfs:
            QMessageBox.critical(None, 'Error', "The folder %s doesn't have any Serafin file!" % dir_name,
                                 QMessageBox.Ok)
            self.dir_path = ''
            return

        self.file_box.clear()
        slfs = list(slfs)
        slfs.sort()
        for slf in slfs:
            self.file_box.addItem(slf)

        self.table.setRowCount(1)
        filtered_name = ''.join(c for c in dir_name if c.isalnum() or c == '_')
        name_item, id_item = QTableWidgetItem(dir_name), QTableWidgetItem(filtered_name)
        name_item.setFlags(Qt.NoItemFlags)
        self.table.setItem(0, 0, name_item)
        self.table.setItem(0, 1, id_item)
        self.success = True


class SimpleVolumePlotViewer(VolumePlotViewer):
    def __init__(self):
        super().__init__()
        self.csv_separator = ''

        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))

        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.menuBar.addMenu(self.poly_menu)
        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

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
        self.time_seconds = self.data['time']

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


class SimpleFluxPlotViewer(FluxPlotViewer):
    def __init__(self):
        super().__init__()
        self.csv_separator = ''
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
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
        self.time_seconds = self.data['time']

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


class SimplePointPlotViewer(PointPlotViewer):
    def __init__(self):
        super().__init__()
        self.csv_separator = ''
        self.indices = []

        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
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
        self.data_menu.addAction(self.select_variable_short)
        self.data_menu.addSeparator()
        self.data_menu.addAction(self.selectColumnsAct_short)
        self.data_menu.addAction(self.editColumnNamesAct_short)
        self.data_menu.addAction(self.editColumColorAct_short)
        self.menuBar.addMenu(self.data_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

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

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        headers = csv_data.table[0]
        for item in headers:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for header, item in zip(headers, row):
                self.data[header].append(float(item))
        for header in headers:
            self.data[header] = np.array(self.data[header])
        self.time_seconds = self.data['time']

        self.var_IDs = csv_data.metadata['var IDs']
        self.current_var = self.var_IDs[0]
        self.points = csv_data.metadata['points']

        self.start_time = csv_data.metadata['start time']
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.indices = []
        for header in headers[1:]:
            _, index, _, _ = header.split()
            index = int(index) - 1
            if index not in self.indices:
                self.indices.append(index)

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


class ColorMapStyleDialog(QDialog):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.color_box = QComboBox()
        self.color_box.setFixedHeight(30)
        for name in self.parent.color_styles:
            self.color_box.addItem(name)
        self.color_box.setCurrentIndex(self.parent.color_styles.index(self.parent.current_style))
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                        Qt.Horizontal, self)
        apply_button = QPushButton('Apply')
        self.buttons.addButton(apply_button, QDialogButtonBox.ApplyRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        apply_button.clicked.connect(lambda: self.parent.change_color(self.color_box.currentText()))

        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a colormap style'))
        vlayout.addWidget(self.color_box)
        vlayout.addStretch()
        vlayout.addWidget(self.buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Change colormap style')
        self.resize(300, 150)


class VerticalCrossSectionPlotViewer(PlotViewer):
    def __init__(self):
        super().__init__()
        self.data = None
        self.current_var = ''
        self.current_vars2read = []
        self.current_section = ''
        self.time_index = -1
        self.section_names = []
        self.sections = []
        self.line_interpolators = []
        self.triang, self.values, self.z_values, self.vars_values, self.values_w, self.values_ut = \
            None, None, None, None, None, None
        self.nplan = -1

        self.color_limits = None
        self.cmap = None
        self.current_style = settings.DEFAULT_COLOR_STYLE
        self.color_styles = settings.COLOR_SYLES
        self.display_mesh = False
        self.revert_section = False
        self.tangential_vel_scales = None
        self.tangential_vel_grid = None

        self.aspect_ratio_check = QCheckBox('Aspect\nratio')
        self.aspect_ratio = QLineEdit('1.0')
        self.aspect_ratio.setAlignment(Qt.AlignCenter)
        self.aspect_ratio.setMaximumWidth(50)
        self.aspect_ratio_check.stateChanged.connect(self.aspect_ratio_changed)
        self.aspect_ratio.editingFinished.connect(self.aspect_ratio_changed)
        self._set_aspect_ratio_value()

        self.slider = SimpleTimeDateSelection()
        self.slider.index.editingFinished.connect(self.select_frame)
        self.slider.value.textChanged.connect(lambda text: self.select_frame())

        self.create_actions()
        self.toolBar.addAction(self.save_all_act)
        self.toolBar.addAction(self.select_variable_act)
        self.toolBar.addAction(self.select_section_prev_act)
        self.toolBar.addAction(self.section_section_act)
        self.toolBar.addAction(self.select_section_next_act)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.change_color_style_act)
        self.toolBar.addAction(self.change_color_range_act)
        self.toolBar.addAction(self.change_tangential_vel_act)
        self.toolBar.addAction(self.toggle_mesh_display_act)
        self.toolBar.addAction(self.toggle_revert_act)
        self.toolBar.addSeparator()
        self.toolBar.addWidget(self.aspect_ratio_check)
        self.toolBar.addWidget(self.aspect_ratio)
        self.toolBar.addSeparator()
        self.toolBar.addWidget(self.slider)

        self.data_menu = QMenu('&Data', self)
        self.data_menu.addAction(self.select_variable_act_short)
        self.data_menu.addAction(self.selectSectionAct_short)
        self.menuBar.addMenu(self.data_menu)

        self.color_menu = QMenu('&Colors', self)
        self.color_menu.addAction(self.change_color_style_act_short)
        self.color_menu.addAction(self.change_color_range_act_short)
        self.menuBar.addMenu(self.color_menu)

    def create_actions(self):
        self.save_all_act = QAction('Save\nall sections', self, shortcut='Ctrl+S', triggered=self.save_all_sections,
                                    icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.select_variable_act = QAction('Select\nvariable', self, triggered=self.select_variable,
                                           icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.change_color_style_act = QAction('Change\ncolor style', self, triggered=self.change_color_style,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_color_range_act = QAction('Change\ncolor range', self, triggered=self.change_color_range,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.select_section_prev_act = QAction('', self, icon=self.style().standardIcon(QStyle.SP_ArrowLeft),
                                               triggered=self.select_section_prev)
        self.section_section_act = QAction('Select\nsection', self,
                                           icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                           triggered=self.select_section)
        self.select_section_next_act = QAction('', self, icon=self.style().standardIcon(QStyle.SP_ArrowRight),
                                               triggered=self.select_section_next)
        self.select_variable_act_short = QAction('Select variable', self, triggered=self.select_variable,
                                                 icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.change_color_style_act_short = QAction('Change color style', self, triggered=self.change_color_style,
                                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_color_range_act_short = QAction('Change color range', self, triggered=self.change_color_range,
                                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_tangential_vel_act = QAction('Tangential\nvelocities', self, triggered=self.change_tangential_vel,
                                               icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.toggle_mesh_display_act = QAction('Show\nmesh', self, triggered=self.toggle_mesh_display, checkable=True,
                                               icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.toggle_revert_act = QAction('Revert\nSection', self, triggered=self.toggle_revert_section,
                                         checkable=True, icon=self.style().standardIcon(QStyle.SP_BrowserReload))
        self.selectSectionAct_short = QAction('Select section', self,
                                              icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                                              triggered=self.select_section)

    def save_all_sections(self):
        msg = QDialog()
        qpb_folder = QPushButton(QWidget().style().standardIcon(QStyle.SP_DialogOpenButton), 'Select folder')
        qle_folder = QLineEdit()
        qle_prefix = QLineEdit()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, msg)

        # Define event functions and connexions
        def select_folder():
            folder = QFileDialog.getExistingDirectory(None, 'Select a folder', QDir.currentPath())
            if folder != '':
                qle_folder.setText(folder)

        def run_save_all_sections():
            if qle_folder.text() != '':
                current_section = self.current_section
                nb_sections = len(self.section_names)
                for i in range(nb_sections):
                    self.current_section = self.section_names[i]
                    self.replot(read_var=False)
                    filename = os.path.join(qle_folder.text(), qle_prefix.text() + '_section-' + str(i) + '.png')
                    try:
                        self.canvas.print_png(filename)
                    except IOError:
                        QMessageBox.critical(msg, 'Error', 'File error for %s' % filename, QMessageBox.Ok)
                        return
                self.current_section = current_section
                self.replot(read_var=False)
                QMessageBox.information(msg, 'Save for all sections', 'Successfully generated %i files' % nb_sections)
            else:
                QMessageBox.critical(msg, 'Error', 'Select folder first')

        qpb_folder.clicked.connect(select_folder)
        buttons.accepted.connect(run_save_all_sections)
        buttons.rejected.connect(msg.reject)

        # Build layout and run QDialog
        qpb_folder.setToolTip('Select <b>folder</b>')
        qpb_folder.setFixedHeight(30)
        qle_folder.setFixedHeight(30)
        qle_prefix.setFixedHeight(30)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        hlayout = QHBoxLayout()
        hlayout.addWidget(qpb_folder)
        hlayout.addWidget(qle_folder)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(QLabel('File prefix'))
        vlayout.addWidget(qle_prefix)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Save *.png for all sections')
        msg.resize(350, 150)
        msg.exec_()

    def change_tangential_vel(self):
        # Tangential velocities can be computed only if U, V and W are present
        variables = [var for var in self.data.header.var_IDs if var != 'Z']
        if not {'U', 'V', 'W'}.issubset(variables):
            QMessageBox.critical(self, 'Error', '3D velocity variables are not found.', QMessageBox.Ok)
            return

        msg = QDialog()

        qcb_display_vectors = QCheckBox('Display tangential velocities')
        qds_scale_x = QDoubleSpinBox()
        qds_scale_x.setValue(1.0)
        qds_scale_x.setRange(0, 1e6)
        qds_scale_y = QDoubleSpinBox()
        qds_scale_y.setValue(1.0)
        qds_scale_y.setRange(0, 1e6)
        qfl_scale_vectors = QFormLayout()
        qfl_scale_vectors.addRow(QLabel('Scale factor for X (m/(m/s))'), qds_scale_x)
        qfl_scale_vectors.addRow(QLabel('Scale factor for Y (m/(m/s))'), qds_scale_y)

        qcb_interp_grid = QCheckBox('Interpolate on a regular grid')
        qds_dx = QDoubleSpinBox()
        qds_dx.setValue(1.0)
        qds_dx.setRange(0, 9e9)
        qds_dy = QDoubleSpinBox()
        qds_dy.setValue(1.0)
        qds_dy.setRange(0, 9e9)
        qfl_regular_grid = QFormLayout()
        qfl_regular_grid.addRow(QLabel('X distance (m)'), qds_dx)
        qfl_regular_grid.addRow(QLabel('Y distance (m)'), qds_dy)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, msg)

        # Initialize states
        if self.tangential_vel_scales:
            qcb_display_vectors.setChecked(True)
            kx, ky = self.tangential_vel_scales
            qds_scale_x.setValue(kx)
            qds_scale_y.setValue(ky)
        else:
            qcb_display_vectors.setChecked(False)
        if self.tangential_vel_grid is not None:
            qcb_interp_grid.setChecked(True)
            dx, dy = self.tangential_vel_grid
            qds_dx.setValue(dx)
            qds_dy.setValue(dy)
        else:
            qcb_interp_grid.setChecked(False)

        # Define event functions and connexions
        def update_qfl_scale_vectors():
            if qcb_display_vectors.isChecked():
                qds_scale_x.setEnabled(True)
                qds_scale_y.setEnabled(True)
            else:
                qds_scale_x.setEnabled(False)
                qds_scale_y.setEnabled(False)
        update_qfl_scale_vectors()

        def update_qfl_regular_grid():
            if qcb_interp_grid.isChecked():
                qds_dx.setEnabled(True)
                qds_dy.setEnabled(True)
            else:
                qds_dx.setEnabled(False)
                qds_dy.setEnabled(False)
        update_qfl_regular_grid()

        def run():
            self.tangential_vel_scales = None
            self.tangential_vel_grid = None
            if qcb_display_vectors.isChecked():
                self.tangential_vel_scales = (qds_scale_x.value(), qds_scale_y.value())
                if qcb_interp_grid.isChecked():
                    self.tangential_vel_grid = (qds_dx.value(), qds_dy.value())
            self._set_vars2read()
            self.replot(read_var=True, compute=True)
            msg.accept()

        qcb_display_vectors.stateChanged.connect(update_qfl_scale_vectors)
        qcb_interp_grid.stateChanged.connect(update_qfl_regular_grid)
        buttons.accepted.connect(run)
        buttons.rejected.connect(msg.reject)

        # Build layout and run QDialog
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(qcb_display_vectors)
        vlayout.addLayout(qfl_scale_vectors)
        vlayout.addWidget(qcb_interp_grid)
        vlayout.addLayout(qfl_regular_grid)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Tangential velocities')
        msg.resize(300, 150)
        msg.exec_()

    def select_section_prev(self):
        current_index = self.section_names.index(self.current_section)
        new_index = max(current_index - 1, 0)
        self.current_section = self.section_names[new_index]
        self.replot(read_var=False)

    def select_section_next(self):
        current_index = self.section_names.index(self.current_section)
        new_index = min(current_index + 1, len(self.section_names) - 1)
        self.current_section = self.section_names[new_index]
        self.replot(read_var=False)

    def select_section(self):
        msg = QDialog()
        combo = QComboBox()
        combo.setFixedHeight(30)
        for section in self.section_names:
            combo.addItem(section)
        combo.setCurrentIndex(self.section_names.index(self.current_section))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a section'))
        vlayout.addWidget(combo)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a section to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_section = combo.currentText()
        self.replot(read_var=False)

    def toggle_mesh_display(self):
        self.display_mesh = not self.display_mesh
        self.replot(read_var=False, compute=False)

    def toggle_revert_section(self):
        self.revert_section = not self.revert_section
        self.replot(read_var=False)

    def _defaultTitle(self):
        value = {'fr': 'Valeurs', 'en': 'Values'}[self.language]
        of = {'fr': 'de', 'en': 'of'}[self.language]
        at = {'fr': 'à la', 'en': 'at'}[self.language]
        return '%s %s %s %s %s' % (value, of, self.current_var, at, self.current_section)

    def _defaultXLabel(self):
        return settings.X_AXIS_LABEL_CROSS_SECTION

    def _defaultYLabel(self):
        if settings.Y_AXIS_LABEL_CROSS_SECTION == '':
            return {'fr': 'Cote Z (m)', 'en': 'Elevation Z (m)'}[self.language]
        else:
            return settings.Y_AXIS_LABEL_CROSS_SECTION

    def select_variable(self):
        msg = QDialog()
        combo = QComboBox()
        combo.setFixedHeight(30)

        variables, names = self._get_var_list()
        for var, name in zip(variables, names):
            combo.addItem(var + ' (%s)' % name)
        combo.setCurrentIndex(variables.index(self.current_var))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a variable'))
        vlayout.addWidget(combo)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText().split(' (')[0]
        self._set_vars2read()
        self.color_limits = None
        self.replot(read_var=True, compute=True)

    def _set_vars2read(self):
        if self.current_var == 'Un':
            self.current_vars2read = []
        else:
            self.current_vars2read = [self.current_var]
        if self.current_var == 'Un' or self.tangential_vel_scales:
            for varID in ('U', 'V'):
                if varID not in self.current_vars2read:
                    self.current_vars2read.append(varID)
        if self.tangential_vel_scales:
            if 'W' not in self.current_vars2read:
                self.current_vars2read.append('W')

    def change_color(self, style):
        self.current_style = style
        self.replot(read_var=False, compute=False)

    def change_color_style(self):
        msg = ColorMapStyleDialog(self)
        if msg.exec_() == QDialog.Accepted:
            self.change_color(msg.color_box.currentText())

    def change_color_range(self):
        msg = QDialog()
        change_color_activate = QCheckBox('User define color range')
        change_color_limits = QLineEdit(', '.join(map(lambda x: '{:+f}'.format(x), self.cmap.get_clim())))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, msg)

        if self.color_limits is None:
            change_color_activate.setChecked(False)
        else:
            change_color_activate.setChecked(True)

        def update_change_color_limits():
            if change_color_activate.isChecked():
                change_color_limits.setEnabled(True)
            else:
                change_color_limits.setEnabled(False)
        update_change_color_limits()

        def run():
            if change_color_activate.isChecked():
                try:
                    cmin, cmax = map(float, change_color_limits.text().split(','))
                except ValueError:
                    QMessageBox.critical(self, 'Error', 'Invalid input.', QMessageBox.Ok)
                    return
                if cmax <= cmin:
                    QMessageBox.critical(self, 'Error', 'Values are not increasing.', QMessageBox.Ok)
                    return
                self.color_limits = (cmin, cmax)
            else:
                self.color_limits = None
            self._set_vars2read()
            self.replot(read_var=False, compute=False)
            msg.accept()

        change_color_activate.stateChanged.connect(update_change_color_limits)
        buttons.accepted.connect(run)
        buttons.rejected.connect(msg.reject)

        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(change_color_activate)
        vlayout.addWidget(QLabel('Set minimum and maximum values'))
        vlayout.addWidget(change_color_limits)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Change color range')
        msg.resize(300, 150)
        msg.exec_()

    def select_frame(self):
        text = self.slider.index.text()
        try:
            index = int(text) - 1
        except ValueError:
            self.slider.index.setText(str(self.time_index+1))
            self.slider.slider.enterIndexEvent()
            return
        if 0 <= index < len(self.data.time):
            self.time_index = index
            self.replot()

    def _set_aspect_ratio_value(self):
        self.aspect_ratio_value = 'auto'
        try:
            if self.aspect_ratio_check.isChecked():
                self.aspect_ratio_value = float(self.aspect_ratio.text())
        except ValueError:
            pass

    def aspect_ratio_changed(self):
        self._set_aspect_ratio_value()
        self.replot(read_var=False, compute=False)

    def compute(self):
        """!
        Compute current cross section
        """
        line_interpolator, distances = self.line_interpolators[int(self.current_section.split()[1]) - 1]
        npt = len(distances)

        if self.current_var == 'Un' or self.tangential_vel_scales:
            # Compute normal vectors: one vector at each point, which is (anticlockwise) orthogonal to cross-section
            #   (At a turning point, the normal vector is based on the segment defined by the next and previous point)
            # Normal and tangential vectors are normalized
            normal_vectors = np.empty((npt, 2))
            tangential_vectors = np.empty((npt, 2))
            coords = np.array([(x, y) for i, (x, y, _, _) in enumerate(line_interpolator)])
            normal_vectors[:, 0] = - (np.ediff1d(coords[:, 1], to_begin=0) + np.ediff1d(coords[:, 1], to_end=0))
            normal_vectors[:, 1] = np.ediff1d(coords[:, 0], to_begin=0) + np.ediff1d(coords[:, 0], to_end=0)
            normal_vector_norm = np.linalg.norm(normal_vectors, axis=1)
            normal_vectors = normal_vectors/normal_vector_norm[:, None]
            tangential_vectors[:, 0] = - normal_vectors[:, 1]
            tangential_vectors[:, 1] = normal_vectors[:, 0]

        if self.revert_section:  # Only the distances and tangencial velocities are reverted (normal velocities are not affected)
            distances = np.amax(distances) - distances
            tangential_vectors = - tangential_vectors

        point_x = np.array([[distances[i]] * self.nplan for i in range(npt)])
        point_y = np.empty((npt, self.nplan))
        point_values = np.empty((npt, self.nplan))

        point_ut = np.empty((npt, self.nplan))
        point_w = np.empty((npt, self.nplan))

        for i_pt, ((_, _, (i, j, k), interpolator), distance) in enumerate(zip(line_interpolator, distances)):
            point_y[i_pt] = interpolator.dot(self.z_values[[i, j, k]])

            if self.current_var == 'Un' or self.tangential_vel_scales:  # Compute normal and tangential velocities
                point_u = interpolator.dot(self.vars_values['U'][[i, j, k]])
                point_v = interpolator.dot(self.vars_values['V'][[i, j, k]])
                uv = np.column_stack((point_u, point_v))

            if self.current_var == 'Un':
                point_values[i_pt] = uv.dot(normal_vectors[i_pt])
            else:
                point_values[i_pt] = interpolator.dot(self.vars_values[self.current_var][[i, j, k]])

            if self.tangential_vel_scales:
                point_ut[i_pt] = uv.dot(tangential_vectors[i_pt])
                point_w[i_pt] = interpolator.dot(self.vars_values['W'][[i, j, k]])

        triangles = [((ipt - 1) * self.nplan + iplan - 1, (ipt - 1) * self.nplan + iplan, ipt * self.nplan + iplan - 1)
                     for ipt in range(1, npt) for iplan in range(1, self.nplan)] + \
                    [((ipt - 1) * self.nplan + iplan, ipt * self.nplan + iplan - 1, ipt * self.nplan + iplan)
                     for ipt in range(1, npt) for iplan in range(1, self.nplan)]

        self.triang = mtri.Triangulation(point_x.flatten(), point_y.flatten(), triangles)
        self.values = point_values.flatten()
        self.values_ut = point_ut.flatten()
        self.values_w = point_w.flatten()

    def _get_var_list(self):
        variables = [var for var in self.data.header.var_IDs if var != 'Z']
        names = [name.decode(Serafin.SLF_EIT).strip()
                 for var, name in zip(self.data.header.var_IDs, self.data.header.var_names) if var in variables]
        # Add normal velocity
        if {'U', 'V'}.issubset(self.data.header.var_IDs):
            variables.insert(0, 'Un')
            names.insert(0, 'Computed Normal Velocity')
        return variables, names

    def read_var(self):
        """Read current variable values"""
        self.vars_values = {}
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time
            self.z_values = input_stream.read_var_in_frame_as_3d(self.time_index, 'Z').T
            for varID in self.current_vars2read:
                self.vars_values[varID] = input_stream.read_var_in_frame_as_3d(self.time_index, varID).T

    def replot(self, read_var=True, compute=True):
        if not self.current_vars2read:
            self._set_vars2read()
        if read_var:
            self.read_var()
        if compute or not self.vars_values:
            self.compute()

        self._update_next_prev()
        self.canvas.figure.clear()  # remove the old color bar
        self.canvas.axes = self.canvas.figure.add_subplot(111)

        if self.color_limits is not None:
            levels = np.linspace(self.color_limits[0], self.color_limits[1], settings.NB_COLOR_LEVELS)
            self.canvas.axes.tricontourf(self.triang, self.values, cmap=self.current_style, levels=levels,
                                         extend='both', vmin=self.color_limits[0], vmax=self.color_limits[1])
        else:
            levels = build_levels_from_minmax(np.nanmin(self.values), np.nanmax(self.values))
            self.canvas.axes.tricontourf(self.triang, self.values, cmap=self.current_style, levels=levels,
                                         extend='both')
        if self.display_mesh:
            self.canvas.axes.triplot(self.triang, 'ko-')

        if self.tangential_vel_scales:
            kx, ky = self.tangential_vel_scales

            if self.tangential_vel_grid:
                dx, dy = self.tangential_vel_grid
                x = np.arange(np.amin(self.triang.x), np.amax(self.triang.x), dx)
                y = np.arange(np.amin(self.triang.y), np.amax(self.triang.y), dy)
                xv, yv = np.meshgrid(x, y)
                try:
                    ut = mtri.LinearTriInterpolator(self.triang, self.values_ut)(xv, yv)
                    w = mtri.LinearTriInterpolator(self.triang, self.values_w)(xv, yv)
                    self.canvas.axes.quiver(xv, yv, kx*ut, ky*w, angles='xy', scale_units='xy', scale=1)
                except RuntimeError as e:
                    QMessageBox.critical(self, 'Error', 'Error with the grid interpolation: %s\n'
                                         'Tangential velocities will not be displayed.' % e, QMessageBox.Ok)
            else:
                self.canvas.axes.quiver(self.triang.x, self.triang.y, kx*self.values_ut, ky*self.values_w,
                                        angles='xy', scale_units='xy', scale=1)

        self.canvas.axes.set_aspect(aspect=self.aspect_ratio_value, adjustable='datalim')
        self.canvas.figure.subplots_adjust(right=0.80)  # left side (80% of figure width) for plot
        cax = self.canvas.figure.add_axes([0.84, 0.1, 0.03, 0.8])  # right side (20% of figure width) for colorbar
        cax.set_title(self.current_var)
        self.cmap = cm.ScalarMappable(cmap=self.current_style)
        self.cmap.set_array(levels)
        self.canvas.figure.colorbar(self.cmap, cax=cax)

        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.current_title = self._defaultTitle()
        self.canvas.axes.set_title(self.current_title)
        self.canvas.draw()

    def _update_next_prev(self):
        """Enable/disable next and previous action depending on position"""
        current_index = self.section_names.index(self.current_section)
        enable_prev = False if current_index == 0 else True
        enable_next = False if current_index == len(self.section_names) - 1 else True
        self.select_section_prev_act.setEnabled(enable_prev)
        self.select_section_next_act.setEnabled(enable_next)

    def get_data(self, data, sections, line_interpolators, section_indices):
        self.data = data
        self.sections = sections
        self.line_interpolators = line_interpolators
        self.section_indices = section_indices

        self.current_var = self._get_var_list()[0][0]  # first possible variable by default
        self.section_names = ['Section %d' % (i+1) for i in self.section_indices]
        self.current_section = self.section_names[0]

        # initialize the plot
        self.language = self.data.language
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = self._defaultTitle()

        self.nplan = self.data.header.nb_planes

        self.slider.initTime(self.data.time, list(map(lambda x: x + self.data.start_time, self.data.time_second)))
        self.replot()


class VerticalProfilePlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.data = None
        self.current_var = ''
        self.points = []
        self.point_interpolators = []
        self.indices = []
        self.y, self.z = [], []
        self.triangles = []
        self.n, self.k, self.m = -1, -1, -1

        self.color_limits = None
        self.cmap = None
        self.current_style = settings.DEFAULT_COLOR_STYLE
        self.color_styles = settings.COLOR_SYLES

        self.create_actions()
        self.current_columns = ('Point 1',)
        self.toolBar.addAction(self.select_variable_act)
        self.toolBar.addAction(self.select_point_prev_act)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.select_point_next_act)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.change_color_style_act)
        self.toolBar.addAction(self.change_color_range_act)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.data_menu = QMenu('&Data', self)
        self.data_menu.addAction(self.select_variable_act_short)
        self.data_menu.addAction(self.selectColumnsAct_short)
        self.menuBar.addMenu(self.data_menu)

        self.color_menu = QMenu('&Colors', self)
        self.color_menu.addAction(self.change_color_style_act_short)
        self.color_menu.addAction(self.change_color_range_act_short)
        self.menuBar.addMenu(self.color_menu)

    def create_actions(self):
        self.select_point_prev_act = QAction('', self, icon=self.style().standardIcon(QStyle.SP_ArrowLeft),
                                             triggered=self.select_point_prev)
        self.select_point_next_act = QAction('', self, icon=self.style().standardIcon(QStyle.SP_ArrowRight),
                                             triggered=self.select_point_next)
        self.select_variable_act = QAction('Select\nvariable', self, triggered=self.select_variable,
                                           icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.change_color_style_act = QAction('Change\ncolor style', self, triggered=self.change_color_style,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_color_range_act = QAction('Change\ncolor range', self, triggered=self.change_color_range,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.select_variable_act_short = QAction('Select variable', self, triggered=self.select_variable,
                                                 icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.change_color_style_act_short = QAction('Change color style', self, triggered=self.change_color_style,
                                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_color_range_act_short = QAction('Change color range', self, triggered=self.change_color_range,
                                                    icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))

    def select_point_prev(self):
        current_index = self.columns.index(self.current_columns[0])
        new_index = max(current_index - 1, 0)
        self.current_columns = [self.columns[new_index]]
        self.color_limits = None
        self.replot()

    def select_point_next(self):
        current_index = self.columns.index(self.current_columns[0])
        new_index = min(current_index + 1, len(self.columns) - 1)
        self.current_columns = [self.columns[new_index]]
        self.color_limits = None
        self.replot()

    def selectColumns(self, unique_selection=False):
        super().selectColumns(True)

    def _defaultTitle(self):
        value = {'fr': 'Valeurs', 'en': 'Values'}[self.language]
        of = {'fr': 'de', 'en': 'of'}[self.language]
        at = {'fr': 'au', 'en': 'at'}[self.language]
        return '%s %s %s %s %s' % (value, of, self.current_var, at, self.current_columns[0])

    def _defaultYLabel(self):
        return {'fr': 'Cote Z', 'en': 'Elevation Z'}[self.language]

    def select_variable(self):
        msg = QDialog()
        combo = QComboBox()
        combo.setFixedHeight(30)
        variables = [var for var in self.data.header.var_IDs if var != 'Z']
        names = [name.decode(Serafin.SLF_EIT).strip()
                 for var, name in zip(self.data.header.var_IDs, self.data.header.var_names) if var in variables]
        for var, name in zip(variables, names):
            combo.addItem(var + ' (%s)' % name)
        combo.setCurrentIndex(variables.index(self.current_var))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a variable'))
        vlayout.addWidget(combo)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText().split(' (')[0]
        self.current_ylabel = self._defaultYLabel()
        self.color_limits = None
        self.replot()

    def change_color(self, style):
        self.current_style = style
        self.replot(False)

    def change_color_style(self):
        msg = ColorMapStyleDialog(self)
        if msg.exec_() == QDialog.Accepted:
            self.change_color(msg.color_box.currentText())

    def change_color_range(self):
        value, ok = QInputDialog.getText(None, 'Change color bar range',
                                         'Enter the new color range',
                                         text=', '.join(map(lambda x: '{:+f}'.format(x),
                                                            self.cmap.get_clim())))
        if not ok:
            return
        try:
            cmin, cmax = map(float, value.split(','))
        except ValueError:
            QMessageBox.critical(self, 'Error', 'Invalid input.', QMessageBox.Ok)
            return
        if cmax <= cmin:
            QMessageBox.critical(self, 'Error', 'Values are not increasing.', QMessageBox.Ok)
            return

        self.color_limits = (cmin, cmax)
        self.replot(False)

    def compute(self):
        (a, b, c), interpolator = self.point_interpolators[int(self.current_columns[0].split()[1])-1]

        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            input_stream.time = self.data.time

            point_y = np.empty((self.n, self.k))
            point_values = np.empty((self.n, self.k))

            for i in range(self.n):
                z = input_stream.read_var_in_frame_as_3d(i, 'Z')
                values = input_stream.read_var_in_frame_as_3d(i, self.current_var)

                for j in range(self.k):
                    point_y[i, j] = z[j, [a, b, c]].dot(interpolator)
                    point_values[i, j] = values[j, [a, b, c]].dot(interpolator)

        y = point_y.flatten()
        z = point_values.flatten()
        return y, z

    def replot(self, compute=True):
        if compute:
            self.y, self.z = self.compute()

        self._update_next_prev()
        self.canvas.figure.clear()   # remove the old color bar
        self.canvas.axes = self.canvas.figure.add_subplot(111)

        triang = mtri.Triangulation(self.time[self.timeFormat], self.y, self.triangles)
        if self.color_limits is not None:
            levels = np.linspace(self.color_limits[0], self.color_limits[1], settings.NB_COLOR_LEVELS)
            self.canvas.axes.tricontourf(triang, self.z, cmap=self.current_style, levels=levels, extend='both',
                                         vmin=self.color_limits[0], vmax=self.color_limits[1])
        else:
            levels = build_levels_from_minmax(np.nanmin(self.z), np.nanmax(self.z))
            self.canvas.axes.tricontourf(triang, self.z, cmap=self.current_style, levels=levels, extend='both')

        divider = make_axes_locatable(self.canvas.axes)
        cax = divider.append_axes('right', size='5%', pad=0.2)
        cax.set_title(self.current_var)
        self.cmap = cm.ScalarMappable(cmap=self.current_style)
        self.cmap.set_array(levels)
        self.canvas.figure.colorbar(self.cmap, cax=cax)

        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.current_title = self._defaultTitle()
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()

    def _update_next_prev(self):
        """Enable/disable next and previous action depending on position"""
        current_index = self.columns.index(self.current_columns[0])
        enable_prev = False if current_index == 0 else True
        enable_next = False if current_index == len(self.columns) - 1 else True
        self.select_point_prev_act.setEnabled(enable_prev)
        self.select_point_next_act.setEnabled(enable_next)

    def get_data(self, data, points, point_interpolators, indices):
        self.data = data
        self.points = points
        self.point_interpolators = point_interpolators
        self.indices = indices

        self.current_var = [var for var in self.data.header.var_IDs if var != 'Z'][0]
        self.columns = ['Point %d' % (i+1) for i in self.indices]
        self.current_columns = self.columns[0:1]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        self.start_time = self.data.start_time
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data.time))
        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        # initialize the plot
        self.language = self.data.language

        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = self._defaultTitle()

        self.n, self.k, self.m = len(self.data.time), self.data.header.nb_planes, self.data.header.nb_nodes_2d
        point_x = np.array([[self.data.time[i]] * self.k for i in range(self.n)])
        point_x = point_x.flatten()
        self.time_seconds = np.array(self.data.time)
        self.time = [point_x, point_x, point_x,
                     point_x / 60, point_x / 3600, point_x / 86400]

        self.triangles = [(i*self.k+j, i*self.k+j+1, i*self.k+j+1-self.k)
                          for i in range(1, self.n) for j in range(self.k-1)] + \
                         [(i*self.k+j, i*self.k+j-self.k, i*self.k+j+1-self.k)
                          for i in range(1, self.n) for j in range(self.k-1)]
        self.replot()


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
        self.output_panel = OutputOptionPanel(['_plot', True, '', False, True])
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
                filename = process_output_options(os.path.join(path, self.csv_name), job_id, '.png',
                                                  suffix, in_source_folder, dir_path, double_name)
                self.out_names.append(filename)

        self.plot()
        QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                QMessageBox.Ok)
        self.accept()

    def read(self, csv_file):
        try:
            data, headers = read_csv(csv_file, self.separator)
            if 'time' not in headers:
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
        fig.set_size_inches(settings.FIG_SIZE[0], settings.FIG_SIZE[1])

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
            fig.savefig(png_name, dpi=settings.FIG_OUT_DPI)


class MultiSaveFluxDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, cumulative):
        super().__init__('Compute Flux', separator, current_columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.cumulative = cumulative

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(settings.FIG_SIZE[0], settings.FIG_SIZE[1])

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
            fig.savefig(png_name, dpi=settings.FIG_OUT_DPI)


class MultiSavePointDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, columns):
        super().__init__('Interpolate on Points', separator, columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.current_points = current_columns

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(settings.FIG_SIZE[0], settings.FIG_SIZE[1])

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
            fig.savefig(png_name, dpi=settings.FIG_OUT_DPI)


class MultiInterpolationPlotDialog(QDialog):
    def __init__(self, parent, name, input_options, output_options, compute_options):
        super().__init__()
        self.parent = parent
        self.compute_options = compute_options
        self.lines = []

        self.table = QTableWidget()
        self.table.setRowCount(len(input_options[0]))
        self.table.setColumnCount(4)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['Job', 'Load Serafin 2D', 'Interpolation', 'Export PNG'])

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
        suffix, in_source_folder, dir_path, double_name, _ = output_options
        self.png_names = []
        for path, job_id in zip(self.dir_paths, self.job_ids):
            png_name = process_output_options(os.path.join(path, self.slf_name), job_id, '.png',
                                              suffix, in_source_folder, dir_path, double_name)
            self.png_names.append(png_name)

    def fail(self, i, j):
        self.table.item(i, j).setBackground(self.red)
        QApplication.processEvents()

    def success(self, i, j):
        self.table.item(i, j).setBackground(self.green)
        QApplication.processEvents()

    def load(self, row, input_file, job_id, language):
        try:
            with open(input_file) as f:
                pass
        except PermissionError:
            self.fail(row, 1)
            return None
        input_data = SerafinData(job_id, input_file, language)
        if input_data.read():
            return input_data
        self.fail(row, 1)
        return None

    def check_load(self, row, input_data):
        pass

    def build_mesh(self, input_data):
        return MeshInterpolator(input_data.header, True)

    def interpolate(self, row, input_mesh):
        nb_nonempty, indices_nonempty, \
                     line_interpolators, line_interpolators_internal = input_mesh.get_line_interpolators(self.lines)
        if nb_nonempty == 0:
            self.fail(row, 2)
            return False, None, None
        return True, line_interpolators, line_interpolators_internal

    def check_interpolate(self, row, line_interpolators, line_interpolators_internal):
        line_interpolator, distances = line_interpolators[self.line_id]
        if not line_interpolator:
            self.fail(row, 2)
            return False, None, None, None, None
        line_interpolator_internal, distances_internal = line_interpolators_internal[self.line_id]
        self.success(row, 2)
        return True, line_interpolator, distances, line_interpolator_internal, distances_internal

    def first_step(self):
        successful_input_data = []
        successful_rows = []

        for row, (dir_path, job_id) in enumerate(zip(self.dir_paths, self.job_ids)):
            input_name = os.path.join(dir_path, self.slf_name)
            input_data = self.load(row, input_name, job_id, self.language)
            if input_data is None:
                continue
            success = self.check_load(row, input_data)
            if not success:
                continue
            successful_rows.append(row)
            successful_input_data.append(input_data)
        return successful_rows, successful_input_data

    def finishing_up(self, nb_successes):
        if nb_successes == len(self.dir_paths):
            QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                    QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Failed', 'Failed to produce all figures.',
                                    QMessageBox.Ok)
        self.btnClose.setEnabled(True)


class MultiSaveMultiVarLinePlotDialog(MultiInterpolationPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'MultiVar Line Plot',
                         input_options, output_options, compute_options)
        self.lines, self.line_id, self.time_index, self.current_vars, self.language = self.compute_options

    def check_load(self, row, input_data):
        # check time
        if self.time_index >= len(input_data.time):
            self.fail(row, 1)
            return False
        # check variables
        for var in self.current_vars:
            if var not in input_data.header.var_IDs:
                self.fail(row, 1)
                return False
        self.success(row, 1)
        return True

    def compute(self, input_data, line_interpolator, line_interpolator_internal):
        values = []
        values_internal = []
        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            for var in self.current_vars:
                line_var_values = []
                line_var_values_internal = []
                var_values = input_stream.read_var_in_frame(self.time_index, var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)

                for x, y, (i, j, k), interpolator in line_interpolator_internal:
                    line_var_values_internal.append(interpolator.dot(var_values[[i, j, k]]))
                values_internal.append(line_var_values_internal)

        return values, values_internal

    def run(self):
        # load serafin
        successful_rows, successful_input_data = self.first_step()

        nb_successes = 0
        for row, input_data in zip(successful_rows, successful_input_data):
            # interpolation
            mesh = self.build_mesh(input_data)
            success, line_interpolators, line_interpolators_internal = self.interpolate(row, mesh)
            if not success:
                continue

            success, line_interpolator, distances, \
                line_interpolator_internal, distances_internal = self.check_interpolate(row, line_interpolators,
                                                                                        line_interpolators_internal)
            if not success:
                continue

            # export PNG
            values, values_internal = self.compute(input_data, line_interpolator, line_interpolator_internal)
            self.parent.plot(values, distances, values_internal, distances_internal,
                             self.current_vars, self.png_names[row])
            self.success(row, 3)
            nb_successes += 1

        self.finishing_up(nb_successes)


class MultiSaveMultiFrameLinePlotDialog(MultiInterpolationPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'MultiVar Frame Plot',
                         input_options, output_options, compute_options)
        self.lines, self.line_id, self.current_var, self.time_indices, self.language = self.compute_options

    def check_load(self, row, input_data):
        # check variable
        if self.current_var not in input_data.header.var_IDs:
            self.fail(row, 1)
            return False
        # check time
        for time_index in self.time_indices:
            if time_index not in input_data.selected_time_indices:
                self.fail(row, 1)
                return False
        self.success(row, 1)
        return True

    def compute(self, input_data, line_interpolator, line_interpolator_internal):
        values = []
        values_internal = []
        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            for index in self.time_indices:
                line_var_values = []
                line_var_values_internal = []
                var_values = input_stream.read_var_in_frame(index, self.current_var)

                for x, y, (i, j, k), interpolator in line_interpolator:
                    line_var_values.append(interpolator.dot(var_values[[i, j, k]]))
                values.append(line_var_values)

                for x, y, (i, j, k), interpolator in line_interpolator_internal:
                    line_var_values_internal.append(interpolator.dot(var_values[[i, j, k]]))
                values_internal.append(line_var_values)
        return values, values_internal

    def run(self):
        # load serafin
        successful_rows, successful_input_data = self.first_step()

        nb_successes = 0
        for row, input_data in zip(successful_rows, successful_input_data):
            # interpolation
            mesh = self.build_mesh(input_data)
            success, line_interpolators, line_interpolators_internal = self.interpolate(row, mesh)
            if not success:
                continue

            success, line_interpolator, distances, \
                line_interpolator_internal, distances_internal = self.check_interpolate(row, line_interpolators,
                                                                                        line_interpolators_internal)
            if not success:
                continue

            # Export PNG
            values, values_internal = self.compute(input_data, line_interpolator, line_interpolator_internal)
            self.parent.plot(values, distances, values_internal, distances_internal,
                             self.time_indices, self.png_names[row])
            self.success(row, 3)
            nb_successes += 1

        self.finishing_up(nb_successes)


class MultiSaveProjectLinesDialog(MultiInterpolationPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'Project Lines',
                         input_options, output_options, compute_options)
        self.lines, self.ref_id, self.reference, self.max_distance, \
                    self.time_index, self.current_vars, self.language = self.compute_options

    def check_load(self, row, input_data):
         # check time
        if self.time_index >= len(input_data.time):
            self.fail(row, 1)
            return False
        # check variables
        for line_id, variables in self.current_vars.items():
            for var in variables:
                if var not in input_data.header.var_IDs:
                    self.fail(row, 1)
                    return False
        self.success(row, 1)
        return True

    def check_interpolate(self, row, all_line_interpolators, all_line_interpolators_internal):
        if all_line_interpolators[self.ref_id] is None:
            self.fail(row, 2)
            return False, None, None

        line_interpolators = {}
        line_interpolators_internal = {}
        for line_id in self.current_vars:
            line_interpolator, _ = all_line_interpolators[line_id]
            if not line_interpolator:
                self.fail(row, 2)
                return False, None, None
            line_interpolators[line_id] = line_interpolator

            line_interpolator_internal, _ = all_line_interpolators_internal[line_id]
            line_interpolators_internal[line_id] = line_interpolator_internal

        self.success(row, 2)
        return True, line_interpolators, line_interpolators_internal

    def compute(self, input_data, line_interpolators, line_interpolators_internal):
        distances, values, distances_internal, values_internal = {}, {}, {}, {}

        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            for line_id in self.current_vars:
                distances[line_id] = []
                distances_internal[line_id] = []
                values[line_id] = {}
                values_internal[line_id] = {}

                for var in self.current_vars[line_id]:
                    values[line_id][var] = []
                    values_internal[line_id][var] = []

                for x, y, (i, j, k), interpolator in line_interpolators[line_id]:
                    d = self.reference.project(x, y)
                    if d <= 0 or d >= self.max_distance:
                        continue
                    distances[line_id].append(d)

                    for var in self.current_vars[line_id]:
                        all_values = input_stream.read_var_in_frame(self.time_index, var)
                        values[line_id][var].append(interpolator.dot(all_values[[i, j, k]]))
                distances[line_id] = np.array(distances[line_id])

                for x, y, (i, j, k), interpolator in line_interpolators_internal[line_id]:
                    d = self.reference.project(x, y)
                    if d <= 0 or d >= self.max_distance:
                        continue
                    distances_internal[line_id].append(d)

                    for var in self.current_vars[line_id]:
                        all_values = input_stream.read_var_in_frame(self.time_index, var)
                        values_internal[line_id][var].append(interpolator.dot(all_values[[i, j, k]]))
                distances_internal[line_id] = np.array(distances_internal[line_id])

        return distances, values, distances_internal, values_internal

    def run(self):
        # load serafin
        successful_rows, successful_input_data = self.first_step()

        nb_successes = 0
        for row, input_data in zip(successful_rows, successful_input_data):
            # interpolation
            mesh = self.build_mesh(input_data)
            success, all_line_interpolators, all_line_interpolators_internal = self.interpolate(row, mesh)
            if not success:
                continue

            success, line_interpolators, \
                     line_interpolators_internal = self.check_interpolate(row,  all_line_interpolators,
                                                                          all_line_interpolators_internal)
            if not success:
                continue

            # export PNG
            distances, values, distances_internal, values_internal = self.compute(input_data, line_interpolators,
                                                                                  line_interpolators_internal)
            self.parent.plot(values, distances, values_internal, distances_internal,
                             self.current_vars, self.png_names[row])
            self.success(row, 3)
            nb_successes += 1

        self.finishing_up(nb_successes)


class MultiSaveVerticalProfileDialog(MultiInterpolationPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'Vertical Temporal Profile',
                         input_options, output_options, compute_options)
        self.point, self.current_var, self.language = self.compute_options

    def load(self, row, input_file, job_id, language):
        try:
            with open(input_file) as f:
                pass
        except PermissionError:
            self.fail(row, 1)
            return None
        input_data = SerafinData(job_id, input_file, language)
        if not input_data.read():
            return input_data
        self.fail(row, 1)
        return None

    def check_load(self, row, input_data):
        # check variables
        if self.current_var not in input_data.header.var_IDs:
            self.fail(row, 1)
            return False
        self.success(row, 1)
        return True

    def interpolate(self, row, input_mesh):
        is_inside, point_interpolator = input_mesh.get_point_interpolators([self.point])
        is_inside, point_interpolator = is_inside[0], point_interpolator[0]
        if not is_inside:
            self.fail(row, 2)
            return False, None
        self.success(row, 2)
        return True, point_interpolator

    def compute(self, input_data, point_interpolator):
        n, k, m = len(input_data.time), input_data.header.nb_planes, input_data.header.nb_nodes_2d
        point_x = np.array([[input_data.time[i]] * k for i in range(n)])
        x = point_x.flatten()

        (a, b, c), interpolator = point_interpolator

        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time

            point_y = np.empty((n, k))
            point_values = np.empty((n, k))

            for i in range(n):
                z = input_stream.read_var_in_frame_as_3d(i, 'Z')
                values = input_stream.read_var_in_frame_as_3d(i, self.current_var)

                for j in range(k):
                    point_y[i, j] = z[j, [a, b, c]].dot(interpolator)
                    point_values[i, j] = values[j, [a, b, c]].dot(interpolator)

        y = point_y.flatten()
        z = point_values.flatten()

        start_time = input_data.start_time
        dates = list(map(lambda x: start_time + datetime.timedelta(seconds=x), input_data.time))
        str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), dates))
        str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), dates))
        time = [x, x, x, x / 60, x / 3600, x / 86400]
        triangles = [(i*k+j, i*k+j+1, i*k+j+1-k) for i in range(1, n) for j in range(k-1)] + \
                    [(i*k+j, i*k+j-k, i*k+j+1-k) for i in range(1, n) for j in range(k-1)]
        return time, y, z, triangles, str_datetime, str_datetime_bis

    def run(self):
        # load serafin
        successful_rows, successful_input_data = self.first_step()

        nb_successes = 0
        for row, input_data in zip(successful_rows, successful_input_data):
            # interpolation
            mesh = self.build_mesh(input_data)
            success, point_interpolator = self.interpolate(row, mesh)
            if not success:
                continue

            # export PNG
            time, y, z, triangles, str_datetime, str_datetime_bis = self.compute(input_data, point_interpolator)
            self.parent.plot(time, y, z, triangles, str_datetime, str_datetime_bis, self.png_names[row])
            self.success(row, 3)
            nb_successes += 1

        self.finishing_up(nb_successes)


class MultiSaveVerticalCrossSectionDialog(MultiInterpolationPlotDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__(parent, 'Vertical Cross Section',
                         input_options, output_options, compute_options)
        self.line, self.current_var, self.language = self.compute_options

    def load(self, row, input_file, job_id, language):
        try:
            with open(input_file) as f:
                pass
        except PermissionError:
            self.fail(row, 1)
            return None
        input_data = SerafinData(job_id, input_file, language)
        if not input_data.read():
            return input_data
        self.fail(row, 1)
        return None

    def check_load(self, row, input_data):
        # check variables
        if self.current_var not in input_data.header.var_IDs:
            self.fail(row, 1)
            return False
        self.success(row, 1)
        return True

    def interpolate(self, row, input_mesh):
        line_interpolators, distances, line_interpolators_internal, distances_internal = \
            input_mesh.get_line_interpolators([self.line])
        is_inside = True if distances_internal else False

        if not is_inside:
            self.fail(row, 2)
            return False, None
        self.success(row, 2)
        return True, distances_internal[0], line_interpolators_internal[0]

    def compute(self, input_data, line_interp):
        line_interpolator, distances = line_interp
        npt = len(distances)
        nplan = input_data.header.nb_planes
        point_x = np.array([[distances[i]] * nplan for i in range(npt)])
        point_y = np.empty((npt, nplan))
        point_values = np.empty((npt, nplan))

        with Serafin.Read(input_data.filename, self.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time

            time_index = self.parent.plot_viewer.time_index
            z = input_stream.read_var_in_frame_as_3d(time_index, 'Z').T
            values = input_stream.read_var_in_frame_as_3d(time_index, self.current_var).T

        for i_pt, ((x, y, (i, j, k), interpolator), distance) in enumerate(zip(line_interpolator, distances)):
            point_y[i_pt] = interpolator.dot(z[[i, j, k]])
            point_values[i_pt] = interpolator.dot(values[[i, j, k]])

        triangles = [((ipt - 1) * nplan + iplan - 1, (ipt - 1) * nplan + iplan, ipt * nplan + iplan - 1)
                     for ipt in range(1, npt) for iplan in range(1, nplan)] + \
                    [((ipt - 1) * nplan + iplan, ipt * nplan + iplan - 1, ipt * nplan + iplan)
                     for ipt in range(1, npt) for iplan in range(1, nplan)]
        triang = mtri.Triangulation(point_x.flatten(), point_y.flatten(), triangles)

        return triang, point_values.flatten()

    def run(self):
        # load serafin
        successful_rows, successful_input_data = self.first_step()

        nb_successes = 0
        for row, input_data in zip(successful_rows, successful_input_data):
            # interpolation
            mesh = self.build_mesh(input_data)
            success, distances, line_interp = self.interpolate(row, mesh)
            if not success:
                continue

            # export PNG
            triang, point_values = self.compute(input_data, line_interp)
            self.parent.plot(triang, point_values, self.png_names[row])
            self.success(row, 3)
            nb_successes += 1

        self.finishing_up(nb_successes)


class ScalarMapCanvas(MapCanvas):
    def __init__(self):
        super().__init__()
        self.cmap = None

    def replot(self, mesh, values, color_style, limits, variable_label):
        self.fig.clear()   # remove the old color bar
        self.axes = self.fig.add_subplot(111)
        self.axes.set_xlabel(settings.X_AXIS_LABEL)
        self.axes.set_ylabel(settings.Y_AXIS_LABEL)
        self.axes.set_aspect('equal', adjustable='box')

        triang = mtri.Triangulation(mesh.x, mesh.y, mesh.ikle)
        if limits is not None:
            levels = np.linspace(limits[0], limits[1], settings.NB_COLOR_LEVELS)
            self.axes.tricontourf(triang, values, cmap=color_style, levels=levels, extend='both',
                                  vmin=limits[0], vmax=limits[1])
        else:
            levels = build_levels_from_minmax(np.nanmin(values), np.nanmax(values))
            self.axes.tricontourf(triang, values, cmap=color_style, levels=levels, extend='both')

        # add colorbar
        divider = make_axes_locatable(self.axes)
        cax = divider.append_axes('right', size='5%', pad=0.2)
        cax.set_title(variable_label)
        self.cmap = cm.ScalarMappable(cmap=color_style)
        self.cmap.set_array(levels)
        self.fig.colorbar(self.cmap, cax=cax)
        self.draw()


class ScalarMapViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.data = None
        self.current_var = ''
        self.time_index = -1
        self.mesh = None
        self.values = []

        self.color_limits = None
        self.cmap = None
        self.current_style = settings.DEFAULT_COLOR_STYLE
        self.color_styles = settings.COLOR_SYLES

        self.canvas = ScalarMapCanvas()
        self.slider = SimpleTimeDateSelection()
        self.slider.index.editingFinished.connect(self.select_frame)
        self.slider.value.textChanged.connect(lambda text: self.select_frame())

        # add the the default tool bar
        self.default_toolbar = NavigationToolbar2QT(self.canvas, self)
        self.default_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.second_toolbar = QToolBar()
        self.second_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.select_variable_act = QAction('Select\nvariable', self, triggered=self.select_variable,
                                           icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.change_color_style_act = QAction('Change\ncolor style', self, triggered=self.change_color_style,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.change_color_range_act = QAction('Change\ncolor range', self, triggered=self.change_color_range,
                                              icon=self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.second_toolbar.addAction(self.select_variable_act)
        self.second_toolbar.addSeparator()
        self.second_toolbar.addAction(self.change_color_style_act)
        self.second_toolbar.addAction(self.change_color_range_act)
        self.second_toolbar.addSeparator()
        self.second_toolbar.addWidget(self.slider)

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.canvas)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.default_toolbar)
        vlayout.addWidget(self.second_toolbar)
        vlayout.addWidget(self.scrollArea)
        vlayout.setSpacing(0)
        vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vlayout)

        self.setWindowTitle('Scalar Map Viewer')
        self.resize(self.sizeHint())

    def select_variable(self):
        msg = QDialog()
        combo = QComboBox()
        combo.setFixedHeight(30)
        for var, name in zip(self.data.header.var_IDs, self.data.header.var_names):
            combo.addItem(var + ' (%s)' % name.decode(Serafin.SLF_EIT).strip())
        combo.setCurrentIndex(self.data.header.var_IDs.index(self.current_var))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a variable'))
        vlayout.addWidget(combo)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText().split(' (')[0]
        self.color_limits = None
        self.replot(compute=True)

    def change_color(self, style):
        self.current_style = style
        self.replot(compute=False)

    def change_color_style(self):
        msg = ColorMapStyleDialog(self)
        if msg.exec_() == QDialog.Accepted:
            self.change_color(msg.color_box.currentText())

    def change_color_range(self):
        value, ok = QInputDialog.getText(None, 'Change color bar range',
                                         'Enter the new color range',
                                         text=', '.join(map(lambda x: '{:+f}'.format(x),
                                                            self.canvas.cmap.get_clim())))
        if not ok:
            return
        try:
            cmin, cmax = map(float, value.split(','))
        except ValueError:
            QMessageBox.critical(self, 'Error', 'Invalid input.', QMessageBox.Ok)
            return
        if cmax <= cmin:
            QMessageBox.critical(self, 'Error', 'Values are not increasing.', QMessageBox.Ok)
            return

        self.color_limits = (cmin, cmax)
        self.replot(False)

    def select_frame(self):
        text = self.slider.index.text()
        try:
            index = int(text) - 1
        except ValueError:
            self.slider.index.setText(str(self.time_index+1))
            self.slider.slider.enterIndexEvent()
            return
        if 0 <= index < len(self.data.time):
            self.time_index = index
            self.replot(compute=True)

    def get_data(self, input_data, input_mesh):
        self.data = input_data
        self.mesh = input_mesh

        self.color_limits = None
        if 'B' in self.data.header.var_IDs:
            self.current_var = 'B'
        else:
            self.current_var = self.data.header.var_IDs[0]

        self.slider.initTime(self.data.time, list(map(lambda x: x + self.data.start_time, self.data.time_second)))
        self.replot(True)

    def compute(self):
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            values = input_stream.read_var_in_frame(self.time_index, self.current_var)
        return values

    def replot(self, compute):
        if compute:
            self.values = self.compute()
        self.canvas.replot(self.mesh, self.values, self.current_style, self.color_limits, self.current_var)


class VectorMapCanvas(MapCanvas):
    def __init__(self):
        super().__init__()
        self.cmap = None

    def replot(self, mesh, values):
        self.initFigure(mesh)
        self.axes.quiver(mesh.x, mesh.y, values[0], values[1], color='Teal')
        self.draw()


class VectorMapViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.current_couple = ('', '')
        self.time_index = -1
        self.data = None
        self.couples = []
        self.mesh = None
        self.values = ([], [])

        self.canvas = VectorMapCanvas()
        self.slider = SimpleTimeDateSelection()
        self.slider.index.editingFinished.connect(self.select_frame)
        self.slider.value.textChanged.connect(lambda text: self.select_frame())

        # add the the default tool bar
        self.default_toolbar = NavigationToolbar2QT(self.canvas, self)
        self.default_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.second_toolbar = QToolBar()
        self.second_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.select_variable_act = QAction('Select\nvariable', self, triggered=self.select_variable,
                                           icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.second_toolbar.addAction(self.select_variable_act)
        self.second_toolbar.addSeparator()
        self.second_toolbar.addWidget(self.slider)

        self.scrollArea = QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.canvas)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.default_toolbar)
        vlayout.addWidget(self.second_toolbar)
        vlayout.addWidget(self.scrollArea)
        vlayout.setSpacing(0)
        vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vlayout)

        self.setWindowTitle('Vector Map Viewer')
        self.resize(self.sizeHint())

    def select_variable(self):
        msg = QDialog()
        combo = QComboBox()
        combo.setFixedHeight(30)
        for brother, sister in self.couples:
            combo.addItem('(%s, %s)' % (brother, sister))
        combo.setCurrentIndex(self.couples.index(self.current_couple))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        vlayout.addWidget(QLabel('Select a vector field'))
        vlayout.addWidget(combo)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a vector field to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_couple = combo.currentText()[1:-1].split(', ')
        self.replot(compute=True)

    def select_frame(self):
        text = self.slider.index.text()
        try:
            index = int(text) - 1
        except ValueError:
            self.slider.index.setText(str(self.time_index+1))
            self.slider.slider.enterIndexEvent()
            return
        if 0 <= index < len(self.data.time):
            self.time_index = index
            self.replot(compute=True)

    def get_data(self, input_data, input_mesh, couples):
        self.data = input_data
        self.mesh = input_mesh
        self.couples = couples
        self.current_couple = self.couples[0]
        self.slider.initTime(self.data.time, list(map(lambda x: x + self.data.start_time, self.data.time_second)))
        self.replot(True)

    def compute(self):
        with Serafin.Read(self.data.filename, self.data.language) as input_stream:
            input_stream.header = self.data.header
            values = (input_stream.read_var_in_frame(self.time_index, self.current_couple[0]),
                      input_stream.read_var_in_frame(self.time_index, self.current_couple[1]))
        return values

    def replot(self, compute):
        if compute:
            self.values = self.compute()
        self.canvas.replot(self.mesh, self.values)
