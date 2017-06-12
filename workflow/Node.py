from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class Port(QGraphicsRectItem):
    WIDTH = 20
    INPUT, OUTPUT = True, False
    COLOR = {OUTPUT: QColor(100, 120, 200, 255), INPUT: QColor(250, 230, 40, 255)}

    def __init__(self, index, x, y, port_type):
        super().__init__(x, y, Port.WIDTH, Port.WIDTH)
        self._index = index
        self.type = port_type
        self.data_type = ''
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
    NOT_CONFIGURED, READY, SUCCESS, FAIL = 'Not configured', 'Ready', 'Success', 'Fail'
    COLOR = {NOT_CONFIGURED: QColor(220, 255, 255, 255), READY: QColor(250, 220, 165, 255),
             SUCCESS: QColor(180, 250, 165, 255), FAIL: QColor(255, 160, 160, 255)}

    def __init__(self, index, label):
        super().__init__()
        self._index = index
        self.box = Box(self)

        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setCursor(Qt.ArrowCursor)
        self.dashed_pen = QPen(Qt.black, 1, Qt.DashLine)

        self.label = label
        self.state = Node.NOT_CONFIGURED

        self.ports = []
        self.links = set()

    def index(self):
        return self._index

    def set_index(self, index):
        self._index = index

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
        painter.drawText(self.box.rect(), Qt.AlignCenter, self.label)
        painter.drawText(self.box.rect().topLeft()+QPointF(4, -3), self.state)
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

    def ready_to_run(self):
        pass

    def configure(self):
        pass

    def run(self):
        pass

    def reconfigure(self):
        pass


class SingleInputNode(Node):
    def __init__(self, index, label):
        super().__init__(index, label)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.add_port(self.in_port)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def reconfigure(self):
        pass


class SingleOutputNode(Node):
    def __init__(self, index, label):
        super().__init__(index, label)
        self.out_port = OutputPort(0, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.out_port)

    def ready_to_run(self):
        return self.state != Node.NOT_CONFIGURED

    def reconfigure(self):
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().reconfigure()


class OneInOneOutNode(Node):
    def __init__(self, index, label):
        super().__init__(index, label)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.out_port = OutputPort(1, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.in_port)
        self.add_port(self.out_port)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def reconfigure(self):
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().reconfigure()


class ConfigureDialog(QDialog):
    def __init__(self, panel, label):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(panel)
        layout.addStretch()
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Configure %s' % label)
        self.resize(500, 400)

