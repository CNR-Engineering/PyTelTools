from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from copy import deepcopy
import datetime

from workflow.Node import Node, OneInOneOutNode
from gui.util import TableWidgetDragRows, TimeRangeSlider, DoubleSliderBox, FrictionLawMessage, FallVelocityMessage
from slf.variables import get_available_variables, get_necessary_equations, add_US, get_US_equation


class SelectVariablesNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index, 'Select\nVariables')
        self.out_port.data_type = 'slf'
        self.in_port.data_type = 'slf'
        self.in_data = None
        self.data = None
        self.selected_vars = []
        self.selected_vars_names = {}
        self.us_equation = None
        self.us_button = None
        self.ws_button = None
        self.first_table = None
        self.second_table = None

        self.YELLOW = QColor(245, 255, 207)
        self.GREEN = QColor(200, 255, 180)

    def get_option_panel(self):
        option_panel = QWidget()
        self.first_table = TableWidgetDragRows()
        self.second_table = TableWidgetDragRows()
        for tw in [self.first_table, self.second_table]:
            tw.setColumnCount(3)
            tw.setHorizontalHeaderLabels(['ID', 'Name', 'Unit'])
            vh = tw.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Fixed)
            vh.setDefaultSectionSize(20)
            hh = tw.horizontalHeader()
            hh.setDefaultSectionSize(100)
            tw.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tw.setMaximumHeight(800)
        for var_id, (var_name, var_unit) in self.in_data.selected_vars_names.items():
            if var_id in self.selected_vars_names:
                row = self.second_table.rowCount()
                self.second_table.insertRow(row)
                id_item = QTableWidgetItem(var_id.strip())
                name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
                unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
                self.second_table.setItem(row, 0, id_item)
                self.second_table.setItem(row, 1, name_item)
                self.second_table.setItem(row, 2, unit_item)
            else:
                row = self.first_table.rowCount()
                self.first_table.insertRow(row)
                id_item = QTableWidgetItem(var_id.strip())
                name_item = QTableWidgetItem(var_name.decode('utf-8').strip())
                unit_item = QTableWidgetItem(var_unit.decode('utf-8').strip())
                self.first_table.setItem(row, 0, id_item)
                self.first_table.setItem(row, 1, name_item)
                self.first_table.setItem(row, 2, unit_item)

        computable_vars = get_available_variables(self.in_data.selected_vars)
        for var in computable_vars:
            if var.ID() not in self.selected_vars:
                row = self.first_table.rowCount()
                self.first_table.insertRow(self.first_table.rowCount())
                id_item = QTableWidgetItem(var.ID())
                name_item = QTableWidgetItem(var.name(self.in_data.language))
                unit_item = QTableWidgetItem(var.unit())
                self.first_table.setItem(row, 0, id_item)
                self.first_table.setItem(row, 1, name_item)
                self.first_table.setItem(row, 2, unit_item)
                self.first_table.item(row, 0).setBackground(self.YELLOW)  # set new variables colors to yellow
                self.first_table.item(row, 1).setBackground(self.YELLOW)
                self.first_table.item(row, 2).setBackground(self.YELLOW)
            else:
                row = self.second_table.rowCount()
                self.second_table.insertRow(self.second_table.rowCount())
                id_item = QTableWidgetItem(var.ID())
                name_item = QTableWidgetItem(var.name(self.in_data.language))
                unit_item = QTableWidgetItem(var.unit())
                self.second_table.setItem(row, 0, id_item)
                self.second_table.setItem(row, 1, name_item)
                self.second_table.setItem(row, 2, unit_item)
                self.second_table.item(row, 0).setBackground(self.YELLOW)
                self.second_table.item(row, 1).setBackground(self.YELLOW)
                self.second_table.item(row, 2).setBackground(self.YELLOW)

        if 'US' not in self.in_data.selected_vars and self.us_equation is not None:
            new_vars = []
            add_US(new_vars, self.in_data.selected_vars)
            for i, var in enumerate(new_vars):
                if var.ID() not in self.selected_vars:
                    row = self.first_table.rowCount()
                    self.first_table.insertRow(row)
                    id_item = QTableWidgetItem(var.ID().strip())
                    name_item = QTableWidgetItem(var.name(self.scene().language))
                    unit_item = QTableWidgetItem(var.unit())
                    self.first_table.setItem(row, 0, id_item)
                    self.first_table.setItem(row, 1, name_item)
                    self.first_table.setItem(row, 2, unit_item)
                    for j in range(3):
                        self.first_table.item(row, j).setBackground(self.GREEN)
                else:
                    row = self.second_table.rowCount()
                    self.second_table.insertRow(row)
                    id_item = QTableWidgetItem(var.ID().strip())
                    name_item = QTableWidgetItem(var.name(self.scene().language))
                    unit_item = QTableWidgetItem(var.unit())
                    self.second_table.setItem(row, 0, id_item)
                    self.second_table.setItem(row, 1, name_item)
                    self.second_table.setItem(row, 2, unit_item)
                    for j in range(3):
                        self.second_table.item(row, j).setBackground(self.GREEN)

        self.us_button = QPushButton('Add US from friction law')
        self.us_button.setToolTip('Compute <b>US</b> based on a friction law')
        self.us_button.setEnabled(False)
        self.us_button.setFixedWidth(200)

        if 'US' not in self.in_data.selected_vars and 'W' in self.in_data.selected_vars and self.us_equation is None:
            available_var_IDs = list(map(lambda x: x.ID(), computable_vars))
            available_var_IDs.extend(self.in_data.selected_vars)
            if 'H' in available_var_IDs and 'M' in available_var_IDs:
                self.us_button.setEnabled(True)

        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        vlayout.setAlignment(Qt.AlignHCenter)
        lb = QLabel('Available variables')
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addWidget(self.first_table)
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

        self.us_button.clicked.connect(self._add_us)
        option_panel.destroyed.connect(self._select)

        return option_panel

    def _select(self):
        self.selected_vars = []
        self.selected_vars_names = {}
        for i in range(self.second_table.rowCount()):
            var_id, var_name, var_unit = [self.second_table.item(i, j).text() for j in range(3)]
            self.selected_vars.append(var_id)
            self.selected_vars_names[var_id] = (bytes(var_name, 'utf-8').ljust(16),
                                                bytes(var_unit, 'utf-8').ljust(16))

    def _add_us(self):
        msg = FrictionLawMessage()
        value = msg.exec_()
        if value != QDialog.Accepted:
            return

        friction_law = msg.getChoice()
        self.us_equation = get_US_equation(friction_law)
        new_vars = []
        add_US(new_vars, self.in_data.selected_vars)

        for i, var in enumerate(new_vars):
            row = self.first_table.rowCount()
            self.first_table.insertRow(row)
            id_item = QTableWidgetItem(var.ID().strip())
            name_item = QTableWidgetItem(var.name(self.scene().language))
            unit_item = QTableWidgetItem(var.unit())
            self.first_table.setItem(row, 0, id_item)
            self.first_table.setItem(row, 1, name_item)
            self.first_table.setItem(row, 2, unit_item)
            self.first_table.item(row, 0).setBackground(self.GREEN)  # set new US color to green
            self.first_table.item(row, 1).setBackground(self.GREEN)
            self.first_table.item(row, 2).setBackground(self.GREEN)

        self.us_button.setEnabled(False)

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        new_vars = self.in_data.selected_vars
        intersection = [var for var in self.selected_vars if var in new_vars]
        if intersection:
            self.selected_vars = intersection
            self.selected_vars_names = {var_id: self.in_data.selected_vars_names[var_id]
                                        for var_id in intersection}
        else:
            self.selected_vars = self.in_data.selected_vars[:]
            self.selected_vars_names = deepcopy(self.in_data.selected_vars_names)

    def reconfigure(self):
        super().reconfigure()
        if self.selected_vars and self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    new_vars = parent_node.data.selected_vars
                    intersection = [var for var in self.selected_vars if var in new_vars]
                    if intersection:
                        self.in_data = parent_node.data
                        self.selected_vars = intersection
                        self.selected_vars_names = {var_id: self.in_data.selected_vars_names[var_id]
                                                    for var_id in intersection}
                        self.data = None
                        self.state = Node.READY
                        return

        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.update()

    def configure(self):
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
                self._reset()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        else:
            self.in_data = parent_node.data

        if super().configure():
            if not self.selected_vars:
                self.state = Node.NOT_CONFIGURED
            else:
                self.state = Node.READY
            self.update()
            QApplication.processEvents()

    def run(self):
        self.data = self.in_data.copy()
        self.data.us_equation = self.us_equation
        self.data.equations = get_necessary_equations(self.in_data.header.var_IDs, self.selected_vars,
                                                      self.us_equation)
        self.data.output_header.nb_var = len(self.selected_vars)
        self.data.output_header.var_IDs, self.data.output_header.var_names, \
                                         self.data.output_header.var_units = [], [], []
        self.data.selected_vars = self.selected_vars
        self.data.selected_vars_names = {}
        for var_ID, (var_name, var_unit) in self.selected_vars_names.items():
            self.data.output_header.var_IDs.append(var_ID)
            self.data.output_header.var_names.append(var_name)
            self.data.output_header.var_units.append(var_unit)
            self.data.selected_vars_names[var_ID] = (var_name, var_unit)

        self.state = Node.SUCCESS
        self.update()
        self.message = 'Successful.'


class SelectTimeNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index, 'Select\nTime')
        self.out_port.data_type = 'slf'
        self.in_port.data_type = 'slf'
        self.in_data = None
        self.data = None
        self.selection = None

        self.selected_indices = []
        self.start_index, self.end_index = -1, -1
        self.sampling_frequency = 1

    def get_option_panel(self):
        slider = TimeRangeSlider()
        slider.setFixedHeight(30)
        slider.setMinimumWidth(600)

        self.selection = DoubleSliderBox(self)
        self.selection.startValue.setReadOnly(True)
        self.selection.endValue.setReadOnly(True)

        if self.in_data.header.date is not None:
            year, month, day, hour, minute, second = self.in_data.header.date
            start_time = datetime.datetime(year, month, day, hour, minute, second)
        else:
            start_time = datetime.datetime(1900, 1, 1, 0, 0, 0)

        time_frames = list(map(lambda x: datetime.timedelta(seconds=x),
                               [self.in_data.time[index] for index in self.selected_indices]))
        self.selection.clearText()
        slider.reinit(start_time, time_frames, self.selection)

        if len(time_frames) == 1:
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
            if sampling_frequency < 1 or sampling_frequency > len(self.in_data.selected_time_indices):
                self.selection.timeSamplig.setText(str(self.sampling_frequency))
        except ValueError:
            self.selection.timeSamplig.setText(str(self.sampling_frequency))

    def _select(self):
        self.start_index = int(self.selection.startIndex.text())-1
        self.end_index = int(self.selection.endIndex.text())-1
        self.sampling_frequency = int(self.selection.timeSamplig.text())

    def _reset(self):
        self.in_data = self.in_port.mother.parentItem().data
        self.selected_indices = self.in_data.selected_time_indices[:]
        self.start_index, self.end_index = self.selected_indices[0], self.selected_indices[-1]

    def reconfigure(self):
        super().reconfigure()
        if self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self.in_data = parent_node.data
                    self.selected_indices = self.in_data.selected_time_indices[:]
                    self.start_index, self.end_index = self.selected_indices[0], self.selected_indices[-1]
                    self.data = None
                    return

        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.update()

    def configure(self):
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
                self._reset()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        else:
            self.in_data = parent_node.data
        super().configure()

    def run(self):
        self.data = self.in_data.copy()
        self.data.selected_time_indices = list(range(self.start_index, self.end_index+1, self.sampling_frequency))
        self.state = Node.SUCCESS
        self.update()
        self.message = 'Successful.'


class AddRouseNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index, 'Add Rouse')
        self.out_port.data_type = 'slf'
        self.in_port.data_type = 'slf'
        self.in_data = None
        self.data = None
        self.table = []
        self.fall_velocities = []

    def _configure(self):
        msg = FallVelocityMessage(self.fall_velocities, self.table)
        value = msg.exec_()
        if value != QDialog.Accepted:
            return False
        self.table = msg.get_table()
        for i in range(len(self.table)):
            self.fall_velocities.append(float(self.table[i][0][6:]))
        return True

    def reconfigure(self):
        super().reconfigure()
        if self.fall_velocities and self.in_port.has_mother():
            parent_node = self.in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    if 'US' in parent_node.selected_vars:
                        self.data = None
                        return

        self.in_data = None
        self.state = Node.NOT_CONFIGURED
        self.update()

    def configure(self):
        if not self.in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if not self.fall_velocities:
                if parent_node.ready_to_run():
                    parent_node.run()
                else:
                    QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                         QMessageBox.Ok)
                    return
                if parent_node.state == Node.SUCCESS:
                    self.in_data = parent_node.data
                    if 'US' not in self.in_data.selected_vars:
                        QMessageBox.critical(None, 'Error', 'US not found.',
                                             QMessageBox.Ok)
                        return
                else:
                    QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                         QMessageBox.Ok)
                    return
            else:
                self.in_data = parent_node.data
                if 'US' not in self.in_data.selected_vars:
                    QMessageBox.critical(None, 'Error', 'US not found.',
                                         QMessageBox.Ok)
                    return
                old_rouse = [self.table[i][0] for i in range(len(self.table))]
                for rouse in old_rouse:
                    if rouse in self.in_data.selected_vars:
                        QMessageBox.critical(self, 'Error', 'Duplicated values found.',
                                             QMessageBox.Ok)
                        return

        if self._configure():
            self.state = Node.READY

    def run(self):
        self.data = self.in_data.copy()
        self.data.selected_vars.extend([self.table[i][0] for i in range(len(self.table))])
        for i in range(len(self.table)):
            self.data.selected_vars_names[self.table[i][0]] = (bytes(self.table[i][1], 'utf-8').ljust(16),
                                                               bytes(self.table[i][2], 'utf-8').ljust(16))
        self.data.equations = get_necessary_equations(self.in_data.header.var_IDs, self.data.selected_vars,
                                                      self.data.us_equation)
        self.data.output_header.nb_var = len(self.in_data.selected_vars)
        self.data.output_header.var_IDs, self.data.output_header.var_names, \
                                         self.data.output_header.var_units = [], [], []
        for var_ID, (var_name, var_unit) in self.data.selected_vars_names.items():
            self.data.output_header.var_IDs.append(var_ID)
            self.data.output_header.var_names.append(var_name)
            self.data.output_header.var_units.append(var_unit)
        self.state = Node.SUCCESS
        self.update()
        self.message = 'Successful.'

