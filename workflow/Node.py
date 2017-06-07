from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class Port(QGraphicsRectItem):
    WIDTH = 20
    INPUT, OUTPUT = True, False
    COLOR = {OUTPUT: QColor(100, 120, 200, 255), INPUT: QColor(250, 230, 40, 255)}

    def __init__(self, index, x, y, port_type):
        super().__init__(x, y, Port.WIDTH, Port.WIDTH)
        self.index = index
        self.type = port_type
        self.data_type = ''
        self.setFlag(QGraphicsItem.ItemIsSelectable)

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


class Box(QGraphicsRectItem):
    WIDTH, HEIGHT = 80, 60

    def __init__(self):
        super().__init__(0, 0, Box.WIDTH, Box.HEIGHT)


class Node(QGraphicsItem):
    NOT_CONFIGURED, READY, SUCCESS, FAIL = 'Not configured', 'Ready', 'Success', 'Fail'
    COLOR = {NOT_CONFIGURED: QColor(220, 255, 255, 255), READY: QColor(250, 220, 165, 255),
             SUCCESS: QColor(180, 250, 165, 255), FAIL: QColor(255, 160, 160, 255)}

    def __init__(self, index, label):
        super().__init__()
        self.index = index
        self.box = Box()
        self.box.setParentItem(self)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.ArrowCursor)

        self.label = label
        self.state = Node.NOT_CONFIGURED

        self.nb_input = 0
        self.nb_output = 0
        self.ports = []
        self.links = set()

    def add_port(self, port):
        if port.type == Port.INPUT:
            self.nb_input += 1
        else:
            self.nb_output += 1
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
        return QRectF(pos.x()-Port.WIDTH, pos.y()-20, Box.WIDTH+Port.WIDTH, Box.HEIGHT+Port.WIDTH+20)

    def paint(self, painter, options, widget=None):
        painter.fillRect(self.box.rect(), Node.COLOR[self.state])
        painter.drawText(self.box.rect(), Qt.AlignCenter, self.label)
        painter.drawText(self.box.rect().topLeft()+QPointF(4, -3), self.state)

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


class SingleInputNode(Node):
    def __init__(self, index, label):
        super().__init__(index, label)
        self.in_port = Port(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2, Port.INPUT)
        self.add_port(self.in_port)


class SingleOutputNode(Node):
    def __init__(self, index, label):
        super().__init__(index, label)
        self.out_port = Port(0, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT, Port.OUTPUT)
        self.add_port(self.out_port)


