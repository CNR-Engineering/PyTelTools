import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


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
                QMessageBox.critical(None, 'Error', 'These folder do not share identical %s file names!' % self.extension,
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


class VerticalProfilePlotViewer():
    def __init__(self):
        pass

    def get_data(self, data, points):
        pass
