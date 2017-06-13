import math
from workflow.Node import Port
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class Link(QGraphicsLineItem):
    def __init__(self, from_port, to_port):
        super().__init__()
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self.head = None
        self.tail = None

        self.selection_offset = 8
        self.arrow_size = 10
        self.selection_polygon = None
        self.from_port = from_port
        self.to_port = to_port
        self.arrow_head = QPolygonF()
        self.update_nodes()

        self.pen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.dashed_pen = QPen(Qt.black, 1, Qt.DashLine)
        self.brush = QBrush(Qt.black)

    def update_polygon(self):
        angle = self.line().angle() * math.pi / 180
        dx = self.selection_offset * math.sin(angle)
        dy = self.selection_offset * math.cos(angle)
        offset1 = QPointF(dx, dy)
        offset2 = QPointF(-dx, -dy)
        if self.head is None and self.tail is None:
            self.selection_polygon = QPolygonF([self.line().p1()+offset1, self.line().p1()+offset2,
                                                self.line().p2()+offset2, self.line().p2()+offset1])
        elif self.tail is None:
            head_angle = self.head.angle() * math.pi / 180
            head_dx = self.selection_offset * math.sin(head_angle)
            head_dy = self.selection_offset * math.cos(head_angle)
            head_offset1 = QPointF(head_dx, head_dy)
            head_offset2 = QPointF(-head_dx, -head_dy)
            self.selection_polygon = QPolygonF([self.line().p1()+offset1, self.head.p1()+head_offset1,
                                                self.head.p1()+head_offset2, self.line().p1()+offset2,
                                                self.line().p2()+offset2, self.line().p2()+offset1])
        elif self.head is None:
            tail_angle = self.tail.angle() * math.pi / 180
            tail_dx = self.selection_offset * math.sin(tail_angle)
            tail_dy = self.selection_offset * math.cos(tail_angle)
            tail_offset1 = QPointF(tail_dx, tail_dy)
            tail_offset2 = QPointF(-tail_dx, -tail_dy)
            self.selection_polygon = QPolygonF([self.line().p1()+offset1, self.line().p1()+offset2,
                                                self.line().p2()+offset2,  self.tail.p2()+tail_offset2,
                                                self.tail.p2()+tail_offset1, self.line().p2()+offset1])
        else:
            head_angle = self.head.angle() * math.pi / 180
            head_dx = self.selection_offset * math.sin(head_angle)
            head_dy = self.selection_offset * math.cos(head_angle)
            head_offset1 = QPointF(head_dx, head_dy)
            head_offset2 = QPointF(-head_dx, -head_dy)
            tail_angle = self.tail.angle() * math.pi / 180
            tail_dx = self.selection_offset * math.sin(tail_angle)
            tail_dy = self.selection_offset * math.cos(tail_angle)
            tail_offset1 = QPointF(tail_dx, tail_dy)
            tail_offset2 = QPointF(-tail_dx, -tail_dy)
            self.selection_polygon = QPolygonF([self.line().p1()+offset1, self.head.p1()+head_offset1,
                                                self.head.p1()+head_offset2, self.line().p1()+offset2,
                                                self.line().p2()+offset2, self.tail.p2()+tail_offset2,
                                                self.tail.p2()+tail_offset1, self.line().p2()+offset1])

    def boundingRect(self):
        return self.selection_polygon.boundingRect()

    def shape(self):
        path = QPainterPath()
        path.addPolygon(self.selection_polygon)
        return path

    def paint(self, painter, options, widget=None):
        painter.setPen(self.pen)
        if self.head is not None:
            painter.drawLine(self.head)
        if self.tail is not None:
            painter.drawLine(self.tail)
        painter.drawLine(self.line())
        if self.isSelected():
            painter.setPen(self.dashed_pen)
            painter.drawPolygon(self.selection_polygon)

        # draw the arrow tip
        if self.tail is not None:
            tail_line = self.tail
        else:
            tail_line = self.line()
        intersection_point = QPointF(0, 0)
        for line in self.to_port.lines():
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            intersection_type = tail_line.intersect(line, intersection_point)
            if intersection_type == QLineF.BoundedIntersection:
                break
        angle = math.acos(tail_line.dx() / tail_line.length())
        if tail_line.dy() >= 0:
            angle = (math.pi * 2) - angle

        arrow_p1 = intersection_point - QPointF(math.sin(angle + math.pi / 3) * self.arrow_size,
                                                math.cos(angle + math.pi / 3) * self.arrow_size)
        arrow_p2 = intersection_point - QPointF(math.sin(angle + math.pi - math.pi / 3) * self.arrow_size,
                                                math.cos(angle + math.pi - math.pi / 3) * self.arrow_size)
        self.arrow_head.clear()
        for p in [intersection_point, arrow_p1, arrow_p2]:
            self.arrow_head.append(p)
        path = QPainterPath()
        path.addPolygon(self.arrow_head)
        painter.fillPath(path, self.brush)

    def update_nodes(self):
        p1 = self.from_port.rect().center()
        p2 = self.to_port.rect().center()
        p1 = self.from_port.parentItem().mapToScene(p1)
        p2 = self.to_port.parentItem().mapToScene(p2)

        line = QLineF(p1, p2)
        self.setLine(line)
        self.update_polygon()

        box1 = self.from_port.parentItem().mapRectToScene(self.from_port.parentItem().box.rect())
        if box1.intersects(self.boundingRect()):
            p3 = box1.bottomRight() + QPointF(0, Port.WIDTH/2)
            self.head = QLineF(p1, p3)
            line = QLineF(p3, p2)
        else:
            self.head = None
        box2 = self.to_port.parentItem().mapRectToScene(self.to_port.parentItem().box.rect())
        if box2.intersects(self.boundingRect()):
            p4 = box2.topLeft() + QPointF(-Port.WIDTH/2, 0)
            self.tail = QLineF(p4, p2)
            line = QLineF(line.p1(), p4)
        else:
            self.tail = None

        self.setLine(line)
        self.update_polygon()
        self.update()

    def remove(self):
        self.from_port.disconnect(self.to_port)
        self.to_port.disconnect()
        self.from_port.parentItem().remove_link(self)
        self.to_port.parentItem().remove_link(self)
        self.to_port.parentItem().reconfigure()

