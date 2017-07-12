from copy import deepcopy

from workflow.MultiNode import Box, MultiLink
from workflow.multinodes_io import *
from workflow.multinodes_op import *
from workflow.multinodes_calc import *


NODES = {'Input/Output': {'Load Serafin': MultiLoadSerafinNode, 'Write Serafin': MultiWriteSerafinNode,
                          'Load 2D Polygons': MultiLoadPolygon2DNode,
                          'Load 2D Open Polylines': MultiLoadOpenPolyline2DNode,
                          'Load 2D Points': MultiLoadPoint2DNode},
         'Basic operations': {'Convert to Single Precision': MultiConvertToSinglePrecisionNode,
                              'Select First Frame': MultiSelectFirstFrameNode,
                              'Select Last Frame': MultiSelectLastFrameNode},
         'Operators': {'Max': MultiComputeMaxNode, 'Min': MultiComputeMinNode, 'Mean': MultiComputeMeanNode},
         'Calculations': {'Compute Volume': MultiComputeVolumeNode, 'Compute Flux': MultiComputeFluxNode,
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


class MultiTreeScene(QGraphicsScene):
    def __init__(self, table):
        super().__init__()
        self.table = table

        self.language = 'fr'
        self.csv_separator = ';'

        self.setSceneRect(QRectF(0, 0, 800, 600))
        self.transform = QTransform()

        self.nodes = {0: MultiLoadSerafinNode(0)}
        self.nodes[0].moveBy(50, 50)

        self.ready_to_run = False
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

        self.ready_to_run = False
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
        if not self.ready_to_run:
            return
        yield str(len(self.ordered_input_indices))
        for node_index in self.ordered_input_indices:
            paths, name, job_ids = self.inputs[node_index]
            nb_files = str(len(paths))
            line = [str(node_index), nb_files, name, '|'.join(paths), '|'.join(job_ids)]
            yield '|'.join(line)

    def load(self, filename):
        self.clear()
        self.ready_to_run = False
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
                    self.ready_to_run = True
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
            self.nodes[u].update_input(len(job_ids))

        if all(self.inputs.values()):
            self.ready_to_run = True

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
