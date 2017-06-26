from PyQt5.QtWidgets import *
from itertools import islice, cycle
import datetime
import numpy as np

from slf.mesh2D import Mesh2D
from slf.volume import VolumeCalculator
from workflow.Node import Node, SingleInputNode, DoubleInputNode
from gui.util import MapCanvas, PolygonMapCanvas, LineMapCanvas, MapViewer, TemporalPlotViewer, \
    PointAttributeTable, PointLabelEditor


class ShowMeshNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Show\nMesh'
        self.in_port.data_type = 'slf'
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
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return

        if self.has_map:
            self.map.show()
        else:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.initFigure(mesh)

            self.has_map = True
            self.map.canvas.draw()
            self.map.show()
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
        self.success()


class LocateOpenLinesNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nOpen\nLines'
        self.first_in_port.data_type = 'slf'
        self.second_in_port.data_type = 'polyline 2d'
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

    def configure(self):
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

        if self.has_map:
            self.map.show()
        else:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Line %d' % (i+1) for i in range(len(line_node.data))],
                                         list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                              len(line_node.data))))

            self.has_map = True
            self.success()
            self.map.canvas.draw()
            self.map.show()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            line_node = self.second_in_port.mother.parentItem()
            mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Line %d' % (i+1) for i in range(len(line_node.data))],
                                         list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                              len(line_node.data))))

            self.has_map = True
            self.map.canvas.draw()
        self.success()


class LocatePolygonsNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nPolygons'
        self.first_in_port.data_type = 'slf'
        self.second_in_port.data_type = 'polygon 2d'
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

    def configure(self):
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

        if self.has_map:
            self.map.show()
        else:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Polygon %d' % (i+1) for i in range(len(line_node.data))])

            self.has_map = True
            self.success()
            self.map.canvas.draw()
            self.map.show()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        line_node = self.second_in_port.mother.parentItem()
        if not self.has_map:
            mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Polygon %d' % (i+1) for i in range(len(line_node.data))])

            self.has_map = True
            self.map.canvas.draw()
        self.success()


class LocateOpenLinesNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nOpen\nLines'
        self.first_in_port.data_type = 'slf'
        self.second_in_port.data_type = 'polyline 2d'
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

    def configure(self):
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

        if self.has_map:
            self.map.show()
        else:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Line %d' % (i+1) for i in range(len(line_node.data))],
                                         list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                              len(line_node.data))))

            self.has_map = True
            self.success()
            self.map.canvas.draw()
            self.map.show()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
            line_node = self.second_in_port.mother.parentItem()
            mesh = Mesh2D(self.first_in_port.mother.parentItem().data.header)
            self.map.canvas.reinitFigure(mesh, line_node.data.lines,
                                         ['Line %d' % (i+1) for i in range(len(line_node.data))],
                                         list(islice(cycle(['b', 'r', 'g', 'y', 'k', 'c', '#F28AD6', 'm']),
                                              len(line_node.data))))

            self.has_map = True
            self.map.canvas.draw()
        self.success()


class LocatePointsNode(DoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Locate\nPoints'
        self.first_in_port.data_type = 'slf'
        self.second_in_port.data_type = 'point 2d'
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

    def configure(self):
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

        if self.has_map:
            self.map.show()
        else:
            mesh = Mesh2D(parent_node.data.header)
            self.map.canvas.initFigure(mesh)
            points = point_node.data.points
            self.map.canvas.axes.scatter(*zip(*points))
            labels = ['%d' % (i+1) for i in range(len(points))]
            for label, (x, y) in zip(labels, points):
                self.map.canvas.axes.annotate(label, xy=(x, y), xytext=(-20, 20), fontsize=8,
                                              textcoords='offset points', ha='right', va='bottom',
                                              bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                                              arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

            self.map.canvas.draw()

            self.has_map = True
            self.success()
            self.map.canvas.draw()
            self.map.show()

    def run(self):
        success = super().run_upward()
        if not success:
            self.fail('input failed.')
            return
        if not self.has_map:
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
            self.has_map = True
            self.map.canvas.draw()
        self.success()


class VolumePlotNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Visualization'
        self.label = 'Volume\nPlot'
        self.in_port.data_type = 'volume csv'
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
        self.in_port.data_type = 'flux csv'
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
            if parent_node.state != Node.SUCCESS:
                QMessageBox.critical(None, 'Error', 'Configure and run the input before configure this node!',
                                     QMessageBox.Ok)
                return

        if self.has_plot:
            self.plot_viewer.show()
        else:
            self.plot_viewer.get_data(parent_node.data)
            self.has_plot = True
            self.plot_viewer.draw()
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
        self.in_port.data_type = 'point csv'
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
        self.in_port.data_type = 'point 2d'
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
        self.var_ID = None
        self.second_var_ID = None
        self.language = 'fr'

        self.current_columns = ('Polygon 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.poly_menu = QMenu('&Polygons', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.poly_menu)

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


class FluxPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('section')
        self.language = 'fr'
        self.flux_title = ''
        self.var_IDs = []
        self.cumulative = False

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

        self.poly_menu = QMenu('&Sections', self)
        self.poly_menu.addAction(self.selectColumnsAct)
        self.poly_menu.addAction(self.editColumnNamesAct)
        self.poly_menu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.poly_menu)

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


class PointPlotViewer(TemporalPlotViewer):
    def __init__(self):
        super().__init__('point')
        self.language = 'fr'
        self.var_IDs = []
        self.current_var = ''
        self.points = None
        self.indices = []

        self.select_variable = QAction('Select\nvariable', self, triggered=self.selectVariableEvent,
                                       icon=self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.current_columns = ('Point 1',)
        self.toolBar.addAction(self.selectColumnsAct)
        self.toolBar.addAction(self.editColumnNamesAct)
        self.toolBar.addAction(self.editColumColorAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.convertTimeAct)
        self.toolBar.addAction(self.changeDateAct)

        self.point_menu = QMenu('&Data', self)
        self.point_menu.addAction(self.select_variable)
        self.point_menu.addSeparator()
        self.point_menu.addAction(self.selectColumnsAct)
        self.point_menu.addAction(self.editColumnNamesAct)
        self.point_menu.addAction(self.editColumColorAct)

        self.menuBar.addMenu(self.point_menu)

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