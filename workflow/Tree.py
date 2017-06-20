from workflow.Node import Port, Box
from workflow.Link import Link
from workflow.nodes_io import *
from workflow.nodes_op import *
from workflow.nodes_calc import *


NODES = {'Input/Output': {'Load Serafin': LoadSerafinNode,
                          'Load 2D Polygons': LoadPolygon2DNode, 'Load 2D Open Polylines': LoadOpenPolyline2DNode,
                          'Load 2D Points': LoadPoint2DNode,
                          'Write CSV': WriteCSVNode, 'Write Serafin': WriteSerafinNode},
         'Basic operations': {'Select Variables': SelectVariablesNode, 'Select Time': SelectTimeNode,
                              'Add Rouse': AddRouseNode, 'Convert to Single Precision': ConvertToSinglePrecisionNode},
         'Calculations': {'Compute Max': ComputeMaxNode, 'Compute Min': ComputeMinNode, 'Compute Mean': ComputeMeanNode,
                          'Compute Arrival Duration': ArrivalDurationNode,
                          'Compute Volume': ComputeVolumeNode, 'Compute Flux': ComputeFluxNode,
                          'Interpolate on Points': InterpolateOnPoints}}


def add_link(from_port, to_port):
    if to_port.is_connected_to(from_port) and from_port.is_connected_to(to_port):
        return False, 'already'
    if to_port.has_mother():
        return False, 'another'
    if to_port.data_type != 'all' and from_port.data_type != 'all':
        if to_port.data_type != from_port.data_type:
            return False, 'type'
    from_port.connect(to_port)
    to_port.connect(from_port)
    return True, ''


class TreeScene(QGraphicsScene):
    def __init__(self):
        super().__init__()

        self.language = 'fr'
        self.csv_separator = ';'
        self.name_pattern = None

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

    def save(self, filename):
        links = []
        for item in self.items():
            if isinstance(item, Link):
                links.append(item.save())

        with open(filename, 'w') as f:
            f.write('.'.join([self.language, self.csv_separator, str(self.name_pattern)]) + '\n')
            f.write('%d %d\n' % (self.nb_nodes, len(links)))
            for node in self.nodes.values():
                f.write(node.save())
                f.write('\n')
            for link in links:
                f.write(link)
                f.write('\n')

    def load(self, filename):
        self.clear()
        self.current_line = QGraphicsLineItem()
        self.addItem(self.current_line)
        self.current_line.setVisible(False)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        self.current_line.setPen(pen)
        self.current_port = None

        self.nb_nodes = 0
        self.nodes = {}
        try:
            with open(filename, 'r') as f:
                self.language, self.csv_separator, self.name_pattern = f.readline().rstrip().split('.')
                if self.name_pattern == 'None':
                    self.name_pattern = None
                nb_nodes, nb_links = map(int, f.readline().split())
                for i in range(nb_nodes):
                    line = f.readline().rstrip().split('|')
                    category, name, index, x, y = line[:5]
                    node = NODES[category][name](int(index))
                    node.load(line[5:])
                    self.nodes[int(index)] = node
                    self.addItem(node)
                    node.moveBy(float(x), float(y))
                    self.nb_nodes += 1
                for i in range(nb_links):
                    from_node_index, from_port_index, \
                                     to_node_index, to_port_index = map(int,  f.readline().rstrip().split('|'))
                    from_node = self.nodes[from_node_index]
                    to_node = self.nodes[to_node_index]
                    from_port = from_node.ports[from_port_index]
                    to_port = to_node.ports[to_port_index]
                    _, _ = add_link(from_port, to_port)
                    link = Link(from_port, to_port)
                    from_node.add_link(link)
                    to_node.add_link(link)
                    self.addItem(link)
                    link.setZValue(-1)
        except (IndexError, ValueError, KeyError):
            QMessageBox.critical(None, 'Error',
                                 'The workspace file is not valid.',
                                 QMessageBox.Ok)
        self.update()

    def run_all(self):
        roots = self._to_sources()

        for root in roots:
            self.nodes[root].run_downward()

    def global_config(self):
        old_name_pattern = self.name_pattern
        dlg = GlobalConfigDialog(self.language, self.csv_separator, self.name_pattern)
        value = dlg.exec_()
        if value == QDialog.Accepted:
            self.language, self.csv_separator, self.name_pattern = dlg.new_options
            if self.name_pattern != old_name_pattern:
                for node in self.nodes.values():
                    if isinstance(node, SingleInputNode):
                        node.state = Node.NOT_CONFIGURED
                self.update()

    def _to_sources(self):
        roots = []
        visited = {node: False for node in self.nodes}

        def forward(node):
            for port in node.ports:
                if port.type == Port.OUTPUT:
                    if port.has_children():
                        for child in port.children:
                            child_node = child.parentItem()
                            if not visited[child_node.index()]:
                                visited[child_node.index()] = False
                                forward(child_node)

        def backward(node_index):
            if not visited[node_index]:
                visited[node_index] = True
                node = self.nodes[node_index]
                if node.ports[0].type == Port.INPUT:
                    backward(node.ports[0].parentItem().index())
                    if len(node.ports) > 1 and node.ports[1].type == Port.INPUT:
                        backward(node.ports[1].parentItem().index())
                else:
                    roots.append(node_index)
                    forward(node)

        for node in self.nodes:
            backward(node)

        return roots

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
            self.update()
        else:
            if cause == 'already':
                QMessageBox.critical(None, 'Error', 'These two ports are already connected.',
                                     QMessageBox.Ok)
            elif cause == 'type':
                QMessageBox.critical(None, 'Error', 'These two ports cannot be connected: incompatible data types.',
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


class GlobalConfigDialog(QDialog):
    def __init__(self, language, csv_separator, name_pattern):
        super().__init__()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self._select)
        buttons.rejected.connect(self.reject)
        self.new_options = tuple()

        self.lang_box = QGroupBox('Input Serafin language')
        hlayout = QHBoxLayout()
        self.french_button = QRadioButton('French')
        english_button = QRadioButton('English')
        hlayout.addWidget(self.french_button)
        hlayout.addWidget(english_button)
        self.lang_box.setLayout(hlayout)
        self.lang_box.setMaximumHeight(80)
        if language == 'fr':
            self.french_button.setChecked(True)
        else:
            english_button.setChecked(True)

        self.csv_box = QComboBox()
        self.csv_box.setFixedHeight(30)
        for sep in ['Semicolon ;', 'Comma ,', 'Tab']:
            self.csv_box.addItem(sep)
        if csv_separator == ';':
            self.csv_box.setCurrentIndex(0)
        elif csv_separator == ',':
            self.csv_box.setCurrentIndex(1)
        else:
            self.csv_box.setCurrentIndex(2)

        self.name_box = QGroupBox('Use naming pattern for output files')
        self.name_box.setCheckable(True)
        self.pattern = QLineEdit()
        self.pattern.setFixedHeight(30)
        if name_pattern is not None:
            self.pattern.setText(name_pattern)
        self.name_box.toggled.connect(self._toggle_name_pattern)

        if name_pattern is not None:
            self.name_box.setChecked(True)
        else:
            self.name_box.setChecked(False)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Append to input name'))
        hlayout.addWidget(self.pattern)
        self.name_box.setLayout(hlayout)

        layout = QVBoxLayout()
        layout.addWidget(self.lang_box)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('CSV separator'))
        hlayout.addWidget(self.csv_box, Qt.AlignLeft)
        layout.addLayout(hlayout)
        layout.addWidget(self.name_box)
        layout.setSpacing(20)
        layout.addStretch()
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Workspace global configuration')
        self.resize(self.sizeHint())

    def _toggle_name_pattern(self, checked):
        self.pattern.setEnabled(checked)
        if not checked:
            self.pattern.clear()
        elif not self.pattern.text():
            self.pattern.setText('_result')

    def _select(self):
        if self.name_box.isChecked():
            pattern = self.pattern.text()
            if not pattern:
                QMessageBox.critical(None, 'Error',
                                     'The naming pattern cannot be empty!',
                                     QMessageBox.Ok)
                return
            elif len(pattern.split()) > 1:
                QMessageBox.critical(None, 'Error',
                                     'The naming pattern should not contain spaces!',
                                     QMessageBox.Ok)
                return
            elif '.' in pattern:
                QMessageBox.critical(None, 'Error',
                                     'The naming pattern should not contain spaces!',
                                     QMessageBox.Ok)
                return
            else:
                splitted = pattern.split('_')
                for part in splitted:
                    if not part:
                        continue
                    if not part.isalnum():
                        QMessageBox.critical(None, 'Error',
                                             'The naming pattern should only contain letters, numbers and underscores.',
                                             QMessageBox.Ok)
                        return
        else:
            pattern = None

        separator = {0: ';', 1: ',', 2: '\t'}[self.csv_box.currentIndex()]
        language = ['en', 'fr'][self.french_button.isChecked()]
        self.new_options = (language, separator, pattern)
        self.accept()

