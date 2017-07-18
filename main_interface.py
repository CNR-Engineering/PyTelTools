import sys

from PyQt5.QtWidgets import *
from gui.MainWindow import MyMainWindow as GUIWindow
from workflow.interface import ProjectWelcome


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
        self.setWindowTitle('TelTools')

    def choose_left(self):
        self.choice = 1
        self.accept()

    def choose_right(self):
        self.choice = 2
        self.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    dlg = HelloWorld()
    value = dlg.exec_()
    if value == QDialog.Accepted:
        if dlg.choice == 1:
            widget = GUIWindow()
            widget.showMaximized()
        else:
            widget = ProjectWelcome()
            widget.show()
    else:
        sys.exit(0)
    app.exec_()

