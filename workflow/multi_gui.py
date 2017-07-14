from copy import deepcopy
import workflow.multi_func as worker
from workflow.MultiNode import Box, MultiLink
from workflow.multi_nodes import *


NODES = {'Input/Output': {'Load Serafin': MultiLoadSerafinNode, 'Write Serafin': MultiWriteSerafinNode,
                          'Load 2D Polygons': MultiLoadPolygon2DNode,
                          'Load 2D Open Polylines': MultiLoadOpenPolyline2DNode,
                          'Load 2D Points': MultiLoadPoint2DNode},
         'Basic operations': {'Select Variables': MultiSelectVariablesNode, 'Add Rouse': MultiAddRouseNode,
                              'Convert to Single Precision': MultiConvertToSinglePrecisionNode,
                              'Select First Frame': MultiSelectFirstFrameNode,
                              'Select Last Frame': MultiSelectLastFrameNode, 'Select Time': MultiSelectTimeNode,
                              'Select Single Frame': MultiSelectSingleFrameNode},
         'Operators': {'Max': MultiComputeMaxNode, 'Min': MultiComputeMinNode, 'Mean': MultiComputeMeanNode},
         'Calculations': {'Compute Arrival Duration': MultiArrivalDurationNode,
                          'Compute Volume': MultiComputeVolumeNode, 'Compute Flux': MultiComputeFluxNode,
                          'Interpolate on Points': MultiInterpolateOnPointsNode,
                          'Interpolate along Lines': MultiInterpolateAlongLinesNode,
                          'Project Lines': MultiProjectLinesNode}}


def topological_ordering(graph):
    """!
    topological ordering of DAG (adjacency list)
    """
    copy_graph = deepcopy(graph)
    ordered = []
    candidates = graph.keys()
    remove_list = []
    for k in graph.keys():
        for c in candidates:
            if c in graph[k]:
                remove_list.append(c)
    candidates = [c for c in candidates if c not in remove_list]
    while len(candidates) != 0:
        ordered.append(candidates.pop())
        a = ordered[-1]
        if a in copy_graph:
            for t in copy_graph[a].copy():
                copy_graph[a].remove(t)
                is_candidate = True
                for b in copy_graph:
                    if t in copy_graph[b]:
                        is_candidate = False
                        break
                if is_candidate:
                    candidates.append(t)
    return ordered


def visit(graph, from_node):
    """!
    all reachable nodes from a given node in a graph (adjacency list including sink nodes)
    """
    stack = [from_node]
    visited = {node: False for node in graph.keys()}
    while stack:
        u = stack.pop()
        if not visited[u]:
            visited[u] = True
            for v in graph[u]:
                stack.append(v)
    return [u for u in graph.keys() if visited[u]]


class MultiScene(QGraphicsScene):
    def __init__(self, table):
        super().__init__()
        self.table = table

        self.language = 'fr'
        self.csv_separator = ';'

        self.setSceneRect(QRectF(0, 0, 800, 600))
        self.transform = QTransform()

        self.nodes = {0: MultiLoadSerafinNode(0)}
        self.nodes[0].moveBy(50, 50)

        self.has_input = False
        self.inputs = {0: []}
        self.ordered_input_indices = [0]
        self.adj_list = {0: set()}

        for node in self.nodes.values():
            self.addItem(node)

        self.auxiliary_input_nodes = []

    def reinit(self):
        self.clear()
        self.nodes = {0: MultiLoadSerafinNode(0)}
        self.nodes[0].moveBy(50, 50)
        self.auxiliary_input_nodes = []

        self.has_input = False
        self.inputs = {0: []}
        self.ordered_input_indices = [0]
        self.adj_list = {0: set()}
        self.update()

    def add_node(self, node, x, y):
        self.addItem(node)
        self.nodes[node.index()] = node
        node.moveBy(x, y)
        self.adj_list[node.index()] = set()
        if node.category == 'Input/Output':
            if node.name() in ('Load 2D Polygons', 'Load 2D Open Polylines', 'Load 2D Points'):
                self.auxiliary_input_nodes.append(node.index())

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        target_item = self.itemAt(event.scenePos(), self.transform)
        if isinstance(target_item, Box):
            node = target_item.parentItem()
            if node.category == 'Input/Output' and node.name() == 'Load Serafin':
                self._handle_add_input(node)

    def save(self):
        if not self.has_input:
            return
        yield str(len(self.ordered_input_indices))
        for node_index in self.ordered_input_indices:
            paths, name, job_ids = self.inputs[node_index]
            nb_files = str(len(paths))
            line = [str(node_index), nb_files, name, '|'.join(paths), '|'.join(job_ids)]
            yield '|'.join(line)

    def load(self, filename):
        self.clear()
        self.has_input = False
        self.inputs = {}
        self.nodes = {}
        self.adj_list = {}
        self.ordered_input_indices = []
        self.auxiliary_input_nodes = []

        try:
            with open(filename, 'r') as f:
                self.language, self.csv_separator = f.readline().rstrip().split('.')
                nb_nodes, nb_links = map(int, f.readline().split())
                for i in range(nb_nodes):
                    line = f.readline().rstrip().split('|')
                    category, name, index, x, y = line[:5]
                    if category == 'Visualization':  # ignore all visualization nodes
                        continue

                    index = int(index)
                    node = NODES[category][name](index)
                    node.load(line[5:])
                    self.add_node(node, float(x), float(y))

                    if category == 'Input/Output' and name == 'Load Serafin':
                        self.inputs[index] = []
                        self.ordered_input_indices.append(index)

                for i in range(nb_links):
                    from_node_index, from_port_index, \
                                     to_node_index, to_port_index = map(int, f.readline().rstrip().split('|'))

                    if to_node_index not in self.nodes:  # visualization nodes
                        continue
                    from_node = self.nodes[from_node_index]
                    to_node = self.nodes[to_node_index]
                    from_port = from_node.ports[from_port_index]
                    to_port = to_node.ports[to_port_index]

                    from_port.connect(to_port)
                    to_port.connect(from_port)
                    link = MultiLink(from_port, to_port)
                    link.setZValue(-1)
                    self.addItem(link)
                    self.adj_list[from_node_index].add(to_node_index)

                self.update()
                ordered_nodes = topological_ordering(self.adj_list)
                self.table.update_rows(self.nodes, [u for u in ordered_nodes if u not in self.auxiliary_input_nodes])
                QApplication.processEvents()

                next_line = f.readline()
                if next_line:
                    nb_inputs = int(next_line)
                    for i in range(nb_inputs):
                        line = f.readline()
                        split_line = line.rstrip().split('|')
                        node_index = int(split_line[0])
                        nb_files = int(split_line[1])
                        slf_name = split_line[2]
                        paths = split_line[3:3+nb_files]
                        job_ids = split_line[3+nb_files:]
                        self.inputs[node_index] = [paths, slf_name, job_ids]
                        downstream_nodes = visit(self.adj_list, node_index)
                        self.table.add_files(node_index, job_ids, downstream_nodes)
                        self.nodes[node_index].state = MultiNode.READY
                        for u in downstream_nodes:
                            self.nodes[u].update_input(len(job_ids))

                    self.update()
                    self.has_input = True
                    QApplication.processEvents()

            return True
        except (IndexError, ValueError, KeyError):
            self.reinit()
            self.table.reinit()
            return False

    def _handle_add_input(self, node):
        success, options = node.configure(self.inputs[node.index()])
        if not success:
            return

        self.inputs[node.index()] = options
        job_ids = options[2]
        downstream_nodes = visit(self.adj_list, node.index())
        if node.index() not in self.table.input_columns:
            self.table.add_files(node.index(), job_ids, downstream_nodes)
        else:
            self.table.update_files(node.index(), job_ids)
        QApplication.processEvents()

        for u in downstream_nodes:
            u_node = self.nodes[u]
            u_node.update_input(len(job_ids))
            if u_node.state != MultiNode.NOT_CONFIGURED:
                u_node.state = MultiNode.READY

        if all(self.inputs.values()):
            self.has_input = True

    def all_configured(self):
        for node in self.nodes.values():
            if node.state == MultiNode.NOT_CONFIGURED:
                return False
        return True

    def prepare_to_run(self):
        for node in self.nodes.values():
            node.state = MultiNode.READY
            node.nb_success = 0
            node.nb_fail = 0
        self.update()


class MultiView(QGraphicsView):
    def __init__(self, parent, table):
        super().__init__(MultiScene(table))
        self.parent = parent
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setAcceptDrops(True)
        self.current_node = None

    def resizeEvent(self, event):
        self.scene().setSceneRect(QRectF(0, 0, self.width()-10, self.height()-10))


class MultiTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.yellow = QColor(245, 255, 207, 255)
        self.green = QColor(180, 250, 165, 255)
        self.grey = QColor(211, 211, 211, 255)
        self.red = QColor(255, 160, 160, 255)

        self.setRowCount(1)
        self.setColumnCount(0)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalHeaderLabels(['Load Serafin'])

        self.row_to_node = {}
        self.node_to_row = {}
        self.input_columns = {}
        self.yellow_nodes = {}

    def reinit(self):
        self.setRowCount(1)
        self.setVerticalHeaderLabels(['Load Serafin'])
        self.setColumnCount(0)
        self.input_columns = {}
        self.yellow_nodes = {}

    def update_rows(self, nodes, ordered_nodes):
        self.row_to_node = {i: ordered_nodes[i] for i in range(len(ordered_nodes))}
        self.node_to_row = {ordered_nodes[i]: i for i in range(len(ordered_nodes))}
        self.setRowCount(len(ordered_nodes))
        self.setColumnCount(0)
        self.setVerticalHeaderLabels([nodes[u].name() for u in ordered_nodes])
        self.input_columns = {}
        self.yellow_nodes = {}

    def add_files(self, node_index, new_ids, downstream_nodes):
        self.input_columns[node_index] = []
        self.yellow_nodes[node_index] = downstream_nodes
        offset = self.columnCount()
        self.setColumnCount(offset + len(new_ids))

        new_labels = []
        for j in range(offset):
            new_labels.append(self.horizontalHeaderItem(j).text())
        new_labels.extend(new_ids)
        self.setHorizontalHeaderLabels(new_labels)

        for j in range(len(new_ids)):
            self.input_columns[node_index].append(offset+j)
            for i in range(self.rowCount()):
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if self.row_to_node[i] in downstream_nodes:
                    self.item(i, offset+j).setBackground(self.yellow)
                else:
                    self.item(i, offset+j).setBackground(self.grey)

    def update_files(self, node_index, new_ids):
        new_labels = []
        old_input_nodes = [u for u in self.input_columns.keys() if u != node_index]
        old_input_nb = {}
        for input_node in old_input_nodes:
            old_input_nb[input_node] = len(self.input_columns[input_node])
            for j in self.input_columns[input_node]:
                new_labels.append(self.horizontalHeaderItem(j).text())

        new_labels.extend(new_ids)   # modified input nodes always at end of the table
        self.input_columns = {}  # all columns could be shuffled

        self.setColumnCount(len(new_labels))
        self.setHorizontalHeaderLabels(new_labels)

        # rebuild the whole table
        offset = 0
        for input_node in old_input_nodes:
            self.input_columns[input_node] = []
            for j in range(old_input_nb[input_node]):
                self.input_columns[input_node].append(offset+j)
                for i in range(self.rowCount()):
                    item = QTableWidgetItem()
                    self.setItem(i, offset+j, item)
                    if i in self.yellow_nodes[input_node]:
                        self.item(i, offset+j).setBackground(self.yellow)
                    else:
                        self.item(i, offset+j).setBackground(self.grey)
            offset += old_input_nb[input_node]
        self.input_columns[node_index] = []
        for j in range(len(new_ids)):
            self.input_columns[node_index].append(offset+j)
            for i in range(self.rowCount()):
                item = QTableWidgetItem()
                self.setItem(i, offset+j, item)
                if self.row_to_node[i] in self.yellow_nodes[node_index]:
                    self.item(i, offset+j).setBackground(self.yellow)
                else:
                    self.item(i, offset+j).setBackground(self.grey)

    def get_result(self, success, node_id, fid):
        if success:
            self.item(self.node_to_row[node_id], fid).setBackground(self.green)
        else:
            self.item(self.node_to_row[node_id], fid).setBackground(self.red)


class MultiWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.table = MultiTable()
        self.view = MultiView(self, self.table)
        self.scene = self.view.scene()

        self.toolbar = QToolBar()
        self.save_act = QAction('Save\n(Ctrl+S)', self, triggered=self.save, shortcut='Ctrl+S')
        self.run_act = QAction('Run\n(F5)', self, triggered=self.run, shortcut='F5')
        self.init_toolbar()

        self.message_box = QPlainTextEdit()
        self.message_box.setReadOnly(True)

        left_panel = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setLayout(layout)

        right_panel = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.message_box)
        layout.setContentsMargins(0, 0, 0, 0)
        right_panel.setLayout(layout)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(1, 1)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        self.worker = worker.Workers()

    def init_toolbar(self):
        for act in [self.save_act, self.run_act]:
            button = QToolButton(self)
            button.setFixedWidth(100)
            button.setMinimumHeight(30)
            button.setDefaultAction(act)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.toolbar.addWidget(button)
            self.toolbar.addSeparator()

    def save(self):
        if not self.scene.has_input:
            QMessageBox.critical(None, 'Error', 'Configure all input nodes before saving.', QMessageBox.Ok)
            return
        self.parent.save()
        QMessageBox.information(None, 'Success', 'Project saved.', QMessageBox.Ok)

    def run(self):
        if not self.scene.all_configured():
            QMessageBox.critical(None, 'Error', 'Configure all nodes first!', QMessageBox.Ok)
            return

        self.scene.prepare_to_run()
        self.setEnabled(False)
        csv_separator = self.scene.csv_separator

        # first get auxiliary tasks done
        success = self._prepare_auxiliary_tasks()
        if not success:
            self.worker.stop()
            self.message_box.appendPlainText('Done!')
            self.setEnabled(True)
            self.worker = worker.Workers()
            return

        # prepare slf input tasks
        nb_tasks = self._prepare_input_tasks()

        while not self.worker.stopped:
            nb_tasks = self._listen(nb_tasks, csv_separator)
            if nb_tasks == 0:
                self.worker.stop()

        self.message_box.appendPlainText('Done!')
        self.setEnabled(True)
        self.worker = worker.Workers()

    def _prepare_auxiliary_tasks(self):
        # auxiliary input tasks for N-1 type of double input nodes
        aux_tasks = []
        for node_id in self.scene.auxiliary_input_nodes:
            fun = worker.FUNCTIONS[self.scene.nodes[node_id].name()]
            aux_tasks.append((fun, (node_id, self.scene.nodes[node_id].options[0])))

        all_success = True
        if aux_tasks:
            self.worker.add_tasks(aux_tasks)
            self.worker.start()
            for i in range(len(aux_tasks)):
                success, node_id, data, message = self.worker.done_queue.get()
                self.message_box.appendPlainText(message)

                if not success:
                    self.scene.nodes[node_id].state = MultiNode.FAIL
                    all_success = False
                    continue

                self.scene.nodes[node_id].state = MultiNode.SUCCESS
                # using the fact that auxiliary input nodes are always directly connected to double input nodes
                next_nodes = self.scene.adj_list[node_id]
                for next_node_id in next_nodes:
                    next_node = self.scene.nodes[next_node_id]
                    next_node.set_auxiliary_data(data)
        return all_success

    def _prepare_input_tasks(self):
        slf_tasks = []
        for node_id in self.scene.ordered_input_indices:
            paths, name, job_ids = self.view.scene().inputs[node_id]
            for path, job_id, fid in zip(paths, job_ids, self.table.input_columns[node_id]):
                slf_tasks.append((worker.read_slf, (node_id, fid, os.path.join(path, name),
                                                    self.scene.language, job_id)))
        self.worker.add_tasks(slf_tasks)
        if not self.worker.started:
            self.worker.start()
        return len(slf_tasks)

    def _listen(self, nb_tasks, csv_separator):
        # get one task result
        success, node_id, fid, data, message = self.worker.done_queue.get()
        nb_tasks -= 1
        self.message_box.appendPlainText(message)
        current_node = self.scene.nodes[node_id]
        self.table.get_result(success, node_id, fid)

        # enqueue tasks from child nodes
        if success:
            current_node.nb_success += 1

            next_nodes = self.scene.adj_list[node_id]
            for next_node_id in next_nodes:
                next_node = self.scene.nodes[next_node_id]
                fun = worker.FUNCTIONS[next_node.name()]
                if next_node.double_input:
                    self.worker.task_queue.put((fun, (next_node_id, fid, data, next_node.auxiliary_data,
                                                      next_node.options, csv_separator)))
                else:
                    self.worker.task_queue.put((fun, (next_node_id, fid, data, next_node.options)))
                nb_tasks += 1
        else:
            current_node.nb_fail += 1

        # change box color
        if current_node.nb_success + current_node.nb_fail == current_node.nb_files():
            if current_node.nb_fail == 0:
                current_node.state = MultiNode.SUCCESS
            elif current_node.nb_success == 0:
                current_node.state = MultiNode.FAIL
            else:
                current_node.state = MultiNode.PARTIAL_FAIL
            current_node.update()
        QApplication.processEvents()

        return nb_tasks

