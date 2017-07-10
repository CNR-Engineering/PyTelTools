import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from workflow.multi_func import read_slf, Workers
from workflow.MultiTree import MultiTreeScene


class MultiTreeView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(MultiTreeScene())
        self.parent = parent
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setAcceptDrops(True)
        self.current_node = None

    def resizeEvent(self, event):
        self.scene().setSceneRect(QRectF(0, 0, self.width()-10, self.height()-10))


class MultiTreePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.view = MultiTreeView(self)

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

        right_panel = QWidget()

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

        self.proc = Workers()

    def run(self):
        if self.proc.stopped:
            print('cannot re-run.')
            return
        # initial tasks
        tasks = [(read_slf, ('../testdata/test.slf', 0)), (read_slf, ('../testdata/test_copy.slf', 1))]
        self.proc.start(tasks)

        while not self.proc.stopped:
            success, job_id = self.proc.done_queue.get()
            if job_id == 1:
                self.proc.task_queue.put((read_slf, ('../testdata/testcopy.slf', 2)))
            elif job_id == 2:
                self.proc.stop()
        print('stopped')

    def init_toolbar(self):
        for act in [self.save_act, self.load_act, self.run_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)
            self.toolbar.addSeparator()

    def save(self):
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
