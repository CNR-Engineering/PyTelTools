from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QPushButton)
import sys

from pyteltools.gui.classic_gui import ClassicMainWindow as GUIWindow
from pyteltools.workflow.workflow_gui import WorkflowWelcomeWindow


class HelloWorld(QDialog):
    def __init__(self):
        super().__init__()
        self.choice = None
        left_button = QPushButton('Classic\nInterface')
        right_button = QPushButton('Workflow\nInterface')
        for bt in [left_button, right_button]:
            bt.setFixedSize(150, 200)

        left_button.clicked.connect(self.choose_left)
        right_button.clicked.connect(self.choose_right)

        vlayout = QHBoxLayout()
        vlayout.addWidget(left_button)
        vlayout.addWidget(right_button)
        self.setLayout(vlayout)
        self.setWindowTitle('PyTelTools')

    def choose_left(self):
        self.choice = 1
        self.accept()

    def choose_right(self):
        self.choice = 2
        self.accept()


def run_gui_app():
    app = QApplication(sys.argv)
    dlg = HelloWorld()
    value = dlg.exec_()
    if value == QDialog.Accepted:
        if dlg.choice == 1:
            widget = GUIWindow()
            widget.showMaximized()
        else:
            widget = WorkflowWelcomeWindow()
            widget.show()
    else:
        sys.exit(0)
    app.exec_()


if __name__ == '__main__':
    run_gui_app()
