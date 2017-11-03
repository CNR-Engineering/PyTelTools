import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from pyteltools.conf.settings import LANG, CSV_SEPARATOR, DIGITS, LOGGING_LEVEL

from .CalculatorGUI import CalculatorGUI
from .CompareResultsGUI import CompareResultsGUI
from .ComputeFluxGUI import ComputeFluxGUI
from .ComputeVolumeGUI import ComputeVolumeGUI
from .ConfigTransformation import TransformationMap
from .ExtractVariablesGUI import ExtractVariablesGUI
from .GeometryConverterGUI import FileConverterGUI
from .LinesGUI import LinesGUI
from .MaxMinMeanGUI import MaxMinMeanGUI
from .PointsGUI import PointsGUI
from .ProjectLinesGUI import ProjectLinesGUI
from .ProjectMeshGUI import ProjectMeshGUI


class GlobalConfigDialog(QDialog):
    def __init__(self, language, csv_separator):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok, Qt.Horizontal, self)
        buttons.accepted.connect(self._select)
        self.new_options = tuple()

        self.lang_box = QGroupBox('Input Serafin language')
        hlayout = QHBoxLayout()
        self.french_button = QRadioButton('French')
        english_button = QRadioButton('English')
        hlayout.addWidget(self.french_button)
        hlayout.addWidget(english_button)
        self.lang_box.setLayout(hlayout)
        self.lang_box.setMaximumHeight(80)
        if language == 'fr':
            self.french_button.setChecked(True)
        else:
            english_button.setChecked(True)

        self.csv_box = QComboBox()
        self.csv_box.setFixedHeight(30)
        for sep in ['Semicolon ;', 'Comma ,', 'Tab']:
            self.csv_box.addItem(sep)
        if csv_separator == ';':
            self.csv_box.setCurrentIndex(0)
        elif csv_separator == ',':
            self.csv_box.setCurrentIndex(1)
        else:
            self.csv_box.setCurrentIndex(2)

        layout = QVBoxLayout()
        layout.addWidget(self.lang_box)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('CSV separator'))
        hlayout.addWidget(self.csv_box, Qt.AlignLeft)
        layout.addLayout(hlayout)
        layout.setSpacing(20)
        layout.addStretch()
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('PyTelTools global configuration')
        self.resize(300, 200)

    def _select(self):
        separator = {0: ';', 1: ',', 2: '\t'}[self.csv_box.currentIndex()]
        language = ['en', 'fr'][self.french_button.isChecked()]
        self.new_options = (language, separator)
        self.accept()

    def closeEvent(self, event):
        separator = {0: ';', 1: ',', 2: '\t'}[self.csv_box.currentIndex()]
        language = ['en', 'fr'][self.french_button.isChecked()]
        self.new_options = (language, separator)


class MainPanel(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.extract = ExtractVariablesGUI(parent)
        self.maxmin = MaxMinMeanGUI(parent)
        self.points = PointsGUI(parent)
        self.lines = LinesGUI(parent)
        self.project = ProjectLinesGUI(parent)
        self.mesh = ProjectMeshGUI(parent)
        self.volume = ComputeVolumeGUI(parent)
        self.compare = CompareResultsGUI(parent)
        self.flux = ComputeFluxGUI(parent)

        trans = TransformationMap()
        self.conv = FileConverterGUI(parent)
        self.calc = CalculatorGUI(parent)

        self.stackLayout = QStackedLayout()
        self.stackLayout.addWidget(QLabel('Hello! This is the start page (TODO)'))
        self.stackLayout.addWidget(self.extract)
        self.stackLayout.addWidget(self.maxmin)
        self.stackLayout.addWidget(self.points)
        self.stackLayout.addWidget(self.lines)
        self.stackLayout.addWidget(self.project)
        self.stackLayout.addWidget(self.mesh)
        self.stackLayout.addWidget(self.volume)
        self.stackLayout.addWidget(self.flux)
        self.stackLayout.addWidget(self.compare)
        self.stackLayout.addWidget(trans)
        self.stackLayout.addWidget(self.conv)
        self.stackLayout.addWidget(self.calc)
        self.setLayout(self.stackLayout)

        self.stackLayout.currentChanged.connect(parent.autoResize)

    def switch_language(self, language):
        for widget in [self.extract, self.maxmin, self.points, self.lines, self.project, self.mesh,
                       self.volume, self.compare, self.flux, self.conv, self.calc]:
            widget.switch_language(language)


class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.language = LANG
        self.csv_separator = CSV_SEPARATOR
        self.digits = DIGITS
        self.logging_level = LOGGING_LEVEL
        self.panel = MainPanel(self)

        config_button = QPushButton('Global\nConfiguration')
        config_button.setMinimumHeight(40)
        config_button.clicked.connect(self.global_config)

        pageList = QListWidget()
        for name in ['Start', 'Extract variables', 'Max/Min/Mean/Arrival/Duration', 'Interpolate on points',
                     'Interpolate along lines', 'Project along lines', 'Project mesh',
                     'Compute volume', 'Compute flux', 'Compare two results',
                     'Transform coordinate systems', 'Convert geom file formats', 'Variable Calculator']:
            pageList.addItem('\n' + name + '\n')
        pageList.setFlow(QListView.TopToBottom)
        pageList.currentRowChanged.connect(self.panel.layout().setCurrentIndex)

        pageList.setCurrentRow(0)

        splitter = QSplitter()
        left_widget = QWidget()
        vlayout = QVBoxLayout()
        vlayout.addWidget(config_button)
        vlayout.addWidget(pageList)
        left_widget.setLayout(vlayout)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.panel)
        splitter.setHandleWidth(5)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        handle = splitter.handle(1)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        handle.setLayout(layout)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

        self.setWindowTitle('Main window')
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.frameGeom = self.frameGeometry()
        self.move(self.frameGeom.center())

    def global_config(self):
        dlg = GlobalConfigDialog(self.language, self.csv_separator)
        value = dlg.exec_()
        if value == QDialog.Accepted:
            self.language, self.csv_separator = dlg.new_options
            self.panel.switch_language(self.language)

    def autoResize(self, index):
        if not self.isMaximized():
            self.resize(self.panel.stackLayout.widget(index).sizeHint())

    def inDialog(self):
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.setEnabled(False)
        self.show()

    def outDialog(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.setEnabled(True)
        self.show()


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
    window = MyMainWindow()
    window.show()
    app.exec_()



