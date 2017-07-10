import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from workflow.MultiNode import MultiNode, MultiOneInOneOutNode, MultiSingleOutputNode


class MultiLoadSerafinNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin'
        self.state = MultiNode.NOT_CONFIGURED

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), '', '', ''])

    def configure(self, old_options):
        dlg = MultiLoadSerafinDialog(old_options)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.success:
                self.state = MultiNode.READY
                return True, [dlg.dir_paths, dlg.slf_name, dlg.job_ids]
        return False, []


class MultiWriteSerafinNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write\nSerafin'

        self.suffix = ''
        self.in_source_folder = True
        self.dir_path = ''
        self.double_name = False
        self.overwrite = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.suffix,
                         str(int(self.in_source_folder)), self.dir_path,
                         str(int(self.double_name)), str(int(self.overwrite))])

    def load(self, options):
        self.suffix = options[0]
        self.in_source_folder = bool(int(options[1]))
        self.dir_path = options[2]
        self.double_name = bool(int(options[3]))
        self.overwrite = bool(int(options[4]))


class MultiLoadSerafinDialog(QDialog):
    def __init__(self, old_options):
        super().__init__()
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
        self.setWindowTitle('Select input files')

    def check(self):
        if not self.success:
            self.reject()
            return
        self.slf_name = self.file_box.currentText()
        self.job_ids = []
        for row in range(self.table.rowCount()):
            job_id = self.table.item(row, 1).text()
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
            self.dir_paths.append(os.path.join(current_dir, name))
        if not self.dir_paths:
            QMessageBox.critical(None, 'Error', 'Choose at least one folder.',
                                 QMessageBox.Ok)
            return

        all_slfs = set()
        for name, path in zip(dir_names, self.dir_paths):
            slfs = set()
            for f in os.listdir(path):
                if os.path.isfile(os.path.join(path, f)) and f[-4:] == '.slf':
                    slfs.add(f)
            if not slfs:
                QMessageBox.critical(None, 'Error', "The folder %s doesn't have any .slf file!" % name,
                                     QMessageBox.Ok)
                self.dir_paths = []
                return
            if not all_slfs:
                all_slfs = slfs.copy()
            else:
                all_slfs.intersection_update(slfs)
            if not all_slfs:
                QMessageBox.critical(None, 'Error', 'These folder do not share identical .slf file names!',
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
            name_item, id_item = QTableWidgetItem(name), QTableWidgetItem(filtered_name)
            name_item.setFlags(Qt.NoItemFlags)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, id_item)
        self.success = True
