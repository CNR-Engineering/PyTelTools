import sys
from collections import defaultdict

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from workflow.Node import Port
from workflow.nodes_io import ReadSerafinNode, WriteSerafinNode
from workflow.Link import Link


class WorkflowTree:
    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes
        self.nb_nodes = len(nodes)
        self.tree = defaultdict(set)

    def add_edge(self, first_node, first_port, second_node, second_port):
        p1 = self.nodes[first_node].ports[first_port]
        p2 = self.nodes[second_node].ports[second_port]
        if p1.type == Port.INPUT and p2.type == Port.OUTPUT:
            if p1.data_type == p2.data_type:
                if (second_node, second_port) not in self.tree[first_node, first_port]:
                    self.tree[first_node, first_port].add((second_node, second_port))
                    return True, ''
                return False, 'already'
            return False, 'type'
        if p1.type == Port.OUTPUT and p2.type == Port.INPUT:
            if p1.data_type == p2.data_type:
                if (first_node, first_port) not in self.tree[second_node, second_port]:
                    self.tree[second_node, second_port].add((first_node, first_port))
                    return True, ''
                return False, 'already'
            return False, 'type'
        return False, 'io'

    def remove_edge(self, from_node, from_port, to_node, to_port):
        self.tree[from_node, from_port].remove((to_node, to_port))


class TreeScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(QRectF(0, 0, 800, 600))
        self.transform = QTransform()

        self.tree = WorkflowTree([ReadSerafinNode(0),
                                  WriteSerafinNode(1)])

        self.current_line = QGraphicsLineItem()
        self.addItem(self.current_line)
        self.current_line.setVisible(False)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        self.current_line.setPen(pen)
        self.current_port = None

        for node in self.tree.nodes:
            self.addItem(node)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        for node_index, node in enumerate(self.tree.nodes):
            for port_index, port in enumerate(node.ports):
                if port.isSelected():
                    self.current_port = (node_index, port_index)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.current_port is not None:
            port = self.tree.nodes[self.current_port[0]].ports[self.current_port[1]]
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

    def _handle_add_link(self, target_item):
        port_index = target_item.index
        node_index = target_item.parentItem().index
        if node_index == self.current_port[0]:
            return
        success, cause = self.tree.add_edge(self.current_port[0], self.current_port[1], node_index, port_index)
        if success:
            first_node = self.tree.nodes[self.current_port[0]]
            first_port = first_node.ports[self.current_port[1]]
            second_node = self.tree.nodes[node_index]
            second_port = second_node.ports[port_index]
            link = Link(first_port, second_port)
            first_node.add_link(link)
            second_node.add_link(link)
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
                                     'Connections can only be established between Input and Output ports!',
                                     QMessageBox.Ok)

    def _handle_remove_link(self, target_item):
        msg = QMessageBox.warning(None, 'Confirm delete',
                                  'Do you want to delete this link?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        from_port, to_port = target_item.from_port, target_item.to_port
        from_node, to_node = from_port.parentItem(), from_port.parentItem()
        from_node.remove_link(target_item)
        to_node.remove_link(target_item)
        self.tree.remove_edge(from_node.index, from_node.ports.index(from_port),
                              to_node.index, to_node.ports.index(to_port))
        self.removeItem(target_item)


class TreeView(QGraphicsView):
    def __init__(self):
        super().__init__(TreeScene())
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    def resizeEvent(self, event):
        self.scene().setSceneRect(QRectF(0, 0, self.width()-10, self.height()-10))


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
    view = TreeView()
    view.show()
    app.exec_()


