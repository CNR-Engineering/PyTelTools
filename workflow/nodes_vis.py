from PyQt5.QtWidgets import *
from itertools import islice, cycle

from slf.mesh2D import Mesh2D
from workflow.Node import Node, SingleInputNode, DoubleInputNode
from gui.util import MapCanvas, PolygonMapCanvas, LineMapCanvas, MapViewer


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

