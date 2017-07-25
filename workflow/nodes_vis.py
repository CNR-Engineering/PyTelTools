from itertools import islice, cycle
import datetime
import os
import pandas
import numpy as np
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from slf import Serafin
from slf.mesh2D import Mesh2D
from slf.volume import VolumeCalculator
from slf.interpolation import MeshInterpolator
from workflow.datatypes import SerafinData
from workflow.Node import Node, SingleInputNode, DoubleInputNode
from workflow.util import MultiLoadCSVDialog, OutputOptionPanel, VerticalProfilePlotViewer, \
    MultiLoadSerafinDialog, MultiSaveDialog
from gui.util import MapCanvas, PolygonMapCanvas, LineMapCanvas, MapViewer, TemporalPlotViewer, \
    PointAttributeTable, PointLabelEditor, ProjectLinesPlotViewer


class ShowMeshNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Show\nMesh'
        self.in_port.data_type = ('slf', 'slf 3d')
        self.state = Node.READY

        canvas = MapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_map = False

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

        if not self.has_map:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.initFigure(mesh)
            self.has_map = True
            self.map.canvas.draw()
        self.map.showMaximized()
        self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            mesh = Mesh2D(self.in_port.mother.parentItem().data.header)
            self.map.canvas.initFigure(mesh)

            self.has_map = True
            self.map.canvas.draw()
        self.map.showMaximized()
        self.success()


class LocateOpenLinesNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nOpen\nLines'
        self.first_in_port.data_type = ('slf', 'slf 3d')
        self.second_in_port.data_type = ('polyline 2d',)
        self.state = Node.READY

        canvas = LineMapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_map = False

    def configure(self, check=None):
        if not self.first_in_port.has_mother() or not self.second_in_port.has_mother():
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
        line_node = self.second_in_port.mother.parentItem()
        if line_node.state != Node.SUCCESS:
            if line_node.ready_to_run():
                line_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if line_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return

        if not self.has_map:
            self._prepare()
        self.map.showMaximized()
        self.success()

    def _prepare(self):
        mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
        line_data = self.second_in_port.mother.parentItem().data
        self.map.canvas.reinitFigure(mesh, line_data.lines,
                                     ['Line %d' % (i+1) for i in range(len(line_data))],
                                     list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                          len(line_data))))

        self.has_map = True
        self.map.canvas.draw()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            self._prepare()
        self.map.showMaximized()
        self.success()


class LocatePolygonsNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nPolygons'
        self.first_in_port.data_type = ('slf', 'slf 3d')
        self.second_in_port.data_type = ('polygon 2d',)
        self.state = Node.READY

        canvas = PolygonMapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_map = False

    def configure(self, check=None):
        if not self.first_in_port.has_mother() or not self.second_in_port.has_mother():
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
        line_node = self.second_in_port.mother.parentItem()
        if line_node.state != Node.SUCCESS:
            if line_node.ready_to_run():
                line_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if line_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return

        if not self.has_map:
            self._prepare()
        self.map.showMaximized()
        self.success()

    def _prepare(self):
        mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
        line_data = self.second_in_port.mother.parentItem().data
        self.map.canvas.reinitFigure(mesh, line_data.lines,
                                     ['Polygon %d' % (i+1) for i in range(len(line_data))])
        self.map.canvas.draw()
        self.has_map = True

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            self._prepare()
        self.map.showMaximized()
        self.success()


class LocatePointsNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nPoints'
        self.first_in_port.data_type = ('slf', 'slf 3d')
        self.second_in_port.data_type = ('point 2d',)
        self.state = Node.READY

        canvas = MapCanvas()
        self.map = MapViewer(canvas)
        self.has_map = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_map = False

    def configure(self, check=None):
        if not self.first_in_port.has_mother() or not self.second_in_port.has_mother():
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
        point_node = self.second_in_port.mother.parentItem()
        if point_node.state != Node.SUCCESS:
            if point_node.ready_to_run():
                point_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if point_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return

        if not self.has_map:
            self._prepare()
            self.map.showMaximized()
        self.success()

    def _prepare(self):
        mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
        self.map.canvas.initFigure(mesh)
        points = self.second_in_port.mother.parentItem().data.points
        self.map.canvas.axes.scatter(*zip(*points))
        labels = ['%d' % (i+1) for i in range(len(points))]
        for label, (x, y) in zip(labels, points):
            self.map.canvas.axes.annotate(label, xy=(x, y), xytext=(-20, 20), fontsize=8,
                                          textcoords='offset points', ha='right', va='bottom',
                                          bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                                          arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

        self.map.canvas.draw()
        self.has_map = True

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            self._prepare()
        self.map.showMaximized()
        self.success()


class ProjectLinesNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Project\nLines\nPlot'
        self.first_in_port.data_type = ('slf',)
        self.second_in_port.data_type = ('polyline 2d',)
        self.state = Node.READY
        self.has_plot = False

        self.plot_viewer = ProjectLinesPlotViewer()
        self.multi_save_act = QAction('Multi-Save', None, triggered=self.multi_save,
                                      icon=self.plot_viewer.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.plot_viewer.plotViewer.toolBar.addSeparator()
        self.plot_viewer.plotViewer.toolBar.addAction(self.multi_save_act)
        self.current_vars = {}

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def configure(self, check=None):
        if not self.first_in_port.has_mother() or not self.second_in_port.has_mother():
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
        if not parent_node.data.header.is_2d:
            QMessageBox.critical(None, 'Error', 'The input file is not 2D!',
                                 QMessageBox.Ok)
            return
        point_node = self.second_in_port.mother.parentItem()
        if point_node.state != Node.SUCCESS:
            if point_node.ready_to_run():
                point_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if point_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        if not self.has_plot:
            success = self._prepare()
            if not success:
                QMessageBox.critical(None, 'Error', 'No line intersects the mesh continuously.',
                                     QMessageBox.Ok)
                return
        self.plot_viewer.showMaximized()
        self.success()

    def _prepare(self):
        input_data = self.first_in_port.mother.parentItem().data
        mesh = MeshInterpolator(input_data.header, False)
        if input_data.has_index:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.construct_mesh(mesh)
            input_data.has_index = True
            input_data.index = mesh.index
            input_data.triangles = mesh.triangles

        lines = self.second_in_port.mother.parentItem().data.lines
        nb_nonempty, indices_nonempty, \
                     line_interpolators, line_interpolators_internal = mesh.get_line_interpolators(lines)
        if nb_nonempty == 0:
            return False
        self.plot_viewer.getInput(input_data.filename, input_data.header, input_data.time,
                                  lines, line_interpolators,
                                  line_interpolators_internal)
        self.has_plot = True
        return True

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.first_in_port.mother.parentItem().data.header.is_2d:
            QMessageBox.critical(None, 'Error', 'The input file is not 2D!',
                                 QMessageBox.Ok)
            return
        if not self.has_plot:
            success = self._prepare()
            if not success:
                QMessageBox.critical(None, 'Error', 'No line intersects the mesh continuously.',
                                     QMessageBox.Ok)
                self.fail('No line intersects the mesh continuously.')
                return
        self.plot_viewer.showMaximized()
        self.success()

    def open(self, job_id, input_name):
        try:
            with open(input_name) as f:
                pass
        except PermissionError:
            return None
        input_data = SerafinData(job_id, input_name, self.first_in_port.mother.parentItem().data.language)
        if input_data.read():
            return input_data
        return None

    def interpolate(self, input_data):
        mesh = MeshInterpolator(input_data.header, True)
        lines = self.plot_viewer.lines
        nb_nonempty, indices_nonempty, \
        line_interpolators, line_interpolators_internal = mesh.get_line_interpolators(lines)

        if nb_nonempty == 0:
            return False, [], []
        return True, line_interpolators, line_interpolators_internal

    def compute(self, reference, max_distance, time_index, input_data,
                all_line_interpolators, all_line_interpolators_internal):
        line_interpolators = {}
        line_interpolators_internal = {}
        for line_id in self.plot_viewer.current_vars:
            line_interpolator, _ = all_line_interpolators[line_id]
            line_interpolators[line_id] = line_interpolator

            line_interpolator_internal, _ = all_line_interpolators_internal[line_id]
            line_interpolators_internal[line_id] = line_interpolator_internal

        distances, values, distances_internal, values_internal = {}, {}, {}, {}

        with Serafin.Read(input_data.filename, input_data.language) as input_stream:
            input_stream.header = input_data.header
            input_stream.time = input_data.time
            for line_id in self.plot_viewer.current_vars:
                distances[line_id] = []
                distances_internal[line_id] = []
                values[line_id] = {}
                values_internal[line_id] = {}

                for var in self.plot_viewer.current_vars[line_id]:
                    values[line_id][var] = []
                    values_internal[line_id][var] = []

                for x, y, (i, j, k), interpolator in line_interpolators[line_id]:
                    d = reference.project(x, y)
                    if d <= 0 or d >= max_distance:
                        continue
                    distances[line_id].append(d)

                    for var in self.plot_viewer.current_vars[line_id]:
                        all_values = input_stream.read_var_in_frame(time_index, var)
                        values[line_id][var].append(interpolator.dot(all_values[[i, j, k]]))
                distances[line_id] = np.array(distances[line_id])

                for x, y, (i, j, k), interpolator in line_interpolators_internal[line_id]:
                    d = reference.project(x, y)
                    if d <= 0 or d >= max_distance:
                        continue
                    distances_internal[line_id].append(d)

                    for var in self.plot_viewer.current_vars[line_id]:
                        all_values = input_stream.read_var_in_frame(time_index, var)
                        values_internal[line_id][var].append(interpolator.dot(all_values[[i, j, k]]))
                distances_internal[line_id] = np.array(distances_internal[line_id])

        return distances, values, distances_internal, values_internal

    def plot(self, values, distances, values_internal, distances_internal, png_name):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)
        if self.plot_viewer.control.addInternal.isChecked():
            if self.plot_viewer.control.intersection.isChecked():
                for line_id, vars in self.plot_viewer.current_vars.items():
                    for var in vars:
                        axes.plot(distances[line_id], values[line_id][var],
                                  linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))

                        axes.plot(distances_internal[line_id], values_internal[line_id][var], 'o',
                                  color=self.plot_viewer.line_colors[line_id])
            else:
                for line_id, vars in self.plot_viewer.current_vars.items():
                    for var in vars:
                        axes.plot(distances_internal[line_id], values_internal[line_id][var],
                                  marker='o', linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))

        else:
            if self.plot_viewer.control.intersection.isChecked():
                for line_id, vars in self.plot_viewer.current_vars.items():
                    for var in vars:
                        axes.plot(distances[line_id], values[line_id][var],
                                  linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))
            else:
                for line_id, vars in self.plot_viewer.current_vars.items():
                    for var in vars:
                        axes.plot(distances_internal[line_id], values_internal[line_id][var],
                                  linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))

        axes.legend()
        axes.grid(linestyle='dotted')
        axes.set_xlabel(self.plot_viewer.plotViewer.current_xlabel)
        axes.set_ylabel(self.plot_viewer.plotViewer.current_ylabel)
        axes.set_title(self.plot_viewer.plotViewer.current_title)
        fig.canvas.draw()
        fig.savefig(png_name, dpi=100)

    def multi_save(self):
        current_vars = self.plot_viewer.getSelection()
        if not current_vars:
            return
        dlg = MultiLoadSerafinDialog([])
        if dlg.exec_() == QDialog.Accepted:
            input_options = (dlg.dir_paths, dlg.slf_name, dlg.job_ids)
        else:
            return
        dlg = MultiSaveDialog(['_project_plot', True, '', False, True])
        dlg.panel.no_button.setEnabled(False)
        if dlg.exec_() == QDialog.Accepted:
            output_options = dlg.panel.get_options()
        else:
            return

        ref_id = int(self.plot_viewer.control.lineBox.currentText().split()[1]) - 1
        reference = self.plot_viewer.lines[ref_id]
        max_distance = reference.length()
        time_index = int(self.plot_viewer.control.timeSelection.index.text()) - 1
        compute_options = (reference, max_distance, time_index)

        dlg = MultiSaveProjectLinesDialog(self, input_options, output_options, compute_options)
        dlg.exec_()


class MultiSaveProjectLinesDialog(QDialog):
    def __init__(self, parent, input_options, output_options, compute_options):
        super().__init__()

        self.parent = parent
        self.input_options = input_options
        self.output_options = output_options
        self.compute_options = compute_options

        self.table = QTableWidget()
        self.table.setRowCount(len(input_options[0]))
        self.table.setColumnCount(4)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['Job', 'Load Serafin', 'Interpolation', 'Export PNG'])

        yellow = QColor(245, 255, 207, 255)

        for i, path in enumerate(input_options[0]):
            name = os.path.basename(path)
            self.table.setItem(i, 0, QTableWidgetItem(name))
            for j in range(1, 4):
                self.table.setItem(i, j, QTableWidgetItem(''))
                self.table.item(i, j).setBackground(yellow)

        self.btnClose = QPushButton('Close', None)
        self.btnClose.setEnabled(False)
        self.btnClose.setFixedSize(120, 30)
        self.btnClose.clicked.connect(self.accept)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('Wait until all yellow cells turn green'))
        vlayout.addWidget(self.table)
        vlayout.addStretch()
        vlayout.addWidget(self.btnClose, Qt.AlignRight)
        self.setLayout(vlayout)
        self.resize(500, 300)
        self.setWindowTitle('Multi-Save Project Lines')
        self.show()
        QApplication.processEvents()
        self.success = self._run()
        self.btnClose.setEnabled(True)

    def _run(self):
        red = QColor(255, 160, 160, 255)
        green = QColor(180, 250, 165, 255)

        dir_paths, slf_name, job_ids = self.input_options
        suffix, in_source_folder, dir_path, double_name, overwrite = self.output_options
        reference, max_distance, time_index = self.compute_options
        png_names = []
        for path, job_id in zip(dir_paths, job_ids):
            if double_name:
                output_name = slf_name[:-4] + '_' + job_id + suffix + '.png'
            else:
                output_name = slf_name[:-4] + suffix + '.png'
            if in_source_folder:
                filename = os.path.join(path, output_name)
            else:
                filename = os.path.join(dir_path, output_name)
            png_names.append(filename)
        nb_success = 0
        for i, (dir_path, job_id, png_name) in enumerate(zip(dir_paths, job_ids, png_names)):
            input_name = os.path.join(dir_path, slf_name)

            input_data = self.parent.open(job_id, input_name)
            if input_data is None:
                self.table.item(i, 1).setBackground(red)
                QApplication.processEvents()
                continue
            self.table.item(i, 1).setBackground(green)
            QApplication.processEvents()

            success, all_lines, all_lines_internal = self.parent.interpolate(input_data)
            if not success:
                self.table.item(i, 2).setBackground(red)
                QApplication.processEvents()
                continue
            self.table.item(i, 2).setBackground(green)
            QApplication.processEvents()

            distances, values, distances_internal, values_internal = self.parent.compute(reference, max_distance,
                                                                                         time_index, input_data,
                                                                                         all_lines, all_lines_internal)
            self.parent.plot(values, distances, values_internal, distances_internal, png_name)
            self.table.item(i, 3).setBackground(green)
            QApplication.processEvents()
            nb_success += 1

        if nb_success == len(dir_paths):
            QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                    QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Failed', 'Failed to produce all figures.',
                                    QMessageBox.Ok)

        self.btnClose.setEnabled(True)


class VerticalTemporalProfileNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Vertical\nTemporal\nProfile 3D'
        self.first_in_port.data_type = ('slf 3d',)
        self.second_in_port.data_type = ('point 2d',)
        self.plot_viewer = VerticalProfilePlotViewer()
        self.state = Node.READY
        self.has_plot = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def configure(self, check=None):
        if not self.first_in_port.has_mother() or not self.second_in_port.has_mother():
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
        point_node = self.second_in_port.mother.parentItem()
        if point_node.state != Node.SUCCESS:
            if point_node.ready_to_run():
                point_node.run()
            else:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
            if point_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return
        # if self.has_plot:
        #     self.plot_viewer.show()
        # else:
        #     self.plot_viewer.get_data(self.first_in_port.mother.parentItem().data,
        #                               self.second_in_port.mother.parentItem().data.points)
        #     self.has_plot = True
        #     self.plot_viewer.show()
        #     self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        # if not self.has_plot:
        #     self.plot_viewer.get_data(self.first_in_port.mother.parentItem().data,
        #                               self.second_in_port.mother.parentItem().points)
        #     self.has_plot = True
        # self.success()


class VolumePlotNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Volume\nPlot'
        self.in_port.data_type = ('volume csv',)
        self.state = Node.READY
        self.plot_viewer = VolumePlotViewer()
        self.has_plot = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_plot = False
        self.plot_viewer.reset()
        self.plot_viewer.current_columns = ('Polygon 1',)

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

        if self.has_plot:
            self.plot_viewer.show()
        else:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
            self.plot_viewer.show()
            self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        parent_node = self.in_port.mother.parentItem()
        if not self.has_plot:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
        self.success()


class FluxPlotNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Flux\nPlot'
        self.in_port.data_type = ('flux csv',)
        self.state = Node.READY
        self.plot_viewer = FluxPlotViewer()
        self.has_plot = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_plot = False
        self.plot_viewer.reset()
        self.plot_viewer.current_columns = ('Section 1',)

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

        if self.has_plot:
            self.plot_viewer.show()
        else:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
            self.plot_viewer.show()
            self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        parent_node = self.in_port.mother.parentItem()
        if not self.has_plot:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
        self.success()


class PointPlotNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Point\nPlot'
        self.in_port.data_type = ('point csv',)
        self.state = Node.READY
        self.plot_viewer = PointPlotViewer()
        self.has_plot = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_plot = False
        self.plot_viewer.reset()
        self.plot_viewer.current_columns = ('Point 1',)

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

        if self.has_plot:
            self.plot_viewer.show()
        else:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
            self.plot_viewer.show()
            self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        parent_node = self.in_port.mother.parentItem()
        if not self.has_plot:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
        self.success()


class PointAttributeTableNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Point\nAttribute\nTable'
        self.in_port.data_type = ('point 2d',)
        self.state = Node.READY
        self.table = PointAttributeTable()
        self.has_table = False

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def reconfigure(self):
        super().reconfigure()
        self.has_table = False

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

        if self.has_table:
            self.table.show()
        else:
            self.table.getData(parent_node.data.points, [], parent_node.data.fields_name,
                               parent_node.data.attributes_decoded)
            self.has_table = True
            self.table.show()
            self.success()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        parent_node = self.in_port.mother.parentItem()
        if not self.has_table:
            self.table.get_data(parent_node.data.points, [], parent_node.data.fields_name,
                               parent_node.data.attributes_decoded)
            self.has_table = True
        self.success()


class VolumePlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('polygon')
        self.csv_separator = ''
        self.var_ID = None
        self.second_var_ID = None
        self.language = 'fr'
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))

        self.current_columns = ('Polygon 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.poly_menu = QMenu('&Polygons', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)
        self.menuBar.addMenu(self.poly_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

    def _defaultYLabel(self):
        word = {'fr': 'de', 'en': 'of'}[self.language]
        if self.second_var_ID == VolumeCalculator.INIT_VALUE:
            return 'Volume %s (%s - %s$_0$)' % (word, self.var_ID, self.var_ID)
        elif self.second_var_ID is None:
            return 'Volume %s %s' % (word, self.var_ID)
        return 'Volume %s (%s - %s)' % (word, self.var_ID, self.second_var_ID)

    def replot(self):
        self.canvas.axes.clear()
        for column in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[column], '-', color=self.column_colors[column],
                                  linewidth=2, label=self.column_labels[column])
        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        self.data['time'] = np.array(self.data['time'])

        self.start_time = csv_data.metadata['start time']
        self.current_columns = ('Polygon 1',)

        self.var_ID = csv_data.metadata['var']
        self.second_var_ID = csv_data.metadata['second var']

        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = list(self.data)[1:]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSaveVolumeDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                    self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                    self.start_time)
        dlg.exec_()


class FluxPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('section')
        self.csv_separator = ''
        self.language = 'fr'
        self.flux_title = ''
        self.var_IDs = []
        self.cumulative = False
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.cumulative_flux_act = QAction('Show\ncumulative flux', self, checkable=True,
                                           icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.cumulative_flux_act.toggled.connect(self.changeFluxType)

        self.current_columns = ('Section 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.cumulative_flux_act)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.poly_menu = QMenu('&Sections', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)
        self.menuBar.addMenu(self.poly_menu)
        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

    def changeFluxType(self):
        self.cumulative = not self.cumulative
        self.current_ylabel = 'Cumulative ' + self.flux_title
        self.replot()

    def replot(self):
        self.canvas.axes.clear()
        for column in self.current_columns:
            if not self.cumulative:
                self.canvas.axes.plot(self.time[self.timeFormat], self.data[column], '-',
                                      color=self.column_colors[column],
                                      linewidth=2, label=self.column_labels[column])
            else:
                self.canvas.axes.plot(self.time[self.timeFormat], np.cumsum(self.data[column]), '-',
                                      color=self.column_colors[column],
                                      linewidth=2, label=self.column_labels[column])

        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        for item in header:
            self.data[item] = np.array(self.data[item])

        self.flux_title = csv_data.metadata['flux title']
        self.start_time = csv_data.metadata['start time']
        self.current_columns = ('Section 1',)

        self.var_IDs = csv_data.metadata['var IDs']
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.columns = list(self.data)[1:]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self.flux_title
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSaveFluxDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                  self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                  self.start_time, self.cumulative)
        dlg.exec_()


class PointPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.csv_separator = ''
        self.language = 'fr'
        self.var_IDs = []
        self.current_var = ''
        self.points = None
        self.indices = []
        self.multi_save_act = QAction('Multi-Save', self, triggered=self.multi_save,
                                      icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.select_variable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.current_columns = ('Point 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.multi_save_act)

        self.point_menu = QMenu('&Data', self)
        self.point_menu.addAction(self.select_variable)
        self.point_menu.addSeparator()
        self.point_menu.addAction(self.selectColumnsAct)
        self.point_menu.addAction(self.editColumnNamesAct)
        self.point_menu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.point_menu)

        self.multi_menu = QMenu('&Multi', self)
        self.multi_menu.addAction(self.multi_save_act)
        self.menuBar.addMenu(self.multi_menu)

    def _to_column(self, point):
        point_index = int(point.split()[1]) - 1
        x, y = self.points.points[point_index]
        return '%s (%.4f, %.4f)' % (self.current_var, x, y)

    def editColumns(self):
        msg = PointLabelEditor(self.column_labels, self.column_name,
                               self.points.points, [True if i in self.indices else False
                                                    for i in range(len(self.points.points))],
                               self.points.fields_name,
                               self.points.attributes_decoded)
        value = msg.exec_()
        if value == QDialog.Rejected:
            return
        msg.getLabels(self.column_labels)
        self.replot()

    def _defaultYLabel(self):
        word = {'fr': 'de', 'en': 'of'}[self.language]
        return 'Values %s %s' % (word, self.current_var)

    def selectVariableEvent(self):
        msg = QDialog()
        combo = QComboBox()
        for var in self.var_IDs:
            combo.addItem(var)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, msg)
        buttons.accepted.connect(msg.accept)
        buttons.rejected.connect(msg.reject)
        vlayout = QVBoxLayout()
        vlayout.addWidget(combo)
        vlayout.addWidget(buttons)
        msg.setLayout(vlayout)
        msg.setWindowTitle('Select a variable to plot')
        msg.resize(300, 150)
        msg.exec_()
        self.current_var = combo.currentText()
        self.current_ylabel = self._defaultYLabel(self.input.language)
        self.replot()

    def replot(self):
        self.canvas.axes.clear()
        for point in self.current_columns:
            self.canvas.axes.plot(self.time[self.timeFormat], self.data[self._to_column(point)], '-',
                                  color=self.column_colors[point],
                                  linewidth=2, label=self.column_labels[point])
        self.canvas.axes.legend()
        self.canvas.axes.grid(linestyle='dotted')
        self.canvas.axes.set_xlabel(self.current_xlabel)
        self.canvas.axes.set_ylabel(self.current_ylabel)
        self.canvas.axes.set_title(self.current_title)
        if self.timeFormat in [1, 2]:
            self.canvas.axes.set_xticklabels(self.str_datetime if self.timeFormat == 1 else self.str_datetime_bis)
            for label in self.canvas.axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        self.canvas.draw()

    def get_data(self, csv_data):
        self.csv_separator = csv_data.separator
        self.data = {}
        header = csv_data.table[0]
        for item in header:
            self.data[item] = []
        for row in csv_data.table[1:]:
            for j, item in enumerate(row):
                self.data[header[j]].append(float(item))
        for item in header:
            self.data[item] = np.array(self.data[item])

        self.var_IDs = csv_data.metadata['var IDs']
        self.current_var = self.var_IDs[0]
        self.points = csv_data.metadata['points']

        self.start_time = csv_data.metadata['start time']
        self.datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), self.data['time']))

        self.str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), self.datetime))
        self.str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), self.datetime))

        self.indices = csv_data.metadata['point indices']
        self.columns = ['Point %d' % (i+1) for i in self.indices]
        self.current_columns = self.columns[0:1]
        self.column_labels = {x: x for x in self.columns}
        self.column_colors = {x: None for x in self.columns}
        for i in range(min(len(self.columns), len(self.defaultColors))):
            self.column_colors[self.columns[i]] = self.defaultColors[i]

        # initialize the plot
        self.time = [self.data['time'], self.data['time'], self.data['time'],
                     self.data['time'] / 60, self.data['time'] / 3600, self.data['time'] / 86400]
        self.language = csv_data.metadata['language']
        self.current_xlabel = self._defaultXLabel()
        self.current_ylabel = self._defaultYLabel()
        self.current_title = ''
        self.replot()

    def multi_save(self):
        dlg = MultiSavePointDialog(self.csv_separator, self.current_columns, self.column_labels, self.column_colors,
                                   self.current_xlabel, self.current_ylabel, self.current_title, self.timeFormat,
                                   self.start_time, [self._to_column(p) for p in self.current_columns])
        dlg.exec_()


class MultiSaveTemporalPlotDialog(QDialog):
    def __init__(self, name, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time):
        super().__init__()
        self.name = name
        self.separator = separator
        self.filenames = []
        self.dir_paths = []
        self.csv_name = ''
        self.job_ids = []
        self.data = []
        self.out_names = []

        self.current_columns = current_columns
        self.column_labels = column_labels
        self.column_colors = column_colors
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.title = title
        self.time_format = time_format
        self.start_time = start_time

        self.stack = QStackedLayout()
        self.stack.addWidget(self.build_first_page())
        self.stack.addWidget(self.build_second_page())
        self.stack.addWidget(self.build_third_page())
        self.setLayout(self.stack)
        self.setWindowTitle('Save figures for multiple CSV results of %s' % self.name)

    def build_first_page(self):
        first_page = QWidget()
        source_box = QGroupBox('Where are the CSV results of %s' % self.name)
        self.same_button = QRadioButton('In the same folder')
        self.different_button = QRadioButton('In different folder under the same name')
        self.different_button.setChecked(True)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.same_button)
        vlayout.addWidget(self.different_button)
        source_box.setLayout(vlayout)
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
        vlayout.addWidget(source_box)
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        first_page.setLayout(vlayout)

        next_button.clicked.connect(self.turn_page)
        cancel_button.clicked.connect(self.reject)
        return first_page

    def build_second_page(self):
        second_page = QWidget()
        back_button = QPushButton('Back')
        ok_button = QPushButton('OK')
        for bt in (back_button, ok_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(back_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel('All figures will have the same names as the CSV files'))
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        second_page.setLayout(vlayout)

        back_button.clicked.connect(self.back)
        ok_button.clicked.connect(self.run)
        return second_page

    def build_third_page(self):
        third_page = QWidget()
        self.output_panel = OutputOptionPanel(['_plot', True, '', '', True])
        self.output_panel.no_button.setEnabled(False)
        back_button = QPushButton('Back')
        ok_button = QPushButton('OK')
        for bt in (back_button, ok_button):
            bt.setMaximumWidth(200)
            bt.setFixedHeight(30)
        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_button)
        hlayout.addWidget(back_button)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.output_panel)
        vlayout.addStretch()
        vlayout.addLayout(hlayout, Qt.AlignRight)
        third_page.setLayout(vlayout)

        back_button.clicked.connect(self.back)
        ok_button.clicked.connect(self.run)
        return third_page

    def back(self):
        self.stack.setCurrentIndex(0)

    def turn_page(self):
        if self.same_button.isChecked():
            filenames, _ = QFileDialog.getOpenFileNames(None, 'Open CSV files', '', 'CSV Files (*.csv)',
                                                        options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
            if not filenames:
                self.reject()
            self.filenames = filenames
            for csv_name in self.filenames:
                success, data = self.read(csv_name)
                if not success:
                    QMessageBox.critical(None, 'Error', 'The file %s is not valid.' % os.path.split(csv_name)[1],
                                         QMessageBox.Ok)
                    return
                self.data.append(data)
                self.out_names.append(csv_name[:-4] + '.png')
            self.stack.setCurrentIndex(1)
        else:
            dlg = MultiLoadCSVDialog([])
            if dlg.exec_() == QDialog.Accepted:
                self.dir_paths, self.csv_name, self.job_ids = dlg.dir_paths, dlg.slf_name, dlg.job_ids
            else:
                self.reject()
            for path in self.dir_paths:
                success, data = self.read(os.path.join(path, self.csv_name))
                if not success:
                    QMessageBox.critical(None, 'Error', 'The file in %s is not valid.' % os.path.basename(path),
                                         QMessageBox.Ok)
                    return
                self.data.append(data)
            self.stack.setCurrentIndex(2)

    def run(self):
        if not self.out_names:
            suffix, in_source_folder, dir_path, double_name, _ = self.output_panel.get_options()

            for path, job_id in zip(self.dir_paths, self.job_ids):
                if double_name:
                    output_name = self.csv_name[:-4] + '_' + job_id + suffix + '.png'
                else:
                    output_name = self.csv_name[:-4] + suffix + '.png'
                if in_source_folder:
                    filename = os.path.join(path, output_name)
                else:
                    filename = os.path.join(dir_path, output_name)
                self.out_names.append(filename)

        self.plot()
        QMessageBox.information(None, 'Success', 'Figures saved successfully',
                                QMessageBox.Ok)
        self.accept()

    def read(self, csv_file):
        try:
            data = pandas.read_csv(csv_file, header=0, sep=self.separator)
            if 'time' not in list(data):
                return False, []
            if not all(p in list(data) for p in self.current_columns):
                return False, []
            value_datetime = list(map(lambda x: self.start_time + datetime.timedelta(seconds=x), data['time']))
            str_datetime = list(map(lambda x: x.strftime('%Y/%m/%d\n%H:%M'), value_datetime))
            str_datetime_bis = list(map(lambda x: x.strftime('%d/%m/%y\n%H:%M'), value_datetime))
            time = [data['time'], data['time'], data['time'],
                    data['time'] / 60, data['time'] / 3600, data['time'] / 86400]
            return True, [data, time, str_datetime, str_datetime_bis]
        except:
            return False, []

    def plot(self):
        pass


class MultiSaveVolumeDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time):
        super().__init__('Compute Volume', separator, current_columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for column in self.current_columns:
                axes.plot(time[self.time_format], data[column], '-', color=self.column_colors[column],
                          linewidth=2, label=self.column_labels[column])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)


class MultiSaveFluxDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, cumulative):
        super().__init__('Compute Flux', separator, current_columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.cumulative = cumulative

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for column in self.current_columns:
                if not self.cumulative:
                    axes.plot(time[self.time_format], data[column], '-',
                              color=self.column_colors[column], linewidth=2, label=self.column_labels[column])
                else:
                    axes.plot(time[self.time_format], np.cumsum(data[column]), '-',
                              color=self.column_colors[column], linewidth=2, label=self.column_labels[column])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)


class MultiSavePointDialog(MultiSaveTemporalPlotDialog):
    def __init__(self, separator, current_columns, column_labels, column_colors,
                 xlabel, ylabel, title, time_format, start_time, columns):
        super().__init__('Interpolate on Points', separator, columns, column_labels, column_colors,
                         xlabel, ylabel, title, time_format, start_time)
        self.current_points = current_columns

    def plot(self):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        for (data, time, str_datetime, str_datetime_bis), png_name in zip(self.data, self.out_names):
            axes.clear()
            for point, column in zip(self.current_points, self.current_columns):
                axes.plot(time[self.time_format], data[column], '-',
                          color=self.column_colors[point], linewidth=2, label=self.column_labels[point])
            axes.legend()
            axes.grid(linestyle='dotted')
            axes.set_xlabel(self.xlabel)
            axes.set_ylabel(self.ylabel)
            axes.set_title(self.title)
            if self.time_format in [1, 2]:
                axes.set_xticklabels(str_datetime if self.time_format == 1 else str_datetime_bis)
                for label in axes.get_xticklabels():
                    label.set_rotation(45)
                    label.set_fontsize(8)
            fig.canvas.draw()
            fig.savefig(png_name, dpi=100)

