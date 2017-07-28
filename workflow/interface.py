import sys
from PyQt5.QtWidgets import *
from workflow.mono_gui import MonoWidget
from workflow.multi_gui import MultiWidget


class ProjectWindow(QWidget):
    def __init__(self, welcome):
        super().__init__()
        self.welcome = welcome
        self.mono = MonoWidget(self)
        self.multi = MultiWidget(self)
        self.tab = QTabWidget()
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 150px; }')

        self.tab.addTab(self.mono, 'Mono')
        self.tab.addTab(self.multi, 'Multi')

        self.tab.currentChanged.connect(self.switch_tab)
        layout = QVBoxLayout()
        layout.addWidget(self.tab)
        self.setLayout(layout)

        self.filename = ''

    def load(self, filename):
        if not self.mono.scene.load(filename):
            return False
        if not self.multi.scene.load(filename):
            return False
        self.filename = filename
        return True

    def save(self):
        suffix = self.mono.scene.suffix_pool()
        if len(suffix) != len(set(suffix)):
            return False

        with open(self.filename, 'w') as f:
            for line in self.mono.scene.save():
                f.write(line)
                f.write('\n')
            if not self.mono.scene.not_connected():
                for line in self.multi.scene.save():
                    f.write(line)
                    f.write('\n')
        return True

    def create_new(self, filename):
        self.filename = filename
        with open(self.filename, 'w') as f:
            for line in self.mono.scene.save():
                f.write(line)
                f.write('\n')

    def switch_tab(self, index):
        if index == 1:
            self.mono_to_multi()
        else:
            self.multi_to_mono()

    def mono_to_multi(self):
        if not self.save():
            self.tab.setCurrentIndex(0)
            QMessageBox.critical(None, 'Error', 'You have duplicated suffix.', QMessageBox.Ok)
            return
        if self.mono.scene.not_connected():
            self.tab.setCurrentIndex(0)
            QMessageBox.critical(None, 'Error', 'You have disconnected nodes.', QMessageBox.Ok)
            return
        self.load(self.filename)

    def multi_to_mono(self):
        self.save()
        self.load(self.filename)

    def closeEvent(self, event):
        if not self.save():
            value = QMessageBox.question(None, 'Confirm exit', 'Are your sure to exit?\n'
                                         '(The project cannot be saved because it has duplicated suffix)',
                                         QMessageBox.Ok | QMessageBox.Cancel)
            if value == QMessageBox.Cancel:
                return
        self.welcome.show()


class ProjectWelcome(QWidget):
    def __init__(self):
        super().__init__()
        self.window = ProjectWindow(self)

        left_button = QPushButton('Create New\nProject')
        right_button = QPushButton('Load\nExisting\nProject')
        for bt in [left_button, right_button]:
            bt.setFixedSize(200, 150)

        left_button.clicked.connect(self.choose_left)
        right_button.clicked.connect(self.choose_right)

        vlayout = QHBoxLayout()
        vlayout.addWidget(left_button)
        vlayout.addWidget(right_button)
        self.setLayout(vlayout)
        self.setWindowTitle('TelTools')

        self.new = False
        self.filename = ''

    def choose_left(self):
        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the project file name', '',
                                                  'All Files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.new = True
        self.filename = filename
        self.open_project()

    def choose_right(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Choose the project file', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.new = False
        self.filename = filename
        self.open_project()

    def open_project(self):
        if self.new:
            self.window.mono.scene.reinit()
            self.window.multi.scene.reinit()
            self.window.create_new(self.filename)
            self.window.tab.setCurrentIndex(0)
            self.window.showMaximized()
            self.hide()
        else:
            if self.window.load(self.filename):
                self.window.tab.setCurrentIndex(0)
                self.window.showMaximized()
                self.hide()
            else:
                QMessageBox.critical(None, 'Error', 'The project file is not valid.', QMessageBox.Ok)


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
    widget = ProjectWelcome()
    widget.show()
    app.exec_()




