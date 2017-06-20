import sys

from PyQt5.QtWidgets import *
from gui.MainWindow import MyMainWindow as GUIWindow
from workflow.interface import MyMainWindow as WorkflowWindow


class HelloWorld(QDialog):
    def __init__(self):
        super().__init__()
        self.choice = None
        left_button = QPushButton('Classic\nInterface')
        right_button = QPushButton('Workflow\nInterface\n(Experimental)')
        for bt in [left_button, right_button]:
            bt.setFixedSize(150, 200)

        left_button.clicked.connect(self.choose_left)
        right_button.clicked.connect(self.choose_right)

        vlayout = QHBoxLayout()
        vlayout.addWidget(left_button)
        vlayout.addWidget(right_button)
        self.setLayout(vlayout)

    def choose_left(self):
        self.choice = 1
        self.accept()

    def choose_right(self):
        self.choice = 2
        self.accept()


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
    dlg = HelloWorld()
    value = dlg.exec_()
    if value == QDialog.Accepted:
        if dlg.choice == 1:
            widget = GUIWindow()
        else:
            widget = WorkflowWindow()
        widget.showMaximized()
    else:
        sys.exit(0)
    app.exec_()

