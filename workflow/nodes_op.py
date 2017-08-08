from copy import deepcopy
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from gui.util import DoubleSliderBox, FrictionLawMessage, SettlingVelocityMessage, SimpleTimeDateSelection,\
    TimeRangeSlider, VariableTable
import slf.misc as operations
from geom.transformation import load_transformation_map
from slf.variables import get_available_variables, get_necessary_equations, \
                          get_US_equation, new_variables_from_US
from workflow.Node import Node, OneInOneOutNode, TwoInOneOutNode


class SelectVariablesNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nVariables'
        self.out_port.data_type = ('slf', 'slf 3d', 'slf geom')
        self.in_port.data_type = ('slf', 'slf 3d')
        self.in_data = None
        self.data = None
        self.selected_vars = []
        self.selected_vars_names = {}
        self.new_options = tuple()
        self.friction_law = -1
        self.us_equation = None
        self.us_button = None
        self.ws_button = None
        self.first_table = None
        self.second_table = None

        self.YELLOW = QColor(245, 255, 207)
        self.GREEN = QColor(200, 255, 180)

    def get_option_panel(self):
        option_panel = QWidget()
        self.first_table = VariableTable()
        self.second_table = VariableTable()
        for var_id, (var_name, var_unit) in self.in_data.selected_vars_names.items():
            if var_id in self.selected_vars_names:
                row = self.second_table.rowCount()
                self.second_table.insertRow(row)
                id_item = QTableWidgetItem(var_id.strip())
                name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
                unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
                for j, item in enumerate([id_item, name_item, unit_item]):
                    if not self.in_data.header.is_2d and var_id == 'Z':
                        item.setFlags(Qt.NoItemFlags)
                    self.second_table.setItem(row, j, item)
            else:
                row = self.first_table.rowCount()
                self.first_table.insertRow(row)
                id_item = QTableWidgetItem(var_id.strip())
                name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
                unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
                for j, item in enumerate([id_item, name_item, unit_item]):
                    self.first_table.setItem(row, j, item)

        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.first_table)

        computable_vars = get_available_variables(self.in_data.selected_vars, is_2d=self.in_data.header.is_2d)

        for var in computable_vars:
            if var.ID() not in self.selected_vars:
                row = self.first_table.rowCount()
                self.first_table.insertRow(self.first_table.rowCount())
                id_item = QTableWidgetItem(var.ID())
                name_item = QTableWidgetItem(var.name(self.in_data.language))
                unit_item = QTableWidgetItem(var.unit())
                for j, item in enumerate([id_item, name_item, unit_item]):
                    self.first_table.setItem(row, j, item)
                    self.first_table.item(row, j).setBackground(self.YELLOW)  # set new variables colors to yellow
            else:
                row = self.second_table.rowCount()
                self.second_table.insertRow(self.second_table.rowCount())
                id_item = QTableWidgetItem(var.ID())
                name_item = QTableWidgetItem(var.name(self.in_data.language))
                unit_item = QTableWidgetItem(var.unit())
                for j, item in enumerate([id_item, name_item, unit_item]):
                    self.second_table.setItem(row, j, item)
                    self.second_table.item(row, j).setBackground(self.YELLOW)  # set new variables colors to yellow

        if self.in_data.header.is_2d:
            self.us_button = QPushButton('Add US from friction law')
            self.us_button.setToolTip('Compute <b>US</b> based on a friction law')
            self.us_button.setEnabled(False)
            self.us_button.setFixedWidth(200)

            if 'US' not in self.in_data.selected_vars and 'W' in self.in_data.selected_vars and self.us_equation is None:
                available_var_IDs = list(map(lambda x: x.ID(), computable_vars))
                available_var_IDs.extend(self.in_data.selected_vars)
                if 'H' in available_var_IDs and 'M' in available_var_IDs:
                    self.us_button.setEnabled(True)

            if 'US' not in self.in_data.selected_vars and self.us_equation is not None:
                new_vars = new_variables_from_US(self.in_data.selected_vars)
                for i, var in enumerate(new_vars):
                    if var.ID() not in self.selected_vars:
                        row = self.first_table.rowCount()
                        self.first_table.insertRow(row)
                        id_item = QTableWidgetItem(var.ID().strip())
                        name_item = QTableWidgetItem(var.name(self.scene().language))
                        unit_item = QTableWidgetItem(var.unit())
                        for j, item in enumerate([id_item, name_item, unit_item]):
                            self.first_table.setItem(row, j, item)
                            self.first_table.item(row, j).setBackground(self.GREEN)
                    else:
                        row = self.second_table.rowCount()
                        self.second_table.insertRow(row)
                        id_item = QTableWidgetItem(var.ID().strip())
                        name_item = QTableWidgetItem(var.name(self.scene().language))
                        unit_item = QTableWidgetItem(var.unit())
                        for j, item in enumerate([id_item, name_item, unit_item]):
                            self.second_table.setItem(row, j, item)
                            self.second_table.item(row, j).setBackground(self.GREEN)

            self.us_button.clicked.connect(self._add_us)

            vlayout.addItem(QSpacerItem(1, 5))
            hlayout2 = QHBoxLayout()
            hlayout2.addItem(QSpacerItem(30, 1))
            hlayout2.addWidget(self.us_button)
            hlayout2.addItem(QSpacerItem(30, 1))
            vlayout.addLayout(hlayout2)
            vlayout.addItem(QSpacerItem(1, 5))

        vlayout.setAlignment(Qt.AlignLeft)
        hlayout.addLayout(vlayout)
        hlayout.addItem(QSpacerItem(15, 1))
        vlayout = QVBoxLayout()
        lb = QLabel('Output variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.second_table)
        hlayout.addLayout(vlayout)
        option_panel.setLayout(hlayout)

        option_panel.destroyed.connect(self._select)

        return option_panel

    def _select(self):
        selected_vars = []
        selected_vars_names = {}
        for i in range(self.second_table.rowCount()):
            var_id, var_name, var_unit = [self.second_table.item(i, j).text() for j in range(3)]
            selected_vars.append(var_id)
            selected_vars_names[var_id] = (bytes(var_name, 'utf-8').ljust(16),
                                           bytes(var_unit, 'utf-8').ljust(16))
        self.new_options = (selected_vars, selected_vars_names)

    def _add_us(self):
        msg = FrictionLawMessage()
        value = msg.exec_()
        if value != QDialog.Accepted:
            return

        self.friction_law = msg.getChoice()
        self.us_equation = get_US_equation(self.friction_law)
        new_vars = new_variables_from_US([var for var in self.in_data.header.var_IDs
                                          if var in self.in_data.selected_vars])
        for i, var in enumerate(new_vars):
            row = self.first_table.rowCount()
            self.first_table.insertRow(row)
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.scene().language))
            unit_item = QTableWidgetItem(var.unit())
            for j, item in enumerate([id_item, name_item, unit_item]):
                self.first_table.setItem(row, j, item)
                self.first_table.item(row, j).setBackground(self.GREEN)  # set new US color to green

        self.us_button.setEnabled(False)

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        if self.selected_vars:
            known_vars = [var for var in self.in_data.header.var_IDs if var in self.in_data.selected_vars]
            new_vars = known_vars[:]
            new_vars.extend(list(map(lambda x: x.ID(), get_available_variables(new_vars,
                                                                               is_2d=self.in_data.header.is_2d))))
            if self.in_data.header.is_2d and self.us_equation is not None:
                if 'US' not in self.in_data.selected_vars and 'W' in self.in_data.selected_vars:
                    us_vars = new_variables_from_US(known_vars)
                    new_vars.extend([x.ID() for x in us_vars])
            intersection = [var for var in self.selected_vars if var in new_vars]

            if intersection:
                self.selected_vars = intersection
                self.selected_vars_names = {var_id: self.selected_vars_names[var_id]
                                            for var_id in intersection}
                if not self.in_data.header.is_2d and 'Z' not in intersection and 'Z' in self.in_data.header.var_IDs:
                    self.selected_vars = ['Z'] + intersection
                    self.selected_vars_names['Z'] = self.in_data.selected_vars_names['Z']
                if not self.in_data.header.is_2d:
                    self.us_equation = None
                else:
                    if 'US' in self.in_data.selected_vars or 'W' not in self.in_data.selected_vars:
                        self.us_equation = None
                    elif 'H' not in known_vars or 'M' not in known_vars:
                        self.us_equation = None
                self.state = Node.READY
                self.reconfigure_downward()
                self.update()
                return
            else:
                self.selected_vars = self.in_data.selected_vars[:]
                self.selected_vars_names = deepcopy(self.in_data.selected_vars_names)
                self.us_equation = None
        else:
            self.selected_vars = self.in_data.selected_vars[:]
            self.selected_vars_names = deepcopy(self.in_data.selected_vars_names)
            self.us_equation = None

    def add_link(self, link):
        super().add_link(link)
        if not self.in_port.has_mother():
            return
        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()

    def reconfigure(self):
        super().reconfigure()
        if self.selected_vars and self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def configure(self, check=None):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return
        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        self.in_data = self.in_port.mother.parentItem().data
        if self.state != Node.SUCCESS:
            self._reset()

        if super().configure():
            self.selected_vars, self.selected_vars_names = self.new_options
            if not self.selected_vars:
                self.state = Node.NOT_CONFIGURED
            else:
                self.reconfigure_downward()
        self.update()

    def save(self):
        vars = ','.join(self.selected_vars)
        names, units = [], []
        for var in self.selected_vars:
            name, unit = self.selected_vars_names[var]
            names.append(name.decode('utf-8').strip())
            units.append(unit.decode('utf-8').strip())
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), str(self.friction_law),
                         vars, ','.join(names), ','.join(units)])

    def load(self, options):
        friction_law, vars, names, units = options
        self.friction_law = int(friction_law)
        if self.friction_law > -1:
            self.us_equation = get_US_equation(self.friction_law)
        if vars:
            for var, name, unit in zip(vars.split(','), names.split(','), units.split(',')):
                self.selected_vars.append(var)
                self.selected_vars_names[var] = (bytes(name, 'utf-8').ljust(16), bytes(unit, 'utf-8').ljust(16))

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        self.data = input_data.copy()
        self.data.us_equation = self.us_equation
        self.data.equations = get_necessary_equations(self.in_data.header.var_IDs, self.selected_vars,
                                                      is_2d=self.data.header.is_2d, us_equation=self.us_equation)
        self.data.selected_vars = self.selected_vars
        self.data.selected_vars_names = {}
        for var_ID, (var_name, var_unit) in self.selected_vars_names.items():
            self.data.selected_vars_names[var_ID] = (var_name, var_unit)
        self.success()


class AddRouseNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nRouse\nNumbers'
        self.out_port.data_type = ('slf out',)
        self.in_port.data_type = ('slf',)
        self.in_data = None
        self.data = None
        self.table = []
        self.settling_velocities = []

    def _configure(self):
        msg = SettlingVelocityMessage(self.settling_velocities, self.table)
        value = msg.exec_()
        if value != QDialog.Accepted:
            return 0
        self.table = msg.get_table()
        new_rouse = [self.table[i][0] for i in range(len(self.table))]
        new_names = [self.table[i][1] for i in range(len(self.table))]
        old_names = [self.in_data.selected_vars_names[var][0].decode('utf-8').strip()
                     for var in self.in_data.selected_vars]
        for rouse in new_rouse:
            if rouse in self.in_data.selected_vars:
                QMessageBox.critical(None, 'Error', 'Duplicated value found.',
                                     QMessageBox.Ok)
                self.table = []
                self.settling_velocities = []
                return 1
        for name in new_names:
            if name in old_names:
                QMessageBox.critical(None, 'Error', 'Duplicated name found.',
                                     QMessageBox.Ok)
                self.table = []
                self.settling_velocities = []
                return 1
        for i in range(len(self.table)):
            self.settling_velocities.append(float(self.table[i][0][6:]))
        return 2

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        if not self.in_data.header.is_2d or 'US' not in self.in_data.selected_vars:
            self.state = Node.NOT_CONFIGURED
            self.in_data = None
        elif self.settling_velocities:
            old_rouse = [self.table[i][0] for i in range(len(self.table))]
            old_names = [self.table[i][1] for i in range(len(self.table))]
            new_names = [self.in_data.selected_vars_names[var][0].decode('utf-8').strip()
                         for var in self.in_data.selected_vars]
            for rouse in old_rouse:
                if rouse in self.in_data.selected_vars:  # duplicated value
                    self.state = Node.NOT_CONFIGURED
                    self.settling_velocities = []
                    self.table = []
                    self.in_data = None
                    self.reconfigure_downward()
                    self.update()
                    return
            for name in old_names:
                if name in new_names:   # duplicated value
                    self.state = Node.NOT_CONFIGURED
                    self.settling_velocities = []
                    self.table = []
                    self.in_data = None
                    self.reconfigure_downward()
                    self.update()
                    return
            self.state = Node.READY
        self.reconfigure_downward()
        self.update()

    def add_link(self, link):
        super().add_link(link)
        if not self.in_port.has_mother():
            return
        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()

    def reconfigure(self):
        super().reconfigure()
        if self.settling_velocities and self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def configure(self, check=None):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if parent_node.state == Node.SUCCESS:
                self.in_data = parent_node.data
                if not self.in_data.header.is_2d:
                    QMessageBox.critical(None, 'Error', 'The input data is not 2D.', QMessageBox.Ok)
                    return
                if 'US' not in self.in_data.selected_vars:
                    QMessageBox.critical(None, 'Error', 'US not found.', QMessageBox.Ok)
                    return
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            self._reset()
        else:
            self.in_data = parent_node.data
            if not self.in_data.header.is_2d:
                QMessageBox.critical(None, 'Error', 'The input data is not 2D.', QMessageBox.Ok)
                return
            if 'US' not in self.in_data.selected_vars:
                QMessageBox.critical(None, 'Error', 'US not found.', QMessageBox.Ok)
                return
            self._reset()

        value = self._configure()
        if value == 0:
            return
        if value == 2:
            self.state = Node.READY
        else:
            self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def save(self):
        table = []
        for line in self.table:
            for j in range(3):
                table.append(line[j])
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()),
                         ','.join(map(str, self.settling_velocities)), ','.join(table)])

    def load(self, options):
        values, table = options
        table = table.split(',')
        if values:
            self.settling_velocities = list(map(float, values.split(',')))
            for i in range(0, len(table), 3):
                self.table.append([table[i], table[i+1], table[i+2]])

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        self.data = input_data.copy()
        self.data.selected_vars.extend([self.table[i][0] for i in range(len(self.table))])
        for i in range(len(self.table)):
            self.data.selected_vars_names[self.table[i][0]] = (bytes(self.table[i][1], 'utf-8').ljust(16),
                                                               bytes(self.table[i][2], 'utf-8').ljust(16))
        self.data.equations = get_necessary_equations(self.in_data.header.var_IDs, self.data.selected_vars,
                                                      is_2d=True, us_equation=self.data.us_equation)
        self.success()


class SelectTimeNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nTime'
        self.out_port.data_type = ('slf', 'slf 3d')
        self.in_port.data_type = ('slf', 'slf 3d')
        self.in_data = None
        self.data = None
        self.selection = None

        self.new_options = tuple()
        self.start_index, self.end_index = -1, -1
        self.start_date, self.end_date = None, None
        self.sampling_frequency = 1

    def get_option_panel(self):
        slider = TimeRangeSlider()
        slider.setFixedHeight(30)
        slider.setMinimumWidth(600)

        self.selection = DoubleSliderBox(self)
        self.selection.startValue.setReadOnly(True)
        self.selection.endValue.setReadOnly(True)

        self.selection.clearText()
        slider.reinit(self.in_data.start_time, self.in_data.time_second, self.selection)

        if len(self.in_data.time) == 1:
            slider.setEnabled(False)
            self.selection.startIndex.setEnabled(False)
            self.selection.endIndex.setEnabled(False)
            self.selection.startValue.setEnabled(False)
            self.selection.endValue.setEnabled(False)

        self.selection.startIndex.editingFinished.connect(slider.enterIndexEvent)
        self.selection.endIndex.editingFinished.connect(slider.enterIndexEvent)

        self.selection.timeSamplig.editingFinished.connect(self._check)
        self.selection.timeSamplig.setText(str(self.sampling_frequency))

        if self.start_index > -1:
            self.selection.startIndex.setText(str(self.start_index+1))
            self.selection.endIndex.setText(str(self.end_index+1))
            slider.enterIndexEvent()

        option_panel = QWidget()
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(10, 10))
        layout.addWidget(slider)
        layout.addWidget(self.selection)
        option_panel.setLayout(layout)
        option_panel.destroyed.connect(self._select)
        return option_panel

    def _check(self):
        try:
            sampling_frequency = int(self.selection.timeSamplig.text())
            if sampling_frequency < 1:
                self.selection.timeSamplig.setText(str(self.sampling_frequency))
        except ValueError:
            self.selection.timeSamplig.setText(str(self.sampling_frequency))

    def _select(self):
        start_index = int(self.selection.startIndex.text())-1
        end_index = int(self.selection.endIndex.text())-1
        sampling_frequency = int(self.selection.timeSamplig.text())
        self.new_options = (start_index, end_index, sampling_frequency)

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        if len(self.in_data.selected_time_indices) != len(self.in_data.time):
            self.state = Node.NOT_CONFIGURED
        elif self.start_date is not None:
            new_time = list(map(lambda x: x + self.in_data.start_time, self.in_data.time_second))
            if self.start_date in new_time:
                self.start_index = new_time.index(self.start_date)
                self.state = Node.READY
            else:
                self.start_index = -1
                self.start_date = None
                self.end_index = -1
                self.end_date = None
                self.state = Node.NOT_CONFIGURED
                self.reconfigure_downward()
                return
            if self.end_date in new_time:
                self.end_index = new_time.index(self.end_date)
                self.state = Node.READY
            else:
                self.start_index = -1
                self.start_date = None
                self.end_index = -1
                self.end_date = None
                self.state = Node.NOT_CONFIGURED
                self.reconfigure_downward()
                return
        self.reconfigure_downward()
        self.update()

    def add_link(self, link):
        super().add_link(link)
        if not self.in_port.has_mother():
            return
        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()

    def reconfigure(self):
        super().reconfigure()
        if self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def configure(self, check=None):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        self.in_data = parent_node.data
        if len(self.in_data.selected_time_indices) != len(self.in_data.time):
            QMessageBox.critical(None, 'Error', 'Cannot re-select time.',
                                 QMessageBox.Ok)
            return
        if self.state != Node.SUCCESS:
            self._reset()
        if super().configure():
            self.start_index, self.end_index, self.sampling_frequency = self.new_options
            self.start_date, self.end_date = self.in_data.start_time + self.in_data.time_second[self.start_index], \
                                             self.in_data.start_time + self.in_data.time_second[self.end_index]
            self.reconfigure_downward()

    def save(self):
        if self.start_date is None:
            str_start_date = ''
            str_end_date = ''
        else:
            str_start_date = self.start_date.strftime('%Y/%m/%d %H:%M:%S')
            str_end_date = self.end_date.strftime('%Y/%m/%d %H:%M:%S')

        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()),
                         str_start_date, str_end_date, str(self.sampling_frequency)])

    def load(self, options):
        start_date, end_date = options[0:2]
        if start_date:
            self.start_date = datetime.datetime.strptime(start_date, '%Y/%m/%d %H:%M:%S')
            self.end_date = datetime.datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
        self.sampling_frequency = int(options[2])

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        self.data = input_data.copy()
        self.data.selected_time_indices = list(range(self.start_index, self.end_index+1, self.sampling_frequency))
        self.success('You selected %d frames.' % len(self.data.selected_time_indices))


class SelectSingleFrameNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nSingle\nFrame'
        self.out_port.data_type = ('slf', 'slf 3d', 'slf geom')
        self.in_port.data_type = ('slf', 'slf 3d')
        self.in_data = None
        self.data = None

        self.selection = -1
        self.date = None
        self.slider = None
        self.new_option = -1

    def get_option_panel(self):
        self.slider = SimpleTimeDateSelection()
        self.slider.initTime(self.in_data.time, list(map(lambda x: x + self.in_data.start_time,
                                                         self.in_data.time_second)))
        if self.selection > -1:
            self.slider.index.setText(str(self.selection+1))
            self.slider.slider.enterIndexEvent()
            self.slider.updateSelection()

        option_panel = QWidget()
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(10, 10))
        layout.addWidget(self.slider)
        option_panel.setLayout(layout)
        option_panel.destroyed.connect(self._select)
        return option_panel

    def _select(self):
        self.new_option = int(self.slider.index.text()) - 1

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        if len(self.in_data.selected_time_indices) != len(self.in_data.time):
            self.state = Node.NOT_CONFIGURED
        elif self.date is not None:
            new_time = list(map(lambda x: x + self.in_data.start_time, self.in_data.time_second))
            if self.date in new_time:
                self.selection = new_time.index(self.date)
                self.state = Node.READY
            else:
                self.selection = -1
                self.date = None
                self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def add_link(self, link):
        super().add_link(link)
        if not self.in_port.has_mother():
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()

    def reconfigure(self):
        super().reconfigure()
        if self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def configure(self, check=None):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        self.in_data = parent_node.data
        if len(self.in_data.selected_time_indices) != len(self.in_data.time):
            QMessageBox.critical(None, 'Error', 'Cannot re-select time.',
                                 QMessageBox.Ok)
            return
        if self.state != Node.SUCCESS:
            self._reset()
        if super().configure():
            self.selection = self.new_option
            self.date = self.in_data.start_time + self.in_data.time_second[self.selection]
            self.reconfigure_downward()

    def save(self):
        if self.date is None:
            str_date = ''
        else:
            str_date = self.date.strftime('%Y/%m/%d %H:%M:%S')
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), str_date])

    def load(self, options):
        if options[0]:
            self.date = datetime.datetime.strptime(options[0], '%Y/%m/%d %H:%M:%S')

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        self.data = input_data.copy()
        self.data.selected_time_indices = [self.selection]
        self.success()


class SynchMaxNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'SynchMax'
        self.out_port.data_type = ('slf out',)
        self.in_port.data_type = ('slf',)
        self.in_data = None
        self.data = None

        self.var = ''
        self.var_box = None
        self.new_option = ''

    def get_option_panel(self):
        self.var_box = QComboBox()
        self.var_box.setFixedHeight(30)
        available_vars = [var for var in self.in_data.selected_vars if var in self.in_data.header.var_IDs]
        for var in available_vars:
            self.var_box.addItem(var)
        if self.var:
            self.var_box.setCurrentIndex(available_vars.index(self.var))

        option_panel = QWidget()
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(10, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Select the reference variable'))
        hlayout.addWidget(self.var_box)
        layout.addLayout(hlayout)
        option_panel.setLayout(layout)
        option_panel.destroyed.connect(self._select)
        return option_panel

    def _select(self):
        self.new_option = self.var_box.currentText()

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        if not self.in_data.header.is_2d or len(self.in_data.selected_time_indices) == 1:
            self.state = Node.NOT_CONFIGURED
        elif self.in_data.operator is not None:
            self.state = Node.NOT_CONFIGURED
        elif self.var:
            available_vars = [var for var in self.in_data.selected_vars if var in self.in_data.header.var_IDs]
            if self.var in available_vars:
                self.state = Node.READY
            else:
                self.var = ''
                self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def add_link(self, link):
        super().add_link(link)
        if not self.in_port.has_mother():
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()

    def reconfigure(self):
        super().reconfigure()
        if self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.reconfigure_downward()
        self.update()

    def configure(self, check=None):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        self.in_data = parent_node.data
        if not self.in_data.header.is_2d:
            QMessageBox.critical(None, 'Error', 'The input file is not 2D.', QMessageBox.Ok)
            return
        if len(self.in_data.selected_time_indices) <= 1:
            QMessageBox.critical(None, 'Error', 'The input file must have more than one frame.', QMessageBox.Ok)
            return
        if self.state != Node.SUCCESS:
            self._reset()
        if super().configure():
            self.var = self.new_option
            self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.var])

    def load(self, options):
        self.var = options[0]

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        self.data = input_data.copy()
        self.data.operator = operations.SYNCH_MAX
        self.data.metadata = {'var': self.var}
        self.success()


class UnaryOperatorNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.state = Node.READY
        self.data = None
        self.message = 'Nothing to configure.'
        self.out_port.data_type = ('slf out',)
        self.in_port.data_type = ('slf',)

    def reconfigure(self):
        super().reconfigure()
        self.state = Node.READY
        self.reconfigure_downward()

    def configure(self, check=None):
        if super().configure():
            self.reconfigure_downward()

    def run(self):
        pass


class BinaryOperatorNode(TwoInOneOutNode):
    def __init__(self, index, operator=None):
        super().__init__(index)
        self.operator = operator
        self.state = Node.READY
        self.data = None
        self.message = 'Nothing to configure.'
        self.out_port.data_type = ('slf out',)
        self.first_in_port.data_type = ('slf', 'slf reference')
        self.second_in_port.data_type = ('slf',)

    def reconfigure(self):
        super().reconfigure()
        self.state = Node.READY
        self.reconfigure_downward()

    def configure(self, check=None):
        if super().configure():
            self.reconfigure_downward()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.first_in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if input_data.filename == self.second_in_port.mother.parentItem().data.filename:
            self.fail('the two inputs cannot be from the same file.')
            return

        self.data = input_data.copy()
        self.data.operator = self.operator
        self.data.metadata = {'operand': self.second_in_port.mother.parentItem().data.copy()}
        self.success()


class ConvertToSinglePrecisionNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Convert to\nSingle\nPrecision'
        self.out_port.data_type = ('slf', 'slf 3d')
        self.in_port.data_type = ('slf', 'slf 3d')

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_double_precision():
            self.fail('the input file is not of double-precision format.')
            return
        if input_data.to_single:
            self.fail('the input data is already converted to single-precision format.')
            return

        self.data = input_data.copy()
        self.data.to_single = True
        self.success()


class SelectFirstFrameNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nFirst\nFrame'
        self.out_port.data_type = ('slf', 'slf 3d', 'slf geom')
        self.in_port.data_type = ('slf', 'slf 3d')

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if len(input_data.selected_time_indices) != len(input_data.time):
            self.fail('cannot re-select time.')
            return

        self.data = input_data.copy()
        self.data.selected_time_indices = [0]
        self.success()


class SelectLastFrameNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nLast\nFrame'
        self.out_port.data_type = ('slf', 'slf 3d', 'slf geom')
        self.in_port.data_type = ('slf', 'slf 3d')

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if len(input_data.selected_time_indices) != len(input_data.time):
            self.fail('cannot re-select time.')
            return

        self.data = input_data.copy()
        self.data.selected_time_indices = [len(input_data.time)-1]
        self.success()


class ComputeMaxNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max'

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if len(input_data.selected_time_indices) == 1:
            self.fail('the input data must have more than one frame')
            return

        self.data = input_data.copy()
        self.data.operator = operations.MAX
        self.success()


class ComputeMinNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min'

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if len(input_data.selected_time_indices) == 1:
            self.fail('the input data must have more than one frame')
            return

        self.data = input_data.copy()
        self.data.operator = operations.MIN
        self.success()


class ComputeMeanNode(UnaryOperatorNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Mean'

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if not input_data.header.is_2d:
            self.fail('the input file is not 2D')
            return
        if len(input_data.selected_time_indices) == 1:
            self.fail('the input data must have more than one frame')
            return

        self.data = input_data.copy()
        self.data.operator = operations.MEAN
        self.success()


class MinusNode(BinaryOperatorNode):
    def __init__(self, index):
        super().__init__(index, operations.DIFF)
        self.category = 'Operators'
        self.label = 'A Minus B'


class ReverseMinusNode(BinaryOperatorNode):
    def __init__(self, index):
        super().__init__(index, operations.REV_DIFF)
        self.category = 'Operators'
        self.label = 'B Minus A'


class ProjectMeshNode(BinaryOperatorNode):
    def __init__(self, index):
        super().__init__(index, operations.PROJECT)
        self.category = 'Operators'
        self.label = 'Project B\non A'


class MaxBetweenNode(BinaryOperatorNode):
    def __init__(self, index):
        super().__init__(index, operations.MAX_BETWEEN)
        self.category = 'Operators'
        self.label = 'Max(A,B)'


class MinBetweenNode(BinaryOperatorNode):
    def __init__(self, index):
        super().__init__(index, operations.MIN_BETWEEN)
        self.category = 'Operators'
        self.label = 'Min(A,B)'


class AddTransformationNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nTrans-\nformation'
        self.name_ = 'Add Transformation'
        self.in_port.data_type = ('slf', 'slf 3d')
        self.out_port.data_type = ('slf geom', 'slf', 'slf 3d')
        self.filename = ''
        self.data = None

        self.map = None
        self.from_index = -1
        self.to_index = -1
        self.transformation = None

        self.name_box = None
        self.from_box = None
        self.to_box = None
        self.new_transformation = None
        self.new_options = tuple()

    def name(self):
        return self.name_

    def get_option_panel(self):
        self.new_transformation = self.transformation
        conf_box = QGroupBox('Apply coordinate transformation')
        conf_box.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        open_button = QPushButton('Load\nTransformation')
        open_button.setToolTip('<b>Open</b> a transformation config file')
        open_button.setFixedSize(105, 50)
        self.name_box = QLineEdit()
        self.name_box.setReadOnly(True)
        self.name_box.setFixedHeight(30)
        self.from_box = QComboBox()
        self.from_box.setFixedWidth(150)
        self.to_box = QComboBox()
        self.to_box.setFixedWidth(150)

        if self.transformation is not None:
            for label in self.new_transformation.labels:
                self.from_box.addItem(label)
                self.to_box.addItem(label)
            self.from_box.setCurrentIndex(self.from_index)
            self.to_box.setCurrentIndex(self.to_index)
            self.name_box.setText(self.filename)

        option_panel = QWidget()
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(open_button)
        hlayout.addWidget(self.name_box)
        vlayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Transform from'))
        hlayout.addWidget(self.from_box)
        hlayout.addWidget(QLabel('to'))
        hlayout.addWidget(self.to_box)
        hlayout.setAlignment(Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.setSpacing(15)
        conf_box.setLayout(vlayout)

        layout = QVBoxLayout()
        layout.addWidget(conf_box)
        option_panel.setLayout(layout)
        open_button.clicked.connect(self._open)
        option_panel.destroyed.connect(self._select)
        return option_panel

    def _open(self):
        filename, _ = QFileDialog.getOpenFileName(None, 'Open a transformation configuration file', '',
                                                  'All file (*)', QDir.currentPath(),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        success, self.new_transformation = load_transformation_map(filename)
        if not success:
            QMessageBox.critical(None, 'Error', 'The configuration is not valid.', QMessageBox.Ok)
            return
        self.name_box.setText(filename)
        for label in self.new_transformation.labels:
            self.from_box.addItem(label)
            self.to_box.addItem(label)

    def _check(self):
        if self.new_transformation is None:
            return 0
        elif self.from_box.currentIndex() == self.to_box.currentIndex():
            QMessageBox.critical(None, 'Error', 'The two systems cannot be identical!', QMessageBox.Ok)
            return 1
        return 2

    def _select(self):
        from_index, to_index = self.from_box.currentIndex(), self.to_box.currentIndex()
        self.new_options = (self.new_transformation, from_index, to_index, self.name_box.text())

    def configure(self, check=None):
        if super().configure(self._check):
            self.transformation, self.from_index, self.to_index, self.filename = self.new_options
            self.reconfigure_downward()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), self.filename, str(self.from_index),
                         str(self.to_index)])

    def load(self, options):
        filename, from_index, to_index = options
        if not filename:
            return
        try:
            with open(filename) as f:
                pass
        except FileNotFoundError:
            self.state = Node.NOT_CONFIGURED
            return
        success, transformation = load_transformation_map(filename)
        if not success:
            self.state = Node.NOT_CONFIGURED
            return
        from_index, to_index = int(from_index), int(to_index)
        if from_index not in transformation.nodes or to_index not in transformation.nodes:
            self.state = Node.NOT_CONFIGURED
            return
        self.filename = filename
        self.transformation = transformation
        self.from_index = from_index
        self.to_index = to_index
        self.state = Node.READY
        self.update()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        input_data = self.in_port.mother.parentItem().data
        if 'transformation' in input_data.metadata:
            self.fail('cannot re-apply transformation.')
            return

        trans = self.transformation.get_transformation(self.from_index, self.to_index)
        self.data = input_data.copy()
        self.data.transform(trans)
        self.data.metadata['transformation'] = trans
        self.success()

