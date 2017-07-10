import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import workflow.multi_func as worker
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
        self.red = QColor(255, 160, 160, 255)

        self.setRowCount(1)
        self.setColumnCount(0)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalHeaderLabels(['Load Serafin'])

        self.input_columns = {}
        self.yellow_nodes = {}

    def reinit(self):
        self.setRowCount(1)
        self.setVerticalHeaderLabels(['Load Serafin'])
        self.setColumnCount(0)
        self.input_columns = {}
        self.yellow_nodes = {}

    def update_rows(self, nodes, ordered_nodes):
        self.setRowCount(len(ordered_nodes))
        self.setColumnCount(0)
        self.setVerticalHeaderLabels([nodes[u].name() for u in ordered_nodes])
        self.input_columns = {}
        self.yellow_nodes = {}

    def add_files(self, node_index, new_ids, downstream_nodes):
        self.input_columns[node_index] = []
        self.yellow_nodes[node_index] = downstream_nodes
        offset = self.columnCount()
        self.setColumnCount(offset + len(new_ids))

        new_labels = []
        for j in range(offset):
            new_labels.append(self.horizontalHeaderItem(j).text())
        new_labels.extend(new_ids)
        self.setHorizontalHeaderLabels(new_labels)

        for j in range(len(new_ids)):
            self.input_columns[node_index].append(offset+j)
            for i in range(self.rowCount()):
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if i in downstream_nodes:
                    self.item(i, offset+j).setBackground(self.yellow)
                else:
                    self.item(i, offset+j).setBackground(self.grey)

    def update_files(self, node_index, new_ids):
        new_labels = []
        old_input_nodes = [u for u in self.input_columns.keys() if u != node_index]
        old_input_nb = {}
        for input_node in old_input_nodes:
            old_input_nb[input_node] = len(self.input_columns[input_node])
            for j in self.input_columns[input_node]:
                new_labels.append(self.horizontalHeaderItem(j).text())

        new_labels.extend(new_ids)   # modified input nodes always at end of the table
        self.input_columns = {}  # all columns could be shuffled

        self.setColumnCount(len(new_labels))
        self.setHorizontalHeaderLabels(new_labels)

        # rebuild the whole table
        offset = 0
        for input_node in old_input_nodes:
            self.input_columns[input_node] = []
            for j in range(old_input_nb[input_node]):
                self.input_columns[input_node].append(offset+j)
                for i in range(self.rowCount()):
                    item = QTableWidgetItem()
                    self.setItem(i, offset+j, item)
                    if i in self.yellow_nodes[input_node]:
                        self.item(i, offset+j).setBackground(self.yellow)
                    else:
                        self.item(i, offset+j).setBackground(self.grey)
            offset += old_input_nb[input_node]
        self.input_columns[node_index] = []
        for j in range(len(new_ids)):
            self.input_columns[node_index].append(offset+j)
            for i in range(self.rowCount()):
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if i in self.yellow_nodes[node_index]:
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
        self.reload_act = QAction('Refresh workspace\n(F3)', self, triggered=self.reload, shortcut='F3')

        self.run_act = QAction('Run\n(F5)', self, triggered=self.run, shortcut='F5')
        self.init_toolbar()

        self.message_box = QPlainTextEdit()
        self.message_box.setReadOnly(True)
        self.workspace = ''

        left_panel = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setLayout(layout)

        right_panel = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.message_box)
        layout.setContentsMargins(0, 0, 0, 0)
        right_panel.setLayout(layout)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(1, 1)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        self.worker = worker.Workers()

    def init_toolbar(self):
        for act in [self.save_act, self.load_act, self.reload_act, self.run_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)
            self.toolbar.addSeparator()

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
        if self.view.scene().load(filename):
            self.workspace = filename

    def reload(self):
        if not self.workspace:
            return
        if self.view.scene().load(self.workspace):
            QMessageBox.information(None, 'Success', 'Workspace updated!', QMessageBox.Ok)

    def run(self):
        if not self.view.scene().ready_to_run:
            return

        self.setEnabled(False)
        # initial tasks
        init_tasks = []
        finished = {}
        for node_id in self.view.scene().ordered_input_indices:
            paths, name, job_ids = self.view.scene().inputs[node_id]
            for path, job_id, fid in zip(paths, job_ids, self.table.input_columns[node_id]):
                init_tasks.append((worker.read_slf, (node_id, fid, os.path.join(path, name),
                                                     self.view.scene().language, job_id)))
                finished[fid] = False

        self.worker.start(init_tasks)
        while not self.worker.stopped:
            success, node_id, fid, data, message = self.worker.done_queue.get()
            self.message_box.appendPlainText(message)

            if success:
                self.table.item(node_id, fid).setBackground(self.table.green)
                QApplication.processEvents()

                next_nodes = self.view.scene().adj_list[node_id]
                if not next_nodes:
                    finished[fid] = True

                for next_node_id in next_nodes:
                    next_node = self.view.scene().nodes[next_node_id]
                    fun = worker.FUNCTIONS[next_node.name()]
                    self.worker.task_queue.put((fun, (next_node_id, fid, data, next_node.options)))

            else:
                self.table.item(node_id, fid).setBackground(self.table.red)
                QApplication.processEvents()
                finished[fid] = True

            if all(finished.values()):
                self.worker.stop()

        self.message_box.appendPlainText('Done!')
        self.setEnabled(True)
        self.worker = worker.Workers()



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
