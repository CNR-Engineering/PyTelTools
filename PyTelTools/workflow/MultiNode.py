from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import math


class MultiPort(QGraphicsRectItem):
    WIDTH = 20
    INPUT, OUTPUT = True, False
    COLOR = {OUTPUT: QColor(100, 120, 200, 255), INPUT: QColor(250, 230, 40, 255)}

    def __init__(self, index, x, y, port_type):
        super().__init__(x, y, MultiPort.WIDTH, MultiPort.WIDTH)
        self._index = index
        self.type = port_type
        self.data_type = ''
        self.setFlag(QGraphicsItem.ItemIsSelectable)

    def index(self):
        return self._index

    def paint(self, painter, options, widget=None):
        painter.fillRect(self.rect(), MultiPort.COLOR[self.type])
        super().paint(painter, options)

    def boundingRect(self):
        return self.rect()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def lines(self):
        p1, p2, p3, p4 = self.rect().bottomLeft(), self.rect().topLeft(), \
                         self.rect().topRight(), self.rect().bottomRight()
        for (a, b) in [(p1, p2), (p2, p3), (p3, p4), (p4, p1)]:
            yield QLineF(self.mapToScene(a), self.mapToScene(b))


class MultiInputPort(MultiPort):
    """!
    MultiPort receiving input stream
    """
    def __init__(self, index, x, y):
        super().__init__(index, x, y, MultiPort.INPUT)
        self.mother = None

    def connect(self, output_port):
        self.mother = output_port


class MultiOutputPort(MultiPort):
    """!
    MultiPort sending output stream
    """
    def __init__(self, index, x, y):
        super().__init__(index, x, y, MultiPort.OUTPUT)
        self.children = set()

    def connect(self, input_port):
        self.children.add(input_port)
        
        
class Box(QGraphicsRectItem):
    WIDTH, HEIGHT = 80, 60

    def __init__(self, parent):
        super().__init__(0, 0, Box.WIDTH, Box.HEIGHT)
        self.setParentItem(parent)
        

class MultiNode(QGraphicsItem):
    """!
    Node representing a tool with its state, ports, ... (in Multi tab)
    """
    NOT_CONFIGURED, READY, SUCCESS, PARTIAL_FAIL, FAIL = 'Not configured', 'Ready', 'Success', 'Partial success', 'Fail'
    COLOR = {NOT_CONFIGURED: QColor(220, 255, 255, 255), READY: QColor(250, 220, 165, 255),
             SUCCESS: QColor(180, 250, 165, 255), PARTIAL_FAIL: QColor(255, 190, 160, 255),
             FAIL: QColor(255, 160, 160, 255)}

    def __init__(self, index):
        super().__init__()
        self._index = index
        self.box = Box(self)
        
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self.dashed_pen = QPen(Qt.black, 1, Qt.DashLine)

        self.label = ''
        self.category = ''

        self.state = MultiNode.READY
        self.message = ''

        self.expected_input = (0,)
        self.nb_success = 0
        self.nb_fail = 0
        self.input_index = set()
        self.double_input = False
        self.two_in_one_out = False
        self.second_parent = False  # special properties for pre-bifurcation nodes
        self.ports = []
        self.options = tuple()

    def index(self):
        return self._index

    def add_port(self, port):
        self.ports.append(port)
        port.setParentItem(self)

    def boundingRect(self):
        pos = self.box.rect().topLeft()
        return QRectF(pos.x()-5-MultiPort.WIDTH, pos.y()-20, Box.WIDTH+2*MultiPort.WIDTH+10,
                      Box.HEIGHT+2*MultiPort.WIDTH+20)

    def paint(self, painter, options, widget=None):
        painter.fillRect(self.box.rect(), MultiNode.COLOR[self.state])
        painter.drawText(self.box.rect().topLeft()+QPointF(4, -3), self.state)
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.drawText(self.box.rect(), Qt.AlignCenter, self.label)
        if self.isSelected():
            painter.setPen(self.dashed_pen)
            painter.drawRect(self.boundingRect())

    def name(self):
        return ' '.join(self.label.split())

    def load(self, options):
        pass

    def mark(self, node_index):
        self.input_index.add(node_index)

    def update_input(self, nb_input):
        self.expected_input = (nb_input,)

    def nb_files(self):
        return max(self.expected_input)


class MultiLink(QGraphicsLineItem):
    """!
    Link between MultiPorts
    """
    def __init__(self, from_port, to_port):
        """!
        @brief Link between two MultiPorts (of different MultiNodes)
        @param from_port <MultiOutputPort>: origin port
        @param to_port <MultiInputPort>: destination port
        """
        super().__init__()
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

    def save(self):
        return '|'.join(map(str, [self.from_port.parentItem().index(), self.from_port.index(),
                                  self.to_port.parentItem().index(), self.to_port.index()]))

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

    def boundingRect(self):
        return self.selection_polygon.boundingRect()

    def shape(self):
        path = QPainterPath()
        path.addPolygon(self.selection_polygon)
        return path

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
            p3 = box1.bottomRight() + QPointF(0, MultiPort.WIDTH/2)
            self.head = QLineF(p1, p3)
            line = QLineF(p3, p2)
        else:
            self.head = None
        box2 = self.to_port.parentItem().mapRectToScene(self.to_port.parentItem().box.rect())
        if box2.intersects(self.boundingRect()):
            p4 = box2.topLeft() + QPointF(-MultiPort.WIDTH/2, 0)
            self.tail = QLineF(p4, p2)
            line = QLineF(line.p1(), p4)
        else:
            self.tail = None

        self.setLine(line)
        self.update_polygon()
        self.update()


class MultiSingleInputNode(MultiNode):
    """!
    MultiNode with single input (without output)
    """
    def __init__(self, index):
        super().__init__(index)
        self.in_port = MultiInputPort(0, -MultiPort.WIDTH, Box.HEIGHT/2-MultiPort.WIDTH/2)
        self.add_port(self.in_port)


class MultiSingleOutputNode(MultiNode):
    """!
    MultiNode with single output (without input)
    """
    def __init__(self, index):
        super().__init__(index)
        self.out_port = MultiOutputPort(0, Box.WIDTH/2-MultiPort.WIDTH/2, Box.HEIGHT)
        self.add_port(self.out_port)


class MultiOneInOneOutNode(MultiNode):
    """!
    MultiNode with single input and single output
    """
    def __init__(self, index):
        super().__init__(index)
        self.in_port = MultiInputPort(0, -MultiPort.WIDTH, Box.HEIGHT/2-MultiPort.WIDTH/2)
        self.out_port = MultiOutputPort(1, Box.WIDTH/2-MultiPort.WIDTH/2, Box.HEIGHT)
        self.add_port(self.in_port)
        self.add_port(self.out_port)
        self.expected_input = (0,)


class MultiTwoInOneOutNode(MultiNode):
    """!
    MultiNode with two inputs and single output
    """
    def __init__(self, index):
        super().__init__(index)
        self.first_in_port = MultiInputPort(0, -MultiPort.WIDTH, Box.HEIGHT/4-MultiPort.WIDTH/2)
        self.second_in_port = MultiInputPort(1, -MultiPort.WIDTH, 3*Box.HEIGHT/4-MultiPort.WIDTH/2)
        self.out_port = MultiOutputPort(2, Box.WIDTH/2-MultiPort.WIDTH/2, Box.HEIGHT)
        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.add_port(self.out_port)
        self.expected_input = (0, 0)
        self.two_in_one_out = True
        self.first_ids = []  # information about coupled multi-input streams
        self.second_ids = []
        self.pending_data = {}

        self.has_auxiliary = False
        self.auxiliary_data = None

    def set_auxiliary_data(self, data):
        self.has_auxiliary = True
        self.auxiliary_data = data

    def update_input(self, nb_input):
        self.expected_input = (nb_input, nb_input)


class MultiDoubleInputNode(MultiNode):
    """!
    MultiNode with two inputs (without output)
    """
    def __init__(self, index):
        super().__init__(index)
        self.first_in_port = MultiInputPort(0, -MultiPort.WIDTH, Box.HEIGHT/4-MultiPort.WIDTH/2)
        self.second_in_port = MultiInputPort(1, -MultiPort.WIDTH, 3*Box.HEIGHT/4-MultiPort.WIDTH/2)
        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.expected_input = (0, 1)
        self.double_input = True
        self.auxiliary_data = None

    def update_input(self, nb_input):
        self.expected_input = (nb_input, 1)

    def set_auxiliary_data(self, data):
        self.auxiliary_data = data
