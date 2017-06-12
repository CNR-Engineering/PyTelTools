from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from workflow.Node import Port, Box, Node
from workflow.nodes_io import LoadSerafinNode
from workflow.Link import Link


def add_link(from_port, to_port):
    if to_port.is_connected_to(from_port) and from_port.is_connected_to(to_port):
        return False, 'already'
    elif to_port.data_type != from_port.data_type:
        return False, 'type'
    elif to_port.has_mother():
        return False, 'another'
    from_port.connect(to_port)
    to_port.connect(from_port)
    return True, ''


class TreeScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.language = 'fr'
        self.overwrite = True

        self.setSceneRect(QRectF(0, 0, 800, 600))
        self.transform = QTransform()
        self.selectionChanged.connect(self.selection_changed)

        self.nodes = {0: LoadSerafinNode(0)}
        self.nodes[0].moveBy(50, 50)
        self.nb_nodes = 1

        self.current_line = QGraphicsLineItem()
        self.addItem(self.current_line)
        self.current_line.setVisible(False)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        self.current_line.setPen(pen)
        self.current_port = None

        for node in self.nodes.values():
            self.addItem(node)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        for node_index, node in enumerate(self.nodes.values()):
            for port_index, port in enumerate(node.ports):
                if port.isSelected():
                    self.current_port = (node_index, port_index)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.current_port is not None:
            port = self.nodes[self.current_port[0]].ports[self.current_port[1]]
            self.current_line.setLine(QLineF(port.mapToScene(port.rect().center()), event.scenePos()))
            self.current_line.setVisible(True)

    def mouseReleaseEvent(self, event):
        if self.current_port is not None:
            target_item = self.itemAt(event.scenePos(), self.transform)
            if isinstance(target_item, Port):
                self._handle_add_link(target_item)
            self.current_line.setVisible(False)
            self.current_port = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        target_item = self.itemAt(event.scenePos(), self.transform)
        if isinstance(target_item, Link):
            self._handle_remove_link(target_item)
        elif isinstance(target_item, Box):
            node = target_item.parentItem()
            node.configure()
            self.selection_changed()

    def selection_changed(self):
        view = self.views()[0]
        selected = self.selectedItems()
        if not selected:
            view.deselect_node()
            return
        selected = selected[0]
        if isinstance(selected, Node):
            view.select_node(selected)
        else:
            view.deselect_node()

    def add_node(self, node, pos):
        self.addItem(node)
        self.nodes[node.index()] = node
        self.nb_nodes += 1
        node.moveBy(pos.x(), pos.y())

    def _handle_add_link(self, target_item):
        port_index = target_item.index()
        node_index = target_item.parentItem().index()
        if node_index == self.current_port[0]:
            return

        from_node, to_node, from_port, to_port = self._permute(self.current_port[0], self.current_port[1],
                                                               node_index, port_index)
        if from_port is None:
            QMessageBox.critical(None, 'Error',
                                 'Connections can only be established between Output and Input ports!',
                                 QMessageBox.Ok)
            return
        success, cause = add_link(from_port, to_port)
        if success:
            link = Link(from_port, to_port)
            from_node.add_link(link)
            to_node.add_link(link)
            self.addItem(link)
            link.setZValue(-1)
        else:
            if cause == 'already':
                QMessageBox.critical(None, 'Error', 'These two ports are already connected.',
                                     QMessageBox.Ok)
            elif cause == 'type':
                QMessageBox.critical(None, 'Error', 'These two ports cannot be connected: different data types.',
                                     QMessageBox.Ok)
            else:
                QMessageBox.critical(None, 'Error',
                                     'The input port is already connected to another port.',
                                     QMessageBox.Ok)

    def _handle_remove_link(self, target_item):
        msg = QMessageBox.warning(None, 'Confirm delete',
                                  'Do you want to delete this link?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        target_item.remove()
        self.removeItem(target_item)

    def handle_remove_node(self, node):
        msg = QMessageBox.warning(None, 'Confirm delete',
                                  'Do you want to delete this node?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        self.removeItem(node)
        for link in node.links.copy():
            link.remove()
            self.removeItem(link)
        del self.nodes[node.index()]

        new_nodes = {}
        self.nb_nodes -= 1

        for index, node in zip(range(self.nb_nodes), self.nodes.values()):
            new_nodes[index] = node
            node.set_index(index)
        self.nodes = new_nodes

    def _permute(self, first_node_index, first_port_index, second_node_index, second_port_index):
        first_node = self.nodes[first_node_index]
        second_node = self.nodes[second_node_index]
        p1 = first_node.ports[first_port_index]
        p2 = second_node.ports[second_port_index]
        if p1.type == Port.OUTPUT and p2.type == Port.INPUT:
            return first_node, second_node, p1, p2
        elif p1.type == Port.INPUT and p2.type == Port.OUTPUT:
            return second_node, first_node, p2, p1
        return None, None, None, None
