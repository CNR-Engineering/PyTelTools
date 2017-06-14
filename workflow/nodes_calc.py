from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import shapely

from workflow.Node import Node, TwoInOneOutNode
from slf import Serafin
from slf.volume import TruncatedTriangularPrisms, VolumeCalculator


class ComputeVolumeNode(TwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nVolume'
        self.out_port.data_type = 'csv'
        self.first_in_port.data_type = 'slf'
        self.second_in_port.data_type = 'polygon'
        self.in_data = None

        self.first_var = None
        self.second_var = None
        self.sup_volume = False

        self.first_var_box = None
        self.second_var_box = None
        self.sup_volume_box = None

    def get_option_panel(self):
        self.first_var_box = QComboBox()
        self.first_var_box.setFixedSize(400, 30)
        self.second_var_box = QComboBox()
        self.second_var_box.setFixedSize(400, 30)
        self.sup_volume_box = QCheckBox('Compute positive and negative volumes (slow)', None)

        self.second_var_box.addItem('0')
        self.second_var_box.addItem('Initial values of the first variable')

        available_vars = [var for var in self.in_data.selected_vars if var in self.in_data.header.var_IDs]
        for var_ID, var_name in zip(self.in_data.header.var_IDs, self.in_data.header.var_names):
            if var_ID not in available_vars:
                continue
            self.first_var_box.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())
            self.second_var_box.addItem(var_ID + ' (%s)' % var_name.decode('utf-8').strip())
        if self.first_var is not None:
            self.first_var_box.setCurrentIndex(available_vars.index(self.first_var))
        if self.second_var is not None:
            if self.second_var == VolumeCalculator.INIT_VALUE:
                self.second_var_box.setCurrentIndex(1)
            else:
                self.second_var_box.setCurrentIndex(2 + available_vars.index(self.second_var))
        self.sup_volume_box.setChecked(self.sup_volume)

        option_panel = QWidget()
        glayout = QGridLayout()
        glayout.addWidget(QLabel('     Select the principal variable'), 1, 1)
        glayout.addWidget(self.first_var_box, 1, 2)
        glayout.addWidget(QLabel('     Select a variable to subtract (optional)'), 2, 1)
        glayout.addWidget(self.second_var_box, 2, 2)
        glayout.addWidget(QLabel('     Positive / negative volumes'), 3, 1)
        glayout.addWidget(self.sup_volume_box, 3, 2)
        option_panel.setLayout(glayout)
        option_panel.destroyed.connect(self._select)
        return option_panel

    def _select(self):
        self.first_var = self.first_var_box.currentText().split('(')[0][:-1]
        self.second_var = self.second_var_box.currentText()
        if self.second_var == '0':
            self.second_var = None
        elif '(' in self.second_var:
            self.second_var = self.second_var.split('(')[0][:-1]
        else:
            self.second_var = VolumeCalculator.INIT_VALUE
        self.sup_volume = self.sup_volume_box.isChecked()

    def _reset(self):
        self.in_data = self.first_in_port.mother.parentItem().data
        available_vars = [var for var in self.in_data.selected_vars if var in self.in_data.header.var_IDs]
        if self.first_var not in available_vars:
            self.first_var = None
        if self.second_var is not None and self.second_var != VolumeCalculator.INIT_VALUE:
            if self.second_var not in available_vars:
                self.second_var = None

    def add_link(self, link):
        super().add_link(link)
        if not self.first_in_port.has_mother():
            return
        parent_node = self.first_in_port.mother.parentItem()
        if parent_node.state != Node.SUCCESS:
            if parent_node.ready_to_run():
                parent_node.run()
            if parent_node.state != Node.SUCCESS:
                return
        self._reset()
        self.state = Node.READY
        self.update()

    def reconfigure(self):
        super().reconfigure()
        if self.first_in_port.has_mother():
            parent_node = self.first_in_port.mother.parentItem()
            if parent_node.ready_to_run():
                parent_node.run()
                if parent_node.state == Node.SUCCESS:
                    self._reset()
                    return
        self.in_data = None
        self.first_var = None
        self.second_var = None
        self.state = Node.NOT_CONFIGURED
        self.update()

    def configure(self):
        if not self.first_in_port.has_mother():
            QMessageBox.critical(None, 'Error', 'Connect and run the input before configure this node!',
                                 QMessageBox.Ok)
            return

        parent_node = self.first_in_port.mother.parentItem()
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
        self._reset()
        super().configure()

    def save(self):
        first = '' if self.first_var is None else self.first_var
        second = '' if self.second_var is None else self.second_var
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()),
                         first, second, str(int(self.sup_volume))])

    def load(self, options):
        first, second, sup = options
        if first:
            self.first_var = first
        if second:
            self.second_var = second
        self.sup_volume = bool(int(sup))

    def run(self):
        success = super().run_upward()
        if not success:
            self.state = Node.FAIL
            self.update()
            self.message = 'Failed: input failed.'
            return

        self.progress_bar.setVisible(True)
        self.in_data = self.first_in_port.mother.parentItem().data
        polygons = self.second_in_port.mother.parentItem().data
        polygon_names = ['Polygon %d' % (i+1) for i in range(len(polygons))]
        if self.sup_volume:
            volume_type = VolumeCalculator.POSITIVE
        else:
            volume_type = VolumeCalculator.NET

        mesh = TruncatedTriangularPrisms(self.in_data.header, False)

        if self.in_data.has_index:
            mesh.index = self.in_data.index
            mesh.triangles = self.in_data.triangles
        else:
            five_percent = 0.05 * mesh.nb_triangles
            nb_processed = 0
            current_percent = 0

            for i, j, k in mesh.ikle:
                t = shapely.geometry.Polygon([mesh.points[i], mesh.points[j], mesh.points[k]])
                mesh.triangles[i, j, k] = t
                mesh.index.insert(i, t.bounds, obj=(i, j, k))

                nb_processed += 1
                if nb_processed > five_percent:
                    nb_processed = 0
                    current_percent += 5
                    self.progress_bar.setValue(current_percent)
                    QApplication.processEvents()

            self.progress_bar.setValue(0)
            QApplication.processEvents()
            self.in_data.has_index = True
            self.in_data.index = mesh.index
            self.in_data.triangles = mesh.triangles

        with Serafin.Read(self.in_data.filename, self.in_data.language) as resin:
            resin.header = self.in_data.header
            resin.time = self.in_data.time

            calculator = VolumeCalculator(VolumeCalculator.NET_STRICT, self.first_var, self.second_var, resin,
                                          polygon_names, polygons, 1)
            calculator.time_indices = self.in_data.selected_time_indices
            calculator.mesh = mesh
            calculator.construct_weights()

            self.data = [['time']]
            if volume_type == VolumeCalculator.POSITIVE:
                for name in polygon_names:
                    self.data[0].append(name)
                    self.data[0].append(name + ' POSITIVE')
                    self.data[0].append(name + ' NEGATIVE')
            else:
                for name in polygon_names:
                    self.data[0].append(name)

            init_values = None
            if calculator.second_var_ID == VolumeCalculator.INIT_VALUE:
                init_values = calculator.input_stream.read_var_in_frame(0, calculator.var_ID)

            for i, time_index in enumerate(calculator.time_indices):
                i_result = [str(calculator.input_stream.time[time_index])]
                values = calculator.read_values_in_frame(time_index, init_values)

                for j in range(len(calculator.polygons)):
                    weight = calculator.weights[j]
                    volume = calculator.volume_in_frame_in_polygon(weight, values, calculator.polygons[j])
                    if calculator.volume_type == VolumeCalculator.POSITIVE:
                        for v in volume:
                            i_result.append('%.6f' % v)
                    else:
                        i_result.append('%.6f' % volume)
                self.data.append(i_result)

                self.progress_bar.setValue(100 * (i+1) / len(calculator.time_indices))
                QApplication.processEvents()

        self.state = Node.SUCCESS
        self.update()
        self.message = 'Successful.'
        self.progress_bar.setVisible(False)
