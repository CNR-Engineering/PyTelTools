import logging
import sys
from time import time

from pyteltools.conf import settings

from .Node import Box, Link, Port
from .nodes_calc import *
from .nodes_io import *
from .nodes_op import *
from .nodes_vis import *
from .util import logger


NODES = {'Input/Output': {'Load Serafin 2D': LoadSerafin2DNode, 'Load Serafin 3D': LoadSerafin3DNode,
                          'Load Reference Serafin': LoadReferenceSerafinNode,
                          'Load 2D Points': LoadPoint2DNode, 'Load 2D Open Polylines': LoadOpenPolyline2DNode,
                          'Load 2D Polygons': LoadPolygon2DNode,
                          'Write LandXML': WriteLandXMLNode, 'Write shp': WriteShpNode, 'Write vtk': WriteVtkNode,
                          'Write Serafin': WriteSerafinNode},
         'Basic operations': {'Select Variables': SelectVariablesNode,
                              'Select Time': SelectTimeNode, 'Select Single Frame': SelectSingleFrameNode,
                              'Select First Frame': SelectFirstFrameNode, 'Select Last Frame': SelectLastFrameNode,
                              'Select Single Layer': SelectSingleLayerNode,
                              'Vertical Aggregation': VerticalAggregationNode,
                              'Add Rouse Numbers': AddRouseNode,
                              'Convert to Single Precision': ConvertToSinglePrecisionNode,
                              'Add Transformation': AddTransformationNode},
         'Operators': {'Max': ComputeMaxNode, 'Min': ComputeMinNode, 'Mean': ComputeMeanNode, 'SynchMax': SynchMaxNode,
                       'Project B on A': ProjectMeshNode, 'A Minus B': MinusNode, 'B Minus A': ReverseMinusNode,
                       'Max(A,B)': MaxBetweenNode, 'Min(A,B)': MinBetweenNode},
         'Calculations': {'Compute Arrival Duration': ArrivalDurationNode,
                          'Compute Volume': ComputeVolumeNode, 'Compute Flux': ComputeFluxNode,
                          'Interpolate on Points': InterpolateOnPointsNode,
                          'Interpolate along Lines': InterpolateAlongLinesNode,
                          'Project Lines': ProjectLinesNode},
         'Visualization': {'Show Mesh': ShowMeshNode, 'Visualize Scalars': VisualizeScalarValuesNode,
                           'Visualize Vectors': VisualizeVectorValuesNode,
                           'Locate Open Lines': LocateOpenLinesNode, 'Locate Polygons': LocatePolygonsNode,
                           'Locate Points': LocatePointsNode,
                           'Volume Plot': VolumePlotNode, 'Flux Plot': FluxPlotNode, 'Point Plot': PointPlotNode,
                           'Point Attribute Table': PointAttributeTableNode, 'MultiVar Line Plot': MultiVarLinePlotNode,
                           'MultiFrame Line Plot': MultiFrameLinePlotNode, 'Project Lines Plot': ProjectLinesPlotNode,
                           'Vertical Cross Section': VerticalCrossSectionNode,
                           'Vertical Temporal Profile 3D': VerticalTemporalProfileNode}}


def add_link(from_port, to_port):
    if to_port.is_connected_to(from_port) and from_port.is_connected_to(to_port):
        return False, 'already'
    if to_port.has_mother():
        return False, 'another'
    intersection = [u for u in from_port.data_type if u in to_port.data_type]
    if not intersection:
        return False, 'type'
    from_port.connect(to_port)
    to_port.connect(from_port)
    return True, ''


def count_cc(nodes, adj_list):
    """returns the number of CC and the CC as a map(node, label)"""
    labels = {}
    current_label = 0
    for node in nodes:
        labels[node] = -1

    def label_connected_component(labels, start_node, current_label):
        labels[start_node] = current_label
        for neighbor in adj_list[start_node]:
            if labels[neighbor] == -1:
                labels = label_connected_component(labels, neighbor, current_label)
        return labels

    for node in nodes:
        if labels[node] == -1:
            labels = label_connected_component(labels, node, current_label)
            current_label += 1
    return current_label, labels


class MonoScene(QGraphicsScene):
    def __init__(self):
        super().__init__()

        self.language = settings.LANG
        self.csv_separator = settings.CSV_SEPARATOR
        self.fmt_float = settings.FMT_FLOAT

        self._init_with_default_node()

        self.setSceneRect(QRectF(0, 0, settings.SCENE_SIZE[0], settings.SCENE_SIZE[1]))
        self.transform = QTransform()
        self.selectionChanged.connect(self.selection_changed)

    def reinit(self):
        self.clear()
        self._init_with_default_node()
        self.update()

    def _init_without_node(self):
        self.nodes = {}
        self.nb_nodes = 0
        self.adj_list = {}

    def _init_with_default_node(self):
        self._init_without_node()
        self.add_node(LoadSerafin2DNode(0), 50, 50)
        self._add_current_line()

    def _add_current_line(self):
        self.current_line = QGraphicsLineItem()
        self.addItem(self.current_line)
        self.current_line.setVisible(False)
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        self.current_line.setPen(pen)
        self.current_port = None

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            selected = self.selectedItems()
            if selected:
                link = selected[0]
                self._handle_remove_link(link)

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

    def add_node(self, node, x, y):
        logger.debug('Add node #%i %s' % (node.index(), node.label.replace('\n', ' ')))
        self.addItem(node)
        self.nodes[node.index()] = node
        self.adj_list[node.index()] = set()
        self.nb_nodes += 1
        node.moveBy(x, y)

    def save(self):
        links = []
        for item in self.items():
            if isinstance(item, Link):
                links.append(item.save())

        yield '.'.join([self.language, self.csv_separator])
        yield '%d %d' % (self.nb_nodes, len(links))
        for node in self.nodes.values():
            yield node.save()

        for link in links:
            yield link

    def load(self, filename):
        logger.debug('Loading project in MONO: %s' % filename)
        self.project_path = filename
        self.clear()
        self._add_current_line()
        self._init_without_node()
        try:
            with open(filename, 'r') as f:
                self.language, self.csv_separator = f.readline().rstrip().split('.')
                nb_nodes, nb_links = map(int, f.readline().split())
                for i in range(nb_nodes):
                    line = f.readline().rstrip().split('|')
                    category, name, index, x, y = line[:5]
                    node = NODES[category][name](int(index))
                    node.load(line[5:])
                    self.add_node(node, float(x), float(y))

                for i in range(nb_links):
                    from_node_index, from_port_index, \
                                     to_node_index, to_port_index = map(int, f.readline().rstrip().split('|'))
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
                    self.adj_list[from_node_index].add(to_node_index)
                    self.adj_list[to_node_index].add(from_node_index)

            self.update()
            return True
        except (IndexError, ValueError, KeyError) as e:
            logger.exception(e)
            logger.error("An exception occured while loading project in MONO.")
            self.reinit()
            return False

    def run_all(self):
        roots = self._to_sources()

        for root in roots:
            self.nodes[root].run_downward()

    def global_config(self):
        dlg = GlobalConfigDialog(self.language, self.csv_separator)
        value = dlg.exec_()
        if value == QDialog.Accepted:
            self.language, self.csv_separator = dlg.new_options

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
            self.adj_list[from_node.index()].add(to_node.index())
            self.adj_list[to_node.index()].add(from_node.index())
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
        from_index, to_index = target_item.from_port.parentItem().index(), target_item.to_port.parentItem().index()
        self.adj_list[from_index].remove(to_index)
        self.adj_list[to_index].remove(from_index)
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

        self.adj_list = {node: set() for node in self.nodes}
        for item in self.items():
            if isinstance(item, Link):
                from_index, to_index = item.from_port.parentItem().index(), item.to_port.parentItem().index()
                self.adj_list[from_index].add(to_index)
                self.adj_list[to_index].add(from_index)

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

    def suffix_pool(self):
        suffix = []
        for node in self.nodes.values():
            if hasattr(node, 'suffix'):
                suffix.append(node.suffix)
        return suffix

    def not_connected(self):
        nb_cc, labels = count_cc(list(self.adj_list.keys()), self.adj_list)
        return nb_cc > 1


class GlobalConfigDialog(QDialog):
    def __init__(self, language, csv_separator):
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

        layout = QVBoxLayout()
        layout.addWidget(self.lang_box)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('CSV separator'))
        hlayout.addWidget(self.csv_box, Qt.AlignLeft)
        layout.addLayout(hlayout)
        layout.setSpacing(20)
        layout.addStretch()
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.setWindowTitle('Global configuration')
        self.resize(self.sizeHint())

    def _select(self):
        separator = {0: ';', 1: ',', 2: '\t'}[self.csv_box.currentIndex()]
        language = ['en', 'fr'][self.french_button.isChecked()]
        self.new_options = (language, separator)
        self.accept()


class MonoView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(MonoScene())
        self.parent = parent
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setAcceptDrops(True)
        self.current_node = None
        self.centerOn(QPoint(400, 300))

    def dropEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            try:
                category, label = event.mimeData().text().split('|')
            except ValueError:
                event.ignore()
                return
            node = NODES[category][label](self.scene().nb_nodes)
            pos = self.mapToScene(event.pos())
            self.scene().add_node(node, pos.x(), pos.y())
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def select_node(self, node):
        self.current_node = node
        self.parent.enable_toolbar()

    def deselect_node(self):
        self.current_node = None
        self.parent.disable_toolbar()


class MonoPanel(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.view = MonoView(self)

        self.toolbar = QToolBar()
        self.node_label = QLineEdit()
        self.save_act = QAction('Save\n(Ctrl+S)', self, triggered=self.save, shortcut='Ctrl+S')
        self.run_all_act = QAction('Run all\n(F5)', self, triggered=self.run_all, shortcut='F5')
        self.configure_act = QAction('Configure\n(Ctrl+C)', self, triggered=self.configure_node,
                                     enabled=False, shortcut='Ctrl+C')
        self.delete_act = QAction('Delete\n(Del)', self, triggered=self.delete_node, enabled=False, shortcut='Del')
        self.run_act = QAction('Run\n(Ctrl+R)', self, triggered=self.run_node, enabled=False, shortcut='Ctrl+R')
        self.init_toolbar()

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def init_toolbar(self):
        for act in [self.save_act, self.run_all_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)
            self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel('   Selected node  '))
        self.toolbar.addWidget(self.node_label)
        self.node_label.setFixedWidth(150)
        self.node_label.setReadOnly(True)
        self.toolbar.addSeparator()
        for act in [self.configure_act, self.run_act, self.delete_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)

    def save(self):
        if not self.parent.save():
            QMessageBox.critical(None, 'Error', 'You have duplicated suffix.', QMessageBox.Ok)
        else:
            QMessageBox.information(None, 'Success', 'Project saved.', QMessageBox.Ok)

    def run_all(self):
        logger.debug('Start running project')
        start_time = time()
        self.view.scene().run_all()
        self.view.scene().update()
        logger.debug('Execution time %f s' % (time() - start_time))

    def configure_node(self):
        self.view.current_node.configure()
        if self.view.current_node.ready_to_run():
            self.run_act.setEnabled(True)
        self.view.scene().update()

    def delete_node(self):
        self.view.scene().handle_remove_node(self.view.current_node)
        self.view.deselect_node()
        self.view.scene().update()

    def run_node(self):
        self.view.current_node.run()
        self.view.scene().update()

    def enable_toolbar(self):
        self.node_label.setText(self.view.current_node.label)
        for act in [self.configure_act, self.delete_act]:
            act.setEnabled(True)
        if self.view.current_node.ready_to_run():
            self.run_act.setEnabled(True)
        else:
            self.run_act.setEnabled(False)

    def disable_toolbar(self):
        self.node_label.clear()
        for act in [self.configure_act, self.run_act, self.delete_act]:
            act.setEnabled(False)


class NodeTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        for category in NODES:
            node = QTreeWidgetItem(self, [category])
            node.setExpanded(True)
            for node_text in NODES[category]:
                node.addChild(QTreeWidgetItem([node_text]))

        self.setDragEnabled(True)
        self.setColumnCount(1)
        self.setHeaderLabel('Add Nodes')

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        current_item = self.currentItem()
        if current_item is None:
            return
        if current_item.parent() is not None:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText('|'.join([self.currentItem().parent().text(0), self.currentItem().text(0)]))
            drag.setMimeData(mime_data)
            drag.exec(Qt.MoveAction | Qt.CopyAction)


class MonoWidget(QWidget):
    def __init__(self, parent=None, project_path=None):
        super().__init__()
        mono = MonoPanel(parent)
        node_list = NodeTree()
        self.scene = mono.view.scene()

        left_panel = QWidget()
        config_button = QPushButton('Global\nConfiguration')
        config_button.setMinimumHeight(40)
        config_button.clicked.connect(self.scene.global_config)

        vlayout = QVBoxLayout()
        vlayout.addWidget(config_button)
        vlayout.addWidget(node_list)
        vlayout.setContentsMargins(0, 0, 0, 0)
        left_panel.setLayout(vlayout)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(mono)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(1, 1)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        if project_path is not None:
            self.scene.load(project_path)
            start_time = time()
            self.scene.run_all()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--workspace', help='workflow project file')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.parse_args()
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    QApp = QCoreApplication.instance()
    QApp = QApplication(sys.argv)
    cmd = MonoWidget(project_path=args.workspace)
