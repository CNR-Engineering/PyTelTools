import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from workflow.multi_func import read_slf, Workers
from workflow.MultiTree import MultiTreeScene


class MultiTreeView(QGraphicsView):
    def __init__(self, parent, table):
        super().__init__(MultiTreeScene(table))
        self.parent = parent
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setAcceptDrops(True)
        self.current_node = None

    def resizeEvent(self, event):
        self.scene().setSceneRect(QRectF(0, 0, self.width()-10, self.height()-10))


class MultiTreeTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.yellow = QColor(245, 255, 207, 255)
        self.green = QColor(180, 250, 165, 255)
        self.grey = QColor(211, 211, 211, 255)

        self.setRowCount(1)
        self.setColumnCount(0)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalHeaderLabels(['Load Serafin'])

        self.input_columns = {}

    def update_rows(self, nodes, ordered_nodes):
        self.setRowCount(len(ordered_nodes))
        self.setColumnCount(0)
        self.setVerticalHeaderLabels([nodes[u].name() for u in ordered_nodes])

    def update_columns(self, node_index, new_ids, downstream_nodes):
        if node_index not in self.input_columns:
            self.add_files(node_index, new_ids, downstream_nodes)
        else:
            self.update_files(node_index, new_ids, downstream_nodes)

    def add_files(self, node_index, new_ids, downstream_nodes):
        self.input_columns[node_index] = []
        offset = self.columnCount()
        self.setColumnCount(offset + len(new_ids))

        new_labels = []
        for j in range(offset):
            new_labels.append(self.horizontalHeaderItem(j).text())
        new_labels.extend(new_ids)
        self.setHorizontalHeaderLabels(new_labels)

        for i in range(self.rowCount()):
            for j in range(len(new_ids)):
                self.input_columns[node_index].append(offset+j)
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if i in downstream_nodes:
                    self.item(i, offset+j).setBackground(self.yellow)
                else:
                    self.item(i, offset+j).setBackground(self.grey)

    def update_files(self, node_index, new_ids, downstream_nodes):
        old_columns = self.input_columns[node_index]
        new_labels = []
        offset = 0
        old_items = {}
        for i in range(self.rowCount()):
            old_items[i] = []

        for j in range(self.columnCount()):
            if j in old_columns:
                continue
            offset += 1
            new_labels.append(self.horizontalHeaderItem(j).text())
            for i in range(self.rowCount()):
                old_items[i].append(self.item(i, j))
        new_labels.extend(new_ids)
        self.setColumnCount(len(new_labels))
        self.setHorizontalHeaderLabels(new_labels)

        for i in range(self.rowCount()):
            for j in range(offset):
                self.setItem(i, j, old_items[i][j])
            for j in range(len(new_ids)):
                self.input_columns[node_index].append(offset+j)
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if i in downstream_nodes:
                    self.item(i, offset+j).setBackground(self.yellow)
                else:
                    self.item(i, offset+j).setBackground(self.grey)


class MultiTreePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.table = MultiTreeTable()
        self.view = MultiTreeView(self, self.table)

        self.toolbar = QToolBar()
        self.node_label = QLineEdit()
        self.save_act = QAction('Save workspace\n(Ctrl+S)', self, triggered=self.save, shortcut='Ctrl+S')
        self.load_act = QAction('Load workspace\n(Ctrl+O)', self, triggered=self.load, shortcut='Ctrl+O')

        self.run_act = QAction('Run\n(F5)', self, triggered=self.run, shortcut='F5')
        self.init_toolbar()

        left_panel = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setLayout(layout)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(self.table)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(1, 1)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        self.proc = Workers()

    def init_toolbar(self):
        for act in [self.save_act, self.load_act, self.run_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)
            self.toolbar.addSeparator()

    def run(self):
        if not self.view.scene().ready_to_run:
            return
        if self.proc.stopped:
            print('cannot re-run.')
            return

        # initial tasks
        init_tasks = []
        fid = 0
        for node_index in self.view.scene().ordered_input_indices:
            paths, name, job_ids = self.view.scene().inputs[node_index]
            for path, job_id in zip(paths, job_ids):
                init_tasks.append((read_slf, (os.path.join(path, name), self.view.scene().language, job_id, fid)))
                fid += 1
        self.proc.start(init_tasks)

        while not self.proc.stopped:
            success, fid, data = self.proc.done_queue.get()
            if fid == 1:
                self.proc.task_queue.put((read_slf, ('../testdata/testcopy.slf', 'fr', 'magic', 10)))
            elif fid == 10:
                self.proc.stop()
        print('stopped')

    def save(self):
        if not self.view.scene().ready_to_run:
            QMessageBox.critical(None, 'Error', 'Configure all input nodes before saving!',
                                 QMessageBox.Ok)
            return
        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.view.scene().save(filename)

    def load(self):
        msg = QMessageBox.warning(None, 'Confirm load',
                                  'Do you want to load workspace file?\n(Your current workspace will be erased)',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        filename, _ = QFileDialog.getOpenFileName(None, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.view.scene().load(filename)


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
    widget = MultiTreePanel()
    widget.show()
    app.exec_()
