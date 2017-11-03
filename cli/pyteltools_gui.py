#!/usr/bin/env python
"""
Run PyTelTools GUI: classic or workflow interface
"""

from PyQt5.QtWidgets import QApplication
import sys

from pyteltools.gui.classic_gui import exception_hook, ClassicMainWindow
from pyteltools.main_interface import run_gui_app
from pyteltools.utils.cli import PyTelToolsArgParse
from pyteltools.workflow.workflow_gui import WorkflowWelcomeWindow


def exec_gui(window):
    """
    Execute a simple GUI application
    @param window <PyQt5.QtWidgets.QWidget>: window to display
    """
    app = QApplication(sys.argv)
    window = window()
    window.show()
    app.exec_()


parser = PyTelToolsArgParse(description=__doc__)
parser.add_argument('-c', '--interface', help='select and open corresponding GUI', choices=('classic', 'workflow'))


if __name__ == '__main__':
    args = parser.parse_args()

    # suppress explicitly traceback silencing
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    if args.interface is None:
        run_gui_app()
    else:
        if args.interface == 'classic':
            exec_gui(ClassicMainWindow)
        elif args.interface == 'workflow':
            exec_gui(WorkflowWelcomeWindow)
