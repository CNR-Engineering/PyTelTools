import os
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from workflow.MultiNode import MultiNode, MultiOneInOneOutNode, \
                               MultiSingleOutputNode, MultiDoubleInputNode, MultiTwoInOneOutNode
import slf.variables as variables
import slf.misc as operations


class MultiLoadSerafinNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin'
        self.state = MultiNode.NOT_CONFIGURED

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

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiLoadPolygon2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPolygons'

    def load(self, options):
        if not options[0]:
            self.state = MultiNode.NOT_CONFIGURED
        else:
            self.options = tuple(options)


class MultiLoadOpenPolyline2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nOpen\nPolylines'

    def load(self, options):
        if not options[0]:
            self.state = MultiNode.NOT_CONFIGURED
        else:
            self.options = tuple(options)


class MultiLoadPoint2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPoints'

    def load(self, options):
        if not options[0]:
            self.state = MultiNode.NOT_CONFIGURED
        else:
            self.options = tuple(options)


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
            all_slfs = set()
            for path in self.dir_paths:
                slfs = set()
                for f in os.listdir(path):
                    if os.path.isfile(os.path.join(path, f)) and f[-4:] == '.slf':
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
            if not filtered_name:   # please do not name a directory with only special letters :D
                filtered_name = 'default__'
            name_item, id_item = QTableWidgetItem(name), QTableWidgetItem(filtered_name)
            name_item.setFlags(Qt.NoItemFlags)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, id_item)
        self.success = True


class MultiConvertToSinglePrecisionNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Convert to\nSingle\nPrecision'


class MultiComputeMaxNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max'


class MultiArrivalDurationNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nArrival\nDuration'

    def load(self, options):
        table = []
        conditions = []
        str_conditions, str_table, time_unit = options
        str_table = str_table.split(',')
        for i in range(int(len(str_table)/3)):
            line = []
            for j in range(3):
                line.append(str_table[3*i+j])
            table.append(line)
        if not table:
            self.state = MultiNode.NOT_CONFIGURED
            return
        str_conditions = str_conditions.split(',')
        for i, condition in zip(range(len(table)), str_conditions):
            literal = table[i][0]
            condition = condition.split()
            expression = condition[:-2]
            comparator = condition[-2]
            threshold = float(condition[-1])
            conditions.append(operations.Condition(expression, literal, comparator, threshold))
        self.options = (table, conditions, time_unit)


class MultiComputeVolumeNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nVolume'

    def load(self, options):
        first, second, sup = options[0:3]
        suffix = options[3]
        in_source_folder = bool(int(options[4]))
        dir_path = options[5]
        double_name = bool(int(options[6]))
        overwrite = bool(int(options[7]))
        if first:
            first_var = first
        else:
            self.state = MultiNode.NOT_CONFIGURED
            return
        if second:
            second_var = second
        else:
            second_var = None
        sup_volume = bool(int(sup))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiComputeFluxNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nFlux'

    def load(self, options):
        flux_options = options[0]
        if not flux_options:
            self.state = MultiNode.NOT_CONFIGURED
            return
        suffix = options[1]
        in_source_folder = bool(int(options[2]))
        dir_path = options[3]
        double_name = bool(int(options[4]))
        overwrite = bool(int(options[5]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (flux_options, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiInterpolateOnPointsNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\non\nPoints'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiInterpolateAlongLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\nalong\nLines'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiProjectLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Project\nLines'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        reference_index = int(options[5])
        if reference_index == -1:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite, reference_index)


class MultiComputeMinNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min'


class MultiComputeMeanNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Mean'


class MultiSynchMaxNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'SynchMax'

    def load(self, options):
        self.options = (options[0],)


class MultiSelectFirstFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nFirst\nFrame'


class MultiSelectLastFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nLast\nFrame'


class MultiSelectTimeNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nTime'

    def load(self, options):
        str_start_date, str_end_date = options[0:2]
        if not str_start_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        start_date = datetime.strptime(str_start_date, '%Y/%m/%d %H:%M:%S')
        end_date = datetime.strptime(str_end_date, '%Y/%m/%d %H:%M:%S')
        sampling_frequency = int(options[2])
        self.options = (start_date, end_date, sampling_frequency)


class MultiSelectSingleFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nSingle\nFrame'

    def load(self, options):
        str_date = options[0]
        if not str_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (datetime.strptime(str_date, '%Y/%m/%d %H:%M:%S'),)


class MultiSelectVariablesNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nVariables'

    def load(self, options):
        friction_law, vars, names, units = options
        friction_law = int(friction_law)
        if friction_law > -1:
            us_equation = variables.get_US_equation(friction_law)
        else:
            us_equation = None

        if not vars:
            self.state = MultiNode.NOT_CONFIGURED
            return

        selected_vars = []
        selected_vars_names = {}
        for var, name, unit in zip(vars.split(','), names.split(','), units.split(',')):
            selected_vars.append(var)
            selected_vars_names[var] = (bytes(name, 'utf-8').ljust(16), bytes(unit, 'utf-8').ljust(16))
        self.options = (us_equation, selected_vars, selected_vars_names)


class MultiAddRouseNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nRouse'

    def load(self, options):
        values, str_table = options
        str_table = str_table.split(',')
        table = []
        if not values:
            self.state = MultiNode.NOT_CONFIGURED
            return
        for i in range(0, len(str_table), 3):
            table.append([str_table[i], str_table[i+1], str_table[i+2]])
        self.options = (table,)


class MultiMinusNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'A Minus B'


class MultiReverseMinusNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'B Minus A'


class MultiProjectMeshNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Project B\non A'


class MultiMaxBetweenNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max(A,B)'


class MultiMinBetweenNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min(A,B)'

