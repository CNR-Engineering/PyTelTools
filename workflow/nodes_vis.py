from itertools import islice, cycle
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.axes_grid1 import make_axes_locatable
from PyQt5.QtWidgets import *

from slf.mesh2D import Mesh2D
from slf.interpolation import MeshInterpolator
from workflow.Node import Node, SingleInputNode, DoubleInputNode
from workflow.util import MultiLoadSerafinDialog, MultiFigureSaveDialog, VolumePlotViewer, \
    FluxPlotViewer, PointPlotViewer, MultiSaveProjectLinesDialog, VerticalProfilePlotViewer, \
    MultiSaveMultiVarLinePlotDialog, MultiSaveMultiFrameLinePlotDialog, MultiSaveVerticalProfileDialog
from gui.util import MapCanvas, PolygonMapCanvas, LineMapCanvas, MapViewer, \
    PointAttributeTable, ProjectLinesPlotViewer, MultiVarLinePlotViewer, MultiFrameLinePlotViewer


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


class MultiVarLinePlotNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'MultiVar\nLine Plot'
        self.first_in_port.data_type = ('slf',)
        self.second_in_port.data_type = ('polyline 2d',)
        self.state = Node.READY
        self.has_plot = False

        self.plot_viewer = MultiVarLinePlotViewer()
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
        if input_data.triangles:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.progress_bar.setVisible(True)
            self.construct_mesh(mesh)
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

    def plot(self, values, distances, values_internal, distances_internal, current_vars, png_name):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)
        if self.plot_viewer.control.addInternal.isChecked():
            if self.plot_viewer.control.intersection.isChecked():
                for i, var in enumerate(current_vars):
                    axes.plot(distances, values[i], '-', linewidth=2, label=var,
                              color=self.plot_viewer.var_colors[var])
                    axes.plot(distances_internal, values_internal[i],
                              'o', color=self.plot_viewer.var_colors[var])
            else:
                for i, var in enumerate(current_vars):
                    axes.plot(distances_internal, values_internal[i], 'o-', linewidth=2, label=var,
                              color=self.plot_viewer.var_colors[var])

        else:
            if self.plot_viewer.control.intersection.isChecked():
                for i, var in enumerate(current_vars):
                    axes.plot(distances, values[i], '-', linewidth=2, label=var,
                              color=self.plot_viewer.var_colors[var])
            else:
                for i, var in enumerate(current_vars):
                    axes.plot(distances_internal, values_internal[i], '-', linewidth=2, label=var,
                              color=self.plot_viewer.var_colors[var])

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
        dlg = MultiFigureSaveDialog('_multi_var_line_plot')
        if dlg.exec_() == QDialog.Accepted:
            output_options = dlg.panel.get_options()
        else:
            return

        line_id = int(self.plot_viewer.control.lineBox.currentText().split()[1]) - 1
        time_index = int(self.plot_viewer.control.timeSelection.index.text()) - 1
        compute_options = (self.second_in_port.mother.parentItem().data.lines,
                           line_id, time_index, current_vars, self.first_in_port.mother.parentItem().data.language)

        dlg = MultiSaveMultiVarLinePlotDialog(self, input_options, output_options, compute_options)
        dlg.run()
        dlg.exec_()


class MultiFrameLinePlotNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'MultiFrame\nLine Plot'
        self.first_in_port.data_type = ('slf',)
        self.second_in_port.data_type = ('polyline 2d',)
        self.state = Node.READY
        self.has_plot = False

        self.plot_viewer = MultiFrameLinePlotViewer()
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
        if input_data.triangles:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.progress_bar.setVisible(True)
            self.construct_mesh(mesh)
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

    def plot(self, values, distances, values_internal, distances_internal, time_indices, png_name):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)
        if self.plot_viewer.control.addInternal.isChecked():
            if self.plot_viewer.control.intersection.isChecked():
                for i, index in enumerate(time_indices):
                    axes.plot(distances, values[i], '-', linewidth=2,
                              label='Frame %d' % (index+1), color=self.plot_viewer.frame_colors[index])
                    axes.plot(distances_internal, values_internal[i],
                              'o', color=self.plot_viewer.frame_colors[index])

            else:
                for i, index in enumerate(time_indices):
                    axes.plot(distances, values[i], 'o-', linewidth=2,
                              label='Frame %d' % (index+1), color=self.plot_viewer.frame_colors[index])

        else:
            if self.plot_viewer.control.intersection.isChecked():
                for i, index in enumerate(time_indices):
                    axes.plot(distances, values[i], '-', linewidth=2,
                              label='Frame %d' % (index+1), color=self.plot_viewer.frame_colors[index])
            else:
                for i, index in enumerate(time_indices):
                    axes.plot(distances_internal, values_internal[i], '-', linewidth=2,
                              label='Frame %d' % (index+1), color=self.plot_viewer.frame_colors[index])

        axes.legend()
        axes.grid(linestyle='dotted')
        axes.set_xlabel(self.plot_viewer.plotViewer.current_xlabel)
        axes.set_ylabel(self.plot_viewer.plotViewer.current_ylabel)
        axes.set_title(self.plot_viewer.plotViewer.current_title)
        fig.canvas.draw()
        fig.savefig(png_name, dpi=100)

    def multi_save(self):
        time_indices = self.plot_viewer.getTime()
        if not time_indices:
            return
        dlg = MultiLoadSerafinDialog([])
        if dlg.exec_() == QDialog.Accepted:
            input_options = (dlg.dir_paths, dlg.slf_name, dlg.job_ids)
        else:
            return
        dlg = MultiFigureSaveDialog('_multi_frame_line_plot')
        if dlg.exec_() == QDialog.Accepted:
            output_options = dlg.panel.get_options()
        else:
            return

        line_id = int(self.plot_viewer.control.lineBox.currentText().split()[1]) - 1
        current_var = self.plot_viewer.control.varBox.currentText().split(' (')[0]
        compute_options = (self.second_in_port.mother.parentItem().data.lines,
                           line_id, current_var, time_indices, self.first_in_port.mother.parentItem().data.language)

        dlg = MultiSaveMultiFrameLinePlotDialog(self, input_options, output_options, compute_options)
        dlg.run()
        dlg.exec_()


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
        if input_data.triangles:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.progress_bar.setVisible(True)
            self.construct_mesh(mesh)
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

    def plot(self, values, distances, values_internal, distances_internal, current_vars, png_name):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)
        if self.plot_viewer.control.addInternal.isChecked():
            if self.plot_viewer.control.intersection.isChecked():
                for line_id, variables in current_vars.items():
                    for var in variables:
                        axes.plot(distances[line_id], values[line_id][var],
                                  linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))

                        axes.plot(distances_internal[line_id], values_internal[line_id][var], 'o',
                                  color=self.plot_viewer.line_colors[line_id])
            else:
                for line_id, variables in current_vars.items():
                    for var in variables:
                        axes.plot(distances_internal[line_id], values_internal[line_id][var],
                                  marker='o', linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))

        else:
            if self.plot_viewer.control.intersection.isChecked():
                for line_id, variables in current_vars.items():
                    for var in variables:
                        axes.plot(distances[line_id], values[line_id][var],
                                  linestyle=self.plot_viewer.current_linestyles[var],
                                  color=self.plot_viewer.line_colors[line_id], linewidth=2,
                                  label='%s$_%d$' % (var, line_id+1))
            else:
                for line_id, variables in current_vars.items():
                    for var in variables:
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
        dlg = MultiFigureSaveDialog('_project_plot')
        if dlg.exec_() == QDialog.Accepted:
            output_options = dlg.panel.get_options()
        else:
            return

        ref_id = int(self.plot_viewer.control.lineBox.currentText().split()[1]) - 1
        reference = self.plot_viewer.lines[ref_id]
        max_distance = reference.length()
        time_index = int(self.plot_viewer.control.timeSelection.index.text()) - 1
        compute_options = (self.second_in_port.mother.parentItem().data.lines, ref_id, reference, max_distance,
                           time_index, current_vars, self.first_in_port.mother.parentItem().data.language)

        dlg = MultiSaveProjectLinesDialog(self, input_options, output_options, compute_options)
        dlg.run()
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

        self.multi_save_act = QAction('Multi-Save', None, triggered=self.multi_save,
                                      icon=self.plot_viewer.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.plot_viewer.toolBar.addSeparator()
        self.plot_viewer.toolBar.addAction(self.multi_save_act)

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
        if parent_node.data.header.is_2d:
            QMessageBox.critical(None, 'Error', 'The input file is not 3D!',
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
            if not self._prepare():
                QMessageBox.critical(None, 'Error', 'No point inside the mesh', QMessageBox.Ok)
                self.fail('no point inside the mesh')
                return
        self.plot_viewer.showMaximized()
        self.success()

    def _prepare(self):
        input_data = self.first_in_port.mother.parentItem().data
        mesh = MeshInterpolator(input_data.header, False)
        if input_data.triangles:
            mesh.index = input_data.index
            mesh.triangles = input_data.triangles
        else:
            self.progress_bar.setVisible(True)
            self.construct_mesh(mesh)
            input_data.index = mesh.index
            input_data.triangles = mesh.triangles

        points = self.second_in_port.mother.parentItem().data.points
        is_inside, point_interpolators = mesh.get_point_interpolators(points)

        nb_inside = sum(map(int, is_inside))
        point_indices = [i for i in range(len(points)) if is_inside[i]]
        if nb_inside == 0:
            return False
        self.plot_viewer.get_data(input_data, points, point_interpolators, point_indices)
        return True

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_plot:
            if not self._prepare():
                QMessageBox.critical(None, 'Error', 'No point inside the mesh', QMessageBox.Ok)
                self.fail('no point inside the mesh')
                return
        self.plot_viewer.showMaximized()
        self.success()

    def plot(self, time, y, z, triangles, str_datetime, str_datetime_bis, png_name):
        fig, axes = plt.subplots(1)
        fig.set_size_inches(8, 6)

        if self.plot_viewer.clim is not None:
            axes.tripcolor(time[self.plot_viewer.timeFormat], y, triangles, z, cmap=self.plot_viewer.current_style,
                           vmin=self.plot_viewer.clim[0], vmax=self.plot_viewer.clim[1])
        else:
            axes.tripcolor(time[self.plot_viewer.timeFormat], y, triangles, z, cmap=self.plot_viewer.current_style)

        divider = make_axes_locatable(axes)
        cax = divider.append_axes('right', size='5%', pad=0.2)
        cmap = cm.ScalarMappable(cmap=self.plot_viewer.current_style)
        if self.plot_viewer.clim is not None:
            cmap.set_array(np.linspace(self.plot_viewer.clim[0], self.plot_viewer.clim[1], 1000))
        else:
            cmap.set_array(np.linspace(np.min(z), np.max(z), 1000))
        fig.colorbar(cmap, cax=cax)

        axes.set_xlabel(self.plot_viewer.current_xlabel)
        axes.set_ylabel(self.plot_viewer.current_ylabel)
        axes.set_title(self.plot_viewer.current_title)
        if self.plot_viewer.timeFormat in [1, 2]:
            axes.set_xticklabels(str_datetime if self.plot_viewer.timeFormat == 1
                                 else str_datetime_bis)
            for label in axes.get_xticklabels():
                label.set_rotation(45)
                label.set_fontsize(8)
        fig.canvas.draw()
        fig.savefig(png_name, dpi=100)

    def multi_save(self):
        dlg = MultiLoadSerafinDialog([])
        if dlg.exec_() == QDialog.Accepted:
            input_options = (dlg.dir_paths, dlg.slf_name, dlg.job_ids)
        else:
            return
        dlg = MultiFigureSaveDialog('_vertical_profile_plot')
        if dlg.exec_() == QDialog.Accepted:
            output_options = dlg.panel.get_options()
        else:
            return

        point_id = int(self.plot_viewer.current_columns[0].split()[1]) - 1
        point = self.plot_viewer.points[point_id]
        compute_options = (point, self.plot_viewer.current_var, self.first_in_port.mother.parentItem().data.language)
        dlg = MultiSaveVerticalProfileDialog(self, input_options, output_options, compute_options)
        dlg.run()
        dlg.exec_()


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

