from itertools import islice, cycle
import numpy as np
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import *

from slf import Serafin
from slf.mesh2D import Mesh2D
from slf.interpolation import MeshInterpolator
from workflow.datatypes import SerafinData
from workflow.Node import Node, SingleInputNode, DoubleInputNode
from workflow.util import MultiLoadSerafinDialog, MultiSaveDialog, VolumePlotViewer, \
    FluxPlotViewer, PointPlotViewer, MultiSaveProjectLinesDialog, VerticalProfilePlotViewer
from gui.util import MapCanvas, PolygonMapCanvas, LineMapCanvas, MapViewer, \
    PointAttributeTable, ProjectLinesPlotViewer


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
            self.progress_bar.setVisible(True)
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
        if not self.has_plot:
            self._prepare()
        self.plot_viewer.showMaximized()
        self.success()

    def _prepare(self):
        input_data = self.first_in_port.mother.parentItem().data
        mesh = MeshInterpolator(input_data.header, False)
        if input_data.has_index:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.progress_bar.setVisible(True)
            self.construct_mesh(mesh)
            input_data.has_index = True
            input_data.index = mesh.index
            input_data.triangles = mesh.triangles

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_plot:
            self._prepare()
        self.plot_viewer.showMaximized()
        self.success()


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

