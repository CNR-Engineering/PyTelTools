from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import math
import os
from shapely.geometry import Polygon


class Port(QGraphicsRectItem):
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

    def __init__(self, index):
        super().__init__()
        self._index = index
        self.box = Box(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.proxy = QGraphicsProxyWidget(self)
        self.proxy.setWidget(self.progress_bar)
        self.proxy.setGeometry(QRectF(self.boundingRect().topLeft(), self.boundingRect().topRight()+QPointF(0, 30)))
        self.progress_bar.setVisible(False)

        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setCursor(Qt.ArrowCursor)

        self.help_action = QAction(QWidget().style().standardIcon(QStyle.SP_MessageBoxQuestion), 'Help', None)
        self.dashed_pen = QPen(Qt.black, 1, Qt.DashLine)

        self.label = ''
        self.category = ''

        self.state = Node.NOT_CONFIGURED
        self.message = ''

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

    def name(self):
        return ' '.join(self.label.split())

    def get_option_panel(self):
        return QWidget()

    def ready_to_run(self):
        pass

    def configure(self, check=None):
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

    def reconfigure_downward(self):
        for port in self.ports:
            if port.type == Port.OUTPUT:
                for child in port.children:
                    child.parentItem().reconfigure()

    def run_upward(self):
        return True

    def run_downward(self):
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
        return ''

    def load(self, options):
        pass

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
    def __init__(self, index):
        super().__init__(index)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.add_port(self.in_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def run_upward(self):
        if self.in_port.mother.parentItem().state != Node.SUCCESS:
            self.in_port.mother.parentItem().run()
        return self.in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        QMessageBox.information(None, 'Help',
                                'Input type: %s' % ', '.join(self.in_port.data_type),
                                QMessageBox.Ok)


class SingleOutputNode(Node):
    def __init__(self, index):
        super().__init__(index)
        self.out_port = OutputPort(0, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.out_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        return self.state != Node.NOT_CONFIGURED

    def run_downward(self):
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
        QMessageBox.information(None, 'Help',
                                'Output type: %s' % ', '.join(self.out_port.data_type),
                                QMessageBox.Ok)


class OneInOneOutNode(Node):
    def __init__(self, index):
        super().__init__(index)
        self.in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/2-Port.WIDTH/2)
        self.out_port = OutputPort(1, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.in_port)
        self.add_port(self.out_port)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.in_port.has_mother():
            return False
        return self.in_port.mother.parentItem().ready_to_run()

    def run_downward(self):
        if not super().run_downward():
            return False
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().run_downward()
        return True

    def run_upward(self):
        success = self.in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.in_port.mother.parentItem().state != Node.SUCCESS:
            self.in_port.mother.parentItem().run()
        return self.in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        QMessageBox.information(None, 'Help',
                                'Input type: %s\n'
                                'Output type: %s' % (', '.join(self.in_port.data_type),
                                                     ', '.join(self.out_port.data_type)),
                                QMessageBox.Ok)


class TwoInOneOutNode(Node):
    def __init__(self, index):
        super().__init__(index)
        self.first_in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/4-Port.WIDTH/2)
        self.second_in_port = InputPort(1, -Port.WIDTH, 3*Box.HEIGHT/4-Port.WIDTH/2)
        self.out_port = OutputPort(2, Box.WIDTH/2-Port.WIDTH/2, Box.HEIGHT)
        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.add_port(self.out_port)
        self.proxy.setZValue(10)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.first_in_port.has_mother():
            return False
        if not self.second_in_port.has_mother():
            return False
        return self.first_in_port.mother.parentItem().ready_to_run() and\
               self.second_in_port.mother.parentItem().ready_to_run()

    def run_downward(self):
        if not super().run_downward():
            return False
        if self.out_port.has_children():
            for child in self.out_port.children:
                child.parentItem().run_downward()
        return True

    def run_upward(self):
        success = self.first_in_port.mother.parentItem().run_upward() and \
                  self.second_in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.first_in_port.mother.parentItem().state != Node.SUCCESS:
            self.first_in_port.mother.parentItem().run()
        if self.second_in_port.mother.parentItem().state != Node.SUCCESS:
            self.second_in_port.mother.parentItem().run()
        return self.first_in_port.mother.parentItem().state == Node.SUCCESS and\
               self.second_in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        QMessageBox.information(None, 'Help',
                                'First input type: %s\n'
                                'Second input type: %s\n'
                                'Output type: %s' % (', '.join(self.first_in_port.data_type),
                                                     ', '.join(self.second_in_port.data_type),
                                                     ', '.join(self.out_port.data_type)),
                                QMessageBox.Ok)


class DoubleInputNode(Node):
    def __init__(self, index):
        super().__init__(index)
        self.first_in_port = InputPort(0, -Port.WIDTH, Box.HEIGHT/4-Port.WIDTH/2)
        self.second_in_port = InputPort(1, -Port.WIDTH, 3*Box.HEIGHT/4-Port.WIDTH/2)
        self.add_port(self.first_in_port)
        self.add_port(self.second_in_port)
        self.proxy.setZValue(10)
        self.help_action.triggered.connect(self.help)

    def ready_to_run(self):
        if self.state == Node.NOT_CONFIGURED:
            return False
        if not self.first_in_port.has_mother():
            return False
        if not self.second_in_port.has_mother():
            return False
        return self.first_in_port.mother.parentItem().ready_to_run() and\
               self.second_in_port.mother.parentItem().ready_to_run()

    def run_upward(self):
        success = self.first_in_port.mother.parentItem().run_upward() and \
                  self.second_in_port.mother.parentItem().run_upward()
        if not success:
            return False
        if self.first_in_port.mother.parentItem().state != Node.SUCCESS:
            self.first_in_port.mother.parentItem().run()
        if self.second_in_port.mother.parentItem().state != Node.SUCCESS:
            self.second_in_port.mother.parentItem().run()
        return self.first_in_port.mother.parentItem().state == Node.SUCCESS and\
               self.second_in_port.mother.parentItem().state == Node.SUCCESS

    def help(self):
        QMessageBox.information(None, 'Help',
                                'First input type: %s\n'
                                'Second input type: %s' % (', '.join(self.first_in_port.data_type),
                                                           ', '.join(self.second_in_port.data_type)),
                                QMessageBox.Ok)


class ConfigureDialog(QDialog):
    def __init__(self, panel, label, check=None):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        if check is None:
            self.check = None
            buttons.accepted.connect(self.accept)
        else:
            self.check = check
            buttons.accepted.connect(self.custom_accept)
        buttons.rejected.connect(self.reject)

        self.message_field = QPlainTextEdit()
        self.message_field.setFixedHeight(50)

        layout = QVBoxLayout()
        layout.addWidget(panel)
        layout.addStretch()
        layout.addWidget(self.message_field)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Configure %s' % label)
        self.resize(500, 400)

    def custom_accept(self):
        value = self.check()
        if value == 2:
            self.accept()
        elif value == 1:
            return
        else:
            self.reject()


class OutputOptionPanel(QWidget):
    def __init__(self, old_options):
        super().__init__()
        folder_box = QGroupBox('Select output folder')
        self.source_folder_button = QRadioButton('Input folder')
        self.another_folder_button = QRadioButton('Another folder')
        self.open_button = QPushButton('Open')
        self.open_button.setEnabled(False)
        self.folder_text = QLineEdit()
        self.folder_text.setReadOnly(True)
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.source_folder_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.another_folder_button)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.open_button)
        hlayout.addWidget(self.folder_text)
        vlayout.addLayout(hlayout)
        folder_box.setLayout(vlayout)
        self.source_folder_button.toggled.connect(self._toggle_folder)
        self.open_button.clicked.connect(self._open)

        name_box = QGroupBox('Select output name')
        self.suffix_box = QLineEdit()
        self.simple_name_button = QRadioButton('input_name + suffix')
        self.double_name_button = QRadioButton('input_name + job_id + suffix')
        self.simple_name_button.setChecked(True)
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Suffix'))
        hlayout.addWidget(self.suffix_box)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.simple_name_button)
        hlayout.addWidget(self.double_name_button)
        vlayout.addLayout(hlayout)
        name_box.setLayout(vlayout)

        overwrite_box = QGroupBox('Overwrite if file already exists')
        self.overwrite_button = QRadioButton('Yes')
        no_button = QRadioButton('No')
        no_button.setChecked(True)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.overwrite_button)
        hlayout.addWidget(no_button)
        overwrite_box.setLayout(hlayout)

        vlayout = QVBoxLayout()
        vlayout.addWidget(folder_box)
        vlayout.addWidget(name_box)
        vlayout.addWidget(overwrite_box)
        vlayout.addStretch()
        self.setLayout(vlayout)

        self.success = True
        self.suffix, self.in_source_folder, self.dir_path, self.double_name, self.overwrite = old_options
        self.suffix_box.setText(self.suffix)
        self.folder_text.setText(self.dir_path)
        if not self.in_source_folder:
            self.another_folder_button.setChecked(True)
        else:
            self.source_folder_button.setChecked(True)
        if self.double_name:
            self.double_name_button.setChecked(True)
        if self.overwrite:
            self.overwrite_button.setChecked(True)

    def _toggle_folder(self, source_folder):
        if not source_folder:
            self.double_name_button.setChecked(True)
            self.simple_name_button.setEnabled(False)
            self.open_button.setEnabled(True)
            self.success = False
        else:
            self.simple_name_button.setEnabled(True)
            self.folder_text.clear()
            self.success = True

    def _open(self):
        self.success = False
        w = QFileDialog()
        w.setWindowTitle('Choose the output folder')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            self.dir_path = os.path.join(current_dir, name)
            break
        if not self.dir_path:
            QMessageBox.critical(None, 'Error', 'Choose a folder !',
                                 QMessageBox.Ok)
            return
        self.folder_text.setText(self.dir_path)
        self.success = True

    def check(self):
        if not self.success:
            return 0
        suffix = self.suffix_box.text()
        if len(suffix) < 1:
            QMessageBox.critical(None, 'Error', 'The suffix cannot be empty!',
                                 QMessageBox.Ok)
            return 1
        if not all(c.isalnum() or c == '_' for c in suffix):
            QMessageBox.critical(None, 'Error', 'The suffix should only contain letters, numbers and underscores.',
                                 QMessageBox.Ok)
            return 1
        self.suffix = suffix
        self.in_source_folder = self.source_folder_button.isChecked()
        self.double_name = self.double_name_button.isChecked()
        self.overwrite = self.overwrite_button.isChecked()
        return 2

    def get_options(self):
        return self.suffix, self.in_source_folder, \
               self.dir_path, self.double_name, self.overwrite
