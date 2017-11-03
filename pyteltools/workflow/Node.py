import math
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from shapely.geometry import Polygon

from .util import ConfigureDialog


class Port(QGraphicsRectItem):
    """!
    Input/output of a Node
    """
    WIDTH = 20
    INPUT, OUTPUT = True, False
    COLOR = {OUTPUT: QColor(100, 120, 200, 255), INPUT: QColor(250, 230, 40, 255)}

    def __init__(self, index, x, y, port_type):
        super().__init__(x, y, Port.WIDTH, Port.WIDTH)
        self._index = index
        self.type = port_type
        self.data_type = tuple()
        self.setFlag(QGraphicsItem.ItemIsSelectable)

    def index(self):
        return self._index

    def paint(self, painter, options, widget=None):
        painter.fillRect(self.rect(), Port.COLOR[self.type])
        super().paint(painter, options)

    def boundingRect(self):
        return self.rect()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.parentItem().setCursor(Qt.CrossCursor)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setSelected(False)
        self.parentItem().setCursor(Qt.ArrowCursor)

    def lines(self):
        p1, p2, p3, p4 = self.rect().bottomLeft(), self.rect().topLeft(), \
                         self.rect().topRight(), self.rect().bottomRight()
        for (a, b) in [(p1, p2), (p2, p3), (p3, p4), (p4, p1)]:
            yield QLineF(self.mapToScene(a), self.mapToScene(b))


class InputPort(Port):
    """!
    Input stream of a Node
    """
    def __init__(self, index, x, y):
        super().__init__(index, x, y, Port.INPUT)
        self.mother = None

    def has_mother(self):
        return self.mother is not None

    def connect(self, output_port):
        self.mother = output_port

    def disconnect(self):
        self.mother = None

    def is_connected_to(self, output_port):
        return self.mother == output_port


class OutputPort(Port):
    """!
    Output stream of a Node
    """
    def __init__(self, index, x, y):
        super().__init__(index, x, y, Port.OUTPUT)
        self.children = set()

    def has_children(self):
        return bool(self.children)

    def connect(self, input_port):
        self.children.add(input_port)

    def disconnect(self, input_port):
        self.children.remove(input_port)

    def is_connected_to(self, input_port):
        return input_port in self.children


class Box(QGraphicsRectItem):
    WIDTH, HEIGHT = 80, 60

    def __init__(self, parent):
        super().__init__(0, 0, Box.WIDTH, Box.HEIGHT)
        self.setParentItem(parent)


class Node(QGraphicsItem):
    """!
    Node representing a tool with its state, ports, ... (in Mono tab)
    """
    # Node status labels <str>
    NOT_CONFIGURED, READY, SUCCESS, FAIL = 'Not configured', 'Ready', 'Success', 'Fail'
    ## Node status colors <{str: PyQt5.QtGui.QColor}>
    COLOR = {NOT_CONFIGURED: QColor(220, 255, 255, 255), READY: QColor(250, 220, 165, 255),
             SUCCESS: QColor(180, 250, 165, 255), FAIL: QColor(255, 160, 160, 255)}

    def __init__(self, index):
        super().__init__()
        self._index = index
        ## Box of the year
        self.box = Box(self)
        ## Progress bar appearing in upper part box <PyQt5.QtWidgets.QProgressBar>
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        ## Progress bar proxy <PyQt5.QtWidgets.QGraphicsProxyWidget>
        self.proxy = QGraphicsProxyWidget(self)
        self.proxy.setWidget(self.progress_bar)
        self.proxy.setGeometry(QRectF(self.boundingRect().topLeft(), self.boundingRect().topRight()+QPointF(0, 30)))
        self.progress_bar.setVisible(False)

        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setCursor(Qt.ArrowCursor)

        ## Help action <PyQt5.QtWidgets.QAction>
        self.help_action = QAction(QWidget().style().standardIcon(QStyle.SP_MessageBoxQuestion), 'Help', None)
        self.dashed_pen = QPen(Qt.black, 1, Qt.DashLine)

        ## Node label <str>
        self.label = ''
        ## Node category <str>
        self.category = ''

        ## Node state (among NOT_CONFIGURED, READY, SUCCESS, FAIL)
        self.state = Node.NOT_CONFIGURED
        ## Node message <str>
        self.message = ''

        ## Input and Output Ports list <[Port]>
        self.ports = []
        ## Links set <set(Link)>
        self.links = set()

    def index(self):
        return self._index

    def set_index(self, index):
        self._index = index

    def name(self):
        return ' '.join(self.label.split())

    def add_port(self, port):
        self.ports.append(port)
        port.setParentItem(self)

    def add_link(self, link):
        self.links.add(link)

    def remove_link(self, link):
        self.links.remove(link)

    def update_links(self):
        for link in self.links:
            link.update_nodes()

    def boundingRect(self):
        pos = self.box.rect().topLeft()
        return QRectF(pos.x()-5-Port.WIDTH, pos.y()-20, Box.WIDTH+2*Port.WIDTH+10, Box.HEIGHT+2*Port.WIDTH+20)

    def paint(self, painter, options, widget=None):
        painter.fillRect(self.box.rect(), Node.COLOR[self.state])
        painter.drawText(self.box.rect().topLeft()+QPointF(4, -3), self.state)
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.drawText(self.box.rect(), Qt.AlignCenter, self.label)
        if self.isSelected():
            painter.setPen(self.dashed_pen)
            painter.drawRect(self.boundingRect())

    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
        self.update_links()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.x() < Port.WIDTH:
            self.setX(Port.WIDTH)
        elif self.x()+self.boundingRect().width() > self.scene().width():
            self.setX(self.scene().width()-self.boundingRect().width())

        if self.y() < Port.WIDTH:
            self.setY(Port.WIDTH)
        elif self.y()+self.boundingRect().height() > self.scene().height():
            self.setY(self.scene().height()-self.boundingRect().height())

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.update_links()
        return result

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction(self.help_action)
        menu.exec_(event.screenPos())

    def get_option_panel(self):
        return QWidget()

    def ready_to_run(self):
        pass

    def configure(self, check=None):
        """Execute configure dialog and check if accepted"""
        configure_dialog = ConfigureDialog(self.get_option_panel(), self.name(), check)
        configure_dialog.message_field.appendPlainText(self.message)
        if configure_dialog.exec_() == QDialog.Accepted:
            self.state = Node.READY
            self.message = ''
            self.update()
            return True
        return False

    def reconfigure(self):
        self.message = ''
        if self.state != Node.NOT_CONFIGURED:
            self.state = Node.READY
            self.update()

    def reconfigure_downward(self):
        for port in self.ports:
            if port.type == Port.OUTPUT:
                for child in port.children:
                    child.parentItem().reconfigure()

    def run_upward(self):
        return True

    def run_downward(self):
        """Try to run current Node and check if succeeded"""
        if self.ready_to_run() and self.state != Node.SUCCESS:
            self.run()
        if self.state != Node.SUCCESS:
            return False
        return True

    def run(self):
        pass

    def construct_mesh(self, mesh):
        five_percent = 0.05 * mesh.nb_triangles
        nb_processed = 0
        current_percent = 0

        for i, j, k in mesh.ikle:
            t = Polygon([mesh.points[i], mesh.points[j], mesh.points[k]])
            mesh.triangles[i, j, k] = t
            mesh.index.insert(i, t.bounds, obj=(i, j, k))

            nb_processed += 1
            if nb_processed > five_percent:
                nb_processed = 0
                current_percent += 5
                self.progress_bar.setValue(current_percent)
                QApplication.processEvents()

        self.progress_bar.setValue(0)
        QApplication.processEvents()

    def save(self):
        return '|'.join([self.category, self.name(), str(self.index()),
                         str(self.pos().x()), str(self.pos().y()), ''])

    def load(self, options):
        self.state = Node.READY

    def success(self, message=''):
        self.progress_bar.setVisible(False)
        self.state = Node.SUCCESS
        self.update()
        self.message = 'Successful. ' + message

    def fail(self, message):
        self.progress_bar.setVisible(False)
        self.state = Node.FAIL
        self.update()
        self.message = 'Failed: ' + message


class Link(QGraphicsLineItem):
    """!
    Link between Ports
    """
    def __init__(self, from_port, to_port):
        """!
        @brief Link between two Ports (of different Nodes)
        @param from_port <OutputPort>: origin port
        @param to_port <InputPort>: destination port
        """
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


class SingleInputNode(Node):
    """!
    Node with single input (without output)
    """
    def __init__(self, index):
        super().__init__(index)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.add_port(self.in_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        """Check if current Node is configured and parent is ready to run"""
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def run_upward(self):
        """Run single parent and check if succeeded"""
        if self.in_port.mother.parentItem().state != Node.SUCCESS:
            self.in_port.mother.parentItem().run()
        return self.in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        """Display help message about input Port datatype"""
        QMessageBox.information(None, 'Help',
                                'Input type: %s' % ', '.join(self.in_port.data_type),
                                QMessageBox.Ok)


class SingleOutputNode(Node):
    """!
    Node with single output (without input)
    """
    def __init__(self, index):
        super().__init__(index)
        self.out_port = OutputPort(0, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.out_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        """Check if current Node is configured"""
        return self.state != Node.NOT_CONFIGURED

    def run_downward(self):
        """Run current Node and ready to run descendants"""
        if not super().run_downward():
            return False
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().run_downward()
        return True

    def reconfigure(self):
        super().reconfigure()
        self.reconfigure_downward()

    def help(self):
        """Display help message about output Port datatype"""
        QMessageBox.information(None, 'Help',
                                'Output type: %s' % ', '.join(self.out_port.data_type),
                                QMessageBox.Ok)


class OneInOneOutNode(Node):
    """!
    Node with single input and single output
    """
    def __init__(self, index):
        super().__init__(index)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.out_port = OutputPort(1, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.in_port)
        self.add_port(self.out_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        """Check if current Node is configured and input is ready to run"""
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def run_downward(self):
        """Run current Node and ready to run descendants"""
        if not super().run_downward():
            return False
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().run_downward()
        return True

    def run_upward(self):
        """Run single parent and check if succeeded"""
        success = self.in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.in_port.mother.parentItem().state != Node.SUCCESS:
            self.in_port.mother.parentItem().run()
        return self.in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        """Display help message about input and output Ports datatype"""
        QMessageBox.information(None, 'Help',
                                'Input type: %s\n'
                                'Output type: %s' % (', '.join(self.in_port.data_type),
                                                     ', '.join(self.out_port.data_type)),
                                QMessageBox.Ok)


class TwoInOneOutNode(Node):
    """!
    Node with two inputs and single output
    """
    def __init__(self, index):
        super().__init__(index)

        ## First input Port
        self.first_in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/4-Port.WIDTH/2)
        ## Second input Port
        self.second_in_port = InputPort(1, -Port.WIDTH, 3*Box.HEIGHT/4-Port.WIDTH/2)
        ## Output Port
        self.out_port = OutputPort(2, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)

        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.add_port(self.out_port)
        self.proxy.setZValue(10)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        """Check if current Node is configured and inputs are ready to run"""
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.first_in_port.has_mother():
            return False
        if not self.second_in_port.has_mother():
            return False
        return self.first_in_port.mother.parentItem().ready_to_run() and\
               self.second_in_port.mother.parentItem().ready_to_run()

    def run_downward(self):
        """Run current Node and ready to run descendants"""
        if not super().run_downward():
            return False
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().run_downward()
        return True

    def run_upward(self):
        """Run parents and check if succeeded"""
        success = self.first_in_port.mother.parentItem().run_upward() and \
                  self.second_in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.first_in_port.mother.parentItem().state != Node.SUCCESS:
            self.first_in_port.mother.parentItem().run()
        if self.second_in_port.mother.parentItem().state != Node.SUCCESS:
            self.second_in_port.mother.parentItem().run()
        return self.first_in_port.mother.parentItem().state == Node.SUCCESS and \
               self.second_in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        """Display help message about inputs and output Ports datatype"""
        QMessageBox.information(None, 'Help',
                                'First input type: %s\n'
                                'Second input type: %s\n'
                                'Output type: %s' % (', '.join(self.first_in_port.data_type),
                                                     ', '.join(self.second_in_port.data_type),
                                                     ', '.join(self.out_port.data_type)),
                                QMessageBox.Ok)


class DoubleInputNode(Node):
    """!
    Node with two inputs (without output)
    """
    def __init__(self, index):
        super().__init__(index)
        self.first_in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/4-Port.WIDTH/2)
        self.second_in_port = InputPort(1, -Port.WIDTH, 3*Box.HEIGHT/4-Port.WIDTH/2)
        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.proxy.setZValue(10)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        """Check if current Node is configured and inputs are ready to run"""
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.first_in_port.has_mother():
            return False
        if not self.second_in_port.has_mother():
            return False
        return self.first_in_port.mother.parentItem().ready_to_run() and\
               self.second_in_port.mother.parentItem().ready_to_run()

    def run_upward(self):
        """Run parents and check if succeeded"""
        success = self.first_in_port.mother.parentItem().run_upward() and \
                  self.second_in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.first_in_port.mother.parentItem().state != Node.SUCCESS:
            self.first_in_port.mother.parentItem().run()
        if self.second_in_port.mother.parentItem().state != Node.SUCCESS:
            self.second_in_port.mother.parentItem().run()
        return self.first_in_port.mother.parentItem().state == Node.SUCCESS and \
               self.second_in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        """Display help message about inputs Ports datatype"""
        QMessageBox.information(None, 'Help',
                                'First input type: %s\n'
                                'Second input type: %s' % (', '.join(self.first_in_port.data_type),
                                                           ', '.join(self.second_in_port.data_type)),
                                QMessageBox.Ok)
