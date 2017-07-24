import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from slf import Serafin
import slf.misc as op
from geom import Shapefile
from gui.util import testOpen, TelToolWidget


class VariableList(QListWidget):
    def __init__(self, pool, editor):
        super().__init__()
        self.pool = pool
        for var, var_name in zip(pool.vars, pool.var_names):
            self.addItem('%s (%s)' % (var, var_name))
        for i in range(1, pool.nb_masks+1):
            self.addItem(pool.masks[i].code())
        for i in range(1, pool.nb_expressions+1):
            expr = pool.expressions[i]
            if not expr.masked:
                self.addItem(str(expr))
        self.setMaximumWidth(250)
        self.editor = editor
        self.old_format = self.editor.currentCharFormat()
        self.editor.cursorPositionChanged.connect(lambda: self.editor.setCurrentCharFormat(self.old_format))

        self.blue = '#554DF7'
        self.green = '#006400'
        self.red = '#CC0066'

    def colorful_text(self, text, color):
        self.editor.insertHtml("<span style=\" font-size:8pt; font-weight:600; color:%s;\" "
                               ">[%s]</span>" % (color, text))
        self.editor.setCurrentCharFormat(self.old_format)

    def mouseDoubleClickEvent(self, *args, **kwargs):
        var = self.currentItem().text()
        if var:
            if '(' in var and var.split(' (')[0] in self.pool.vars:  # variable
                var = var.split(' (')[0]
                self.colorful_text(var, self.blue)
            elif var[:4] == 'POLY':  # mask value
                self.colorful_text(var, self.red)
            else:  # expression
                expr = self.pool.get_expression(var)
                if expr.polygonal:
                    self.colorful_text(expr.code(), self.red)
                else:
                    self.colorful_text(expr.code(), self.green)
            self.clearSelection()


class ExpressionDialog(QDialog):
    def __init__(self, expr_pool):
        super().__init__()
        self.pool = expr_pool
        self.stack = QStackedLayout()
        self.stack.addWidget(self.build_first_page())
        self.stack.addWidget(self.build_second_page())
        self.stack.addWidget(self.build_third_page())
        self.stack.addWidget(self.build_fourth_page())
        self.stack.addWidget(self.build_fifth_page())
        self.setLayout(self.stack)
        self.setWindowTitle('Add expression')

    def build_first_page(self):
        first_page = QWidget()
        expression_type_box = QGroupBox('Select expression type')
        self.simple_button = QRadioButton('Simple expression\nUse variables, operators, numbers and existing'
                                          'expressions to create a new expression. Example: B+H+(V^2)/(2*9.81)')
        self.simple_button.setChecked(True)
        self.condition_button = QRadioButton('Conditional expression\nUse existing conditions and expressions'
                                             'to create a conditional expression. Example: IF (B > 0) THEN (B) ELSE (0)')
        self.max_min_button = QRadioButton('Max/Min between two expressions\nUse two existing expressions and'
                                           'MAX or MIN to create a new expression. Example: MAX(B, RB+0.5)')
        self.masked_button = QRadioButton('Masked expression\nUse an expression containing polygonal values '
                                          'and a non-polygonal expression\nto create a masked expression. '
                                          'Example: IF (POLY1) THEN (B+POLY1) ELSE (B)')

        self.condition_button.setEnabled(self.pool.ready_for_conditional_expression())
        self.max_min_button.setEnabled(self.pool.ready_for_max_min_expression())
        self.masked_button.setEnabled(self.pool.ready_for_masked_expression())
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.simple_button)
        vlayout.addWidget(self.condition_button)
        vlayout.addWidget(self.max_min_button)
        vlayout.addWidget(self.masked_button)
        expression_type_box.setLayout(vlayout)
        next_button = QPushButton('Next')
        cancel_button = QPushButton('Cancel')
        for bt in (next_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(next_button)
        hlayout.addWidget(cancel_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(expression_type_box)
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        first_page.setLayout(vlayout)

        next_button.clicked.connect(self.turn_page)
        cancel_button.clicked.connect(self.reject)
        return first_page

    def build_second_page(self):
        second_page = QWidget()
        self.expression_text = QTextEdit()
        var_list = VariableList(self.pool, self.expression_text)
        ok_button = QPushButton('OK')
        cancel_button = QPushButton('Cancel')
        for bt in (ok_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        lb = QLabel('Available variables and expressions')
        vlayout.addWidget(lb)
        vlayout.addWidget(var_list)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addLayout(vlayout)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('<p style="font-size:10pt">'
                                 '<b>Help</b>: double click on the list to add variables or existing expressions.<br>'
                                 'You can also enter operators, parentheses and numbers.<br>'
                                 'Supported operators: <tt>+ - * / ^ sqrt sin cos atan</tt>.</p>'))
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(QLabel('Expression Editor'))
        vlayout.addWidget(self.expression_text)
        hlayout.addLayout(vlayout)
        hlayout.setSpacing(10)
        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(cancel_button)
        vlayout.addLayout(hlayout)
        second_page.setLayout(vlayout)

        ok_button.clicked.connect(self.check)
        cancel_button.clicked.connect(self.reject)
        return second_page

    def build_third_page(self):
        third_page = QWidget()
        if not self.condition_button.isEnabled():
            return third_page
        self.condition_box = QComboBox()
        self.true_box = QComboBox()
        self.false_box = QComboBox()
        ok_button = QPushButton('OK')
        cancel_button = QPushButton('Cancel')
        for bt in (ok_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        for box in (self.condition_box, self.true_box, self.false_box):
            box.setFixedHeight(30)
            box.setMaximumWidth(250)
        for i in range(1, self.pool.nb_expressions+1):
            expr = self.pool.expressions[i]
            if expr.masked:
                continue
            self.true_box.addItem(str(expr))
            self.false_box.addItem(str(expr))
        for i in range(1, self.pool.nb_conditions+1):
            self.condition_box.addItem(str(self.pool.conditions[i]))
        vlayout = QVBoxLayout()
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Condition'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('True'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('False'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.condition_box, 2, 1)
        glayout.addWidget(self.true_box, 2, 2)
        glayout.addWidget(self.false_box, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        vlayout.addLayout(glayout)
        vlayout.addStretch()
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(cancel_button)
        vlayout.addLayout(hlayout)
        third_page.setLayout(vlayout)

        ok_button.clicked.connect(self.check)
        cancel_button.clicked.connect(self.reject)
        return third_page

    def build_fourth_page(self):
        fourth_page = QWidget()
        if not self.max_min_button.isEnabled():
            return fourth_page
        self.max_min_box = QComboBox()
        self.max_min_box.addItem('MAX')
        self.max_min_box.addItem('MIN')
        self.first_box = QComboBox()
        self.second_box = QComboBox()
        ok_button = QPushButton('OK')
        cancel_button = QPushButton('Cancel')
        for bt in (ok_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        for box in (self.first_box, self.second_box):
            box.setFixedHeight(30)
            box.setMaximumWidth(250)
        self.max_min_box.setFixedSize(100, 30)
        for i in range(1, self.pool.nb_expressions+1):
            expr = self.pool.expressions[i]
            if expr.masked:
                continue
            self.first_box.addItem(str(expr))
            self.second_box.addItem(str(expr))
        vlayout = QVBoxLayout()
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Condition'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('True'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('False'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.max_min_box, 2, 1)
        glayout.addWidget(self.first_box, 2, 2)
        glayout.addWidget(self.second_box, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        vlayout.addLayout(glayout)
        vlayout.addStretch()
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(cancel_button)
        vlayout.addLayout(hlayout)
        fourth_page.setLayout(vlayout)

        ok_button.clicked.connect(self.check)
        cancel_button.clicked.connect(self.reject)
        return fourth_page

    def build_fifth_page(self):
        fifth_page = QWidget()
        if not self.masked_button.isEnabled():
            return fifth_page
        self.poly_box = QComboBox()
        self.inside_box = QComboBox()
        self.outside_box = QComboBox()
        ok_button = QPushButton('OK')
        cancel_button = QPushButton('Cancel')
        for bt in (ok_button, cancel_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        for box in (self.poly_box, self.inside_box, self.outside_box):
            box.setFixedHeight(30)
            box.setMaximumWidth(250)
        for i in range(1, self.pool.nb_masks+1):
            mask = self.pool.masks[i]
            if mask.nb_children > 0:
                self.poly_box.addItem(mask.code())
        for i in range(1, self.pool.nb_expressions+1):
            expr = self.pool.expressions[i]
            if not expr.polygonal:
                self.outside_box.addItem(str(expr))
        self.update_inside_mask(self.poly_box.currentText())
        self.poly_box.currentTextChanged.connect(self.update_inside_mask)
        vlayout = QVBoxLayout()
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Mask'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Inside'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Outside'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.poly_box, 2, 1)
        glayout.addWidget(self.inside_box, 2, 2)
        glayout.addWidget(self.outside_box, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        vlayout.addLayout(glayout)
        vlayout.addStretch()
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(cancel_button)
        vlayout.addLayout(hlayout)
        fifth_page.setLayout(vlayout)

        ok_button.clicked.connect(self.check)
        cancel_button.clicked.connect(self.reject)
        return fifth_page

    def update_inside_mask(self, current_mask):
        mask = self.pool.get_mask(current_mask)
        self.inside_box.clear()
        for child_code in mask.children:
            expr = self.pool.get_expression(child_code)
            self.inside_box.addItem(str(expr))

    def turn_page(self):
        if self.simple_button.isChecked():
            self.stack.setCurrentIndex(1)
        elif self.condition_button.isChecked():
            self.stack.setCurrentIndex(2)
        elif self.max_min_button.isChecked():
            self.stack.setCurrentIndex(3)
        else:
            self.stack.setCurrentIndex(4)

    def polygonal_success_message(self):
        QMessageBox.information(None, 'Polygonal expression created',
                                'You just created an expression containing polygon values.\n'
                                'To use it, click "Add Expression" then choose "Masked expression"\n'
                                '(You will also need at least one non-polygonal expression).',
                                QMessageBox.Ok)

    def polygonal_fail_message(self):
        QMessageBox.critical(None, 'Error', 'One expression can only use only one polygonal mask!',
                             QMessageBox.Ok)

    def check(self):
        current_page = self.stack.currentIndex()
        if current_page == 1:
            literal_expression = self.expression_text.toPlainText()
            success_code = self.pool.add_simple_expression(literal_expression)
            if success_code == -1:
                QMessageBox.critical(None, 'Error', 'Invalid expression.', QMessageBox.Ok)
                return
            elif success_code == -2:
                self.polygonal_fail_message()
                return
            elif success_code == 1:
                self.polygonal_success_message()

        elif current_page == 2:
            str_true, str_false = self.true_box.currentText(), self.false_box.currentText()
            if str_true == str_false:
                QMessageBox.critical(None, 'Error', 'The True/False expressions cannot be identical!', QMessageBox.Ok)
                return
            str_cond = self.condition_box.currentText()
            success_code = self.pool.add_conditional_expression(self.pool.get_condition(str_cond),
                                                                self.pool.get_expression(str_true),
                                                                self.pool.get_expression(str_false))
            if success_code == -2:
                self.polygonal_fail_message()
                return
            elif success_code == 1:
                self.polygonal_success_message()
        elif current_page == 3:
            is_max = self.max_min_box.currentText() == 'MAX'
            str_first, str_second = self.first_box.currentText(), self.second_box.currentText()
            if str_first == str_second:
                QMessageBox.critical(None, 'Error', 'The two expressions cannot be identical!', QMessageBox.Ok)
                return
            success_code = self.pool.add_max_min_expression(self.pool.get_expression(str_first),
                                                            self.pool.get_expression(str_second), is_max)
            if success_code == -2:
                self.polygonal_fail_message()
                return
            elif success_code == 1:
                self.polygonal_success_message()
        else:
            str_inside, str_outside = self.inside_box.currentText(), self.outside_box.currentText()
            self.pool.add_masked_expression(self.pool.get_expression(str_inside),
                                            self.pool.get_expression(str_outside))
        self.accept()


class ConditionDialog(QDialog):
    def __init__(self, expr_pool):
        super().__init__()
        self.expr_pool = expr_pool
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        self.expression_box = QComboBox()
        self.expression_box.setFixedHeight(30)
        self.expression_box.setMinimumWidth(150)
        self.expression_box.setMaximumWidth(250)

        for i in range(1, expr_pool.nb_expressions+1):
            expr = expr_pool.expressions[i]
            if expr.masked:
                continue
            self.expression_box.addItem(str(expr))

        self.comparator_box = QComboBox()
        for comparator in ['>', '<', '>=', '<=']:
            self.comparator_box.addItem(comparator)
        self.comparator_box.setFixedSize(50, 30)

        self.threshold_box = QLineEdit()
        self.threshold_box.setFixedSize(150, 30)

        vlayout = QVBoxLayout()
        glayout = QGridLayout()
        glayout.addWidget(QLabel('Expression'), 1, 1, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Comparator'), 1, 2, Qt.AlignHCenter)
        glayout.addWidget(QLabel('Threshold'), 1, 3, Qt.AlignHCenter)
        glayout.addWidget(self.expression_box, 2, 1)
        glayout.addWidget(self.comparator_box, 2, 2)
        glayout.addWidget(self.threshold_box, 2, 3)
        glayout.setVerticalSpacing(12)
        glayout.setRowStretch(0, 1)
        vlayout.addLayout(glayout)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Add condition')

    def check(self):
        threshold = self.threshold_box.text()
        try:
            threshold = float(threshold)
        except ValueError:
            QMessageBox.critical(None, 'Error', 'The threshold is not a number!', QMessageBox.Ok)
            return
        expr_text = self.expression_box.currentText()
        self.expr_pool.add_condition(self.expr_pool.get_expression(expr_text),
                                     self.comparator_box.currentText(), threshold)
        self.accept()


class AttributeDialog(QDialog):
    def __init__(self, items):
        super().__init__()
        self.attribute_box = QComboBox()
        for item in items:
            self.attribute_box.addItem(item)
        self.attribute_box.setFixedHeight(30)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Attribute'))
        hlayout.addWidget(self.attribute_box)
        vlayout = QVBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.setWindowTitle('Select the attribute corresponding to the polygonal mask value')


class InputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.filename = None
        self.language = None

        self.header = None
        self.time = []

        self._initWidgets()
        self._setLayout()
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.polygon_button.clicked.connect(self.polygon_event)

    def _initWidgets(self):
        self.btnOpen = QPushButton('Open', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a .slf file')
        self.btnOpen.setFixedSize(105, 50)
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.inNameBox.setFixedHeight(30)
        self.summaryTextBox = QPlainTextEdit()
        self.summaryTextBox.setFixedHeight(50)
        self.summaryTextBox.setReadOnly(True)
        self.langBox = QGroupBox('Input language')
        hlayout = QHBoxLayout()
        self.frenchButton = QRadioButton('French')
        hlayout.addWidget(self.frenchButton)
        hlayout.addWidget(QRadioButton('English'))
        self.langBox.setLayout(hlayout)
        self.langBox.setMaximumHeight(80)
        self.frenchButton.setChecked(True)

        self.polygon_box = QGroupBox('Add Polygonal Masks (optional)')
        self.polygon_box.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        self.polygon_button = QPushButton('Open\npolygons', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.polygon_button.setToolTip('<b>Open</b> a .shp file')
        self.polygon_button.setFixedSize(105, 50)
        self.polygon_table = QTableWidget()
        self.polygon_table.setColumnCount(3)
        self.polygon_table.setHorizontalHeaderLabels(['ID', 'Value', 'File'])
        vh = self.polygon_table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(25)
        self.polygon_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.polygon_table.setMaximumHeight(400)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.polygon_button)
        hlayout.addWidget(self.polygon_table)
        self.polygon_box.setLayout(hlayout)
        self.polygon_box.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.addItem(QSpacerItem(50, 1))
        hlayout.addWidget(self.btnOpen)
        hlayout.addItem(QSpacerItem(30, 1))
        hlayout.addWidget(self.langBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        glayout = QGridLayout()
        glayout.addWidget(QLabel('Input file'), 1, 1)
        glayout.addWidget(self.inNameBox, 1, 2)
        glayout.addWidget(QLabel('Summary'), 2, 1)
        glayout.addWidget(self.summaryTextBox, 2, 2)
        glayout.setAlignment(Qt.AlignLeft)
        glayout.setSpacing(10)
        mainLayout.addLayout(glayout)
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addWidget(self.polygon_box)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def _reinitInput(self):
        self.summaryTextBox.clear()
        self.header = None
        self.time = []
        if not self.frenchButton.isChecked():
            self.language = 'en'
        else:
            self.language = 'fr'
        self.polygon_table.setRowCount(0)
        self.polygon_box.setEnabled(False)
        self.parent.reset()

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .slf file', '',
                                                  'Serafin Files (*.slf)', options=options)
        if not filename:
            return
        if not testOpen(filename):
            return

        # reinitialize input file data
        self._reinitInput()
        self.filename = filename
        self.inNameBox.setText(filename)
        with Serafin.Read(self.filename, self.language) as resin:
            resin.read_header()
            if not resin.header.is_2d:
                QMessageBox.critical(self, 'Error', 'The file type (TELEMAC 3D) is currently not supported.',
                                     QMessageBox.Ok)
                return
            self.summaryTextBox.appendPlainText(resin.get_summary())
            resin.get_time()
            self.header = resin.header.copy()
            self.time = resin.time[:]
        self.polygon_box.setEnabled(True)
        self.parent.get_input()

    def polygon_event(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a .shp file', '', 'Polygon file (*.shp)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        if not testOpen(filename):
            return

        polygons = []
        try:
            for polygon in Shapefile.get_polygons(filename):
                polygons.append(polygon)
        except struct.error:
            QMessageBox.critical(self, 'Error', 'Inconsistent bytes.', QMessageBox.Ok)
            return
        if not self.polygons:
            QMessageBox.critical(self, 'Error', 'The file does not contain any polygon.',
                                 QMessageBox.Ok)
            return
        items = ['%d - %s' % (index, name) for (index, name) in Shapefile.get_numeric_attribute_names(filename)]
        if not items:
            QMessageBox.critical(self, 'Error', 'The polygons do not have numeric attributes.',
                                 QMessageBox.Ok)
            return
        dlg = AttributeDialog(items)
        if dlg.exec_() != QDialog.Accepted:
            return
        attribute_index, attribute_name = dlg.attribute_box.currentText().split(' - ')
        attribute_index = int(attribute_index)

        row = self.polygon_table.rowCount()
        self.polygon_table.insertRow(row)
        self.polygon_table.setItem(row, 0, QTableWidgetItem('POLY%d' % (row+1)))
        self.polygon_table.setItem(row, 1, QTableWidgetItem(attribute_name))
        self.polygon_table.setItem(row, 2, QTableWidgetItem(filename))

        self.parent.editor_tab.pool.add_polygonal_mask(polygons, attribute_index)


class EditorTab(QWidget):
    def __init__(self, input_tab):
        super().__init__()
        self.input = input_tab
        self.pool = op.ComplexExpressionPool()

        self.add_expression_button = QPushButton('Add Expression')
        self.add_condition_button = QPushButton('Add Condition')
        for bt in (self.add_expression_button, self.add_condition_button):
            bt.setFixedHeight(40)
            bt.setMinimumWidth(150)
            bt.setMaximumWidth(300)

        self.add_expression_button.clicked.connect(self.add_expression)
        self.add_condition_button.clicked.connect(self.add_condition)
        self.add_condition_button.setEnabled(False)

        self.condition_list = QListWidget()
        self.condition_list.setMaximumWidth(400)
        self.condition_list.setMinimumWidth(250)
        self.expression_list = QListWidget()
        self.expression_list.setMinimumWidth(250)

        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        vlayout.addItem(QSpacerItem(10, 15))
        vlayout.addWidget(self.add_expression_button)
        vlayout.addItem(QSpacerItem(10, 10))
        vlayout.addWidget(self.add_condition_button)
        vlayout.addItem(QSpacerItem(10, 15))
        lb = QLabel('Conditions')
        vlayout.addWidget(lb)
        vlayout.addWidget(self.condition_list)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.setAlignment(self.add_expression_button, Qt.AlignHCenter)
        vlayout.setAlignment(self.add_condition_button, Qt.AlignHCenter)
        hlayout.addLayout(vlayout)
        vlayout = QVBoxLayout()
        lb = QLabel('Expressions')
        vlayout.addWidget(lb)
        vlayout.addWidget(self.expression_list)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addLayout(vlayout)
        hlayout.addStretch()
        self.setLayout(hlayout)

    def reset(self):
        self.add_condition_button.setEnabled(False)
        self.expression_list.clear()
        self.condition_list.clear()

    def get_input(self):
        self.pool.init(self.input.header.var_IDs,
                       list(map(lambda x: x.decode('utf-8').strip(), self.input.header.var_names)),
                       self.input.header.x, self.input.header.y)

    def add_expression(self):
        dlg = ExpressionDialog(self.pool)
        value = dlg.exec_()
        if value == QDialog.Accepted:
            item = QListWidgetItem(str(self.pool.expressions[self.pool.nb_expressions]))
            self.expression_list.addItem(item)
            self.add_condition_button.setEnabled(True)

    def add_condition(self):
        dlg = ConditionDialog(self.pool)
        value = dlg.exec_()
        if value == QDialog.Accepted:
            new_condition = str(self.pool.conditions[self.pool.nb_conditions])
            item = QListWidgetItem(new_condition)
            self.condition_list.addItem(item)


class CalculatorGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input_tab = InputTab(self)
        self.editor_tab = EditorTab(self.input_tab)
        self.setWindowTitle('Variable Editor')

        self.tab = QTabWidget()
        self.tab.addTab(self.input_tab, 'Input')
        self.tab.addTab(self.editor_tab, 'Editor')

        self.tab.setTabEnabled(1, False)
        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        layout = QVBoxLayout()
        layout.addWidget(self.tab)
        self.setLayout(layout)
        self.resize(600, 500)

    def reset(self):
        self.tab.setTabEnabled(1, False)

    def get_input(self):
        self.tab.setTabEnabled(1, True)
        self.editor_tab.get_input()


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
    widget = CalculatorGUI()
    widget.show()
    app.exec_()