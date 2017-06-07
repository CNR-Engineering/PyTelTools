import math
from workflow.Node import Port
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class Link(QGraphicsLineItem):
    def __init__(self, first_port, second_port):
        super().__init__()
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.selection_offset = 8
        self.selection_polygon = None
        if first_port.type == Port.INPUT:
            self.from_port = first_port
            self.to_port = second_port
        else:
            self.from_port = second_port
            self.to_port = first_port
        self.update_nodes()

    def update_polygon(self):
        angle = self.line().angle() * math.pi / 180
        dx = self.selection_offset * math.sin(angle)
        dy = self.selection_offset * math.cos(angle)
        offset1 = QPointF(dx, dy)
        offset2 = QPointF(-dx, -dy)
        self.selection_polygon = QPolygonF([self.line().p1()+offset1, self.line().p1()+offset2,
                                            self.line().p2()+offset2, self.line().p2()+offset1])

    def boundingRect(self):
        return self.selection_polygon.boundingRect()

    def shape(self):
        path = QPainterPath()
        path.addPolygon(self.selection_polygon)
        return path

    def paint(self, painter, options, widget=None):
        painter.setPen(QPen(Qt.black, 2))
        painter.drawLine(self.line())
        if self.isSelected():
            painter.setPen(QPen(Qt.black, 1, Qt.DashLine))
            painter.drawPolygon(self.selection_polygon)

    def update_nodes(self):
        p1 = self.from_port.rect().center()
        p2 = self.to_port.rect().center()
        p1 = self.from_port.parentItem().mapToScene(p1)
        p2 = self.to_port.parentItem().mapToScene(p2)
        # TODO: connect two port without collision
        self.setLine(QLineF(p1, p2))
        self.update_polygon()
        self.update()

