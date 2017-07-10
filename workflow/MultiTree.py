from copy import deepcopy

from workflow.MultiNode import Box, MultiLink
from workflow.multinodes_io import *
from workflow.multinodes_op import *


NODES = {'Input/Output': {'Load Serafin': MultiLoadSerafinNode, 'Write Serafin': MultiWriteSerafinNode},
         'Basic operations': {'Select Last Frame': MultiSelectLastFrameNode},
         'Operators': {'Max': MultiComputeMaxNode, 'Min': MultiComputeMinNode}}


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

    def add_node(self, node, pos):
        self.addItem(node)
        self.nodes[node.index()] = node
        self.nb_nodes += 1
        node.moveBy(pos.x(), pos.y())

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        target_item = self.itemAt(event.scenePos(), self.transform)
        if isinstance(target_item, Box):
            node = target_item.parentItem()
            if node.category == 'Input/Output' and node.name() == 'Load Serafin':
                success, options = node.configure(self.inputs[node.index()])
                if success:
                    self.inputs[node.index()] = options
                    downstream_nodes = visit(self.adj_list, node.index())
                    self.table.update_columns(node.index(), options[2], downstream_nodes)
                    QApplication.processEvents()

                    if all(self.inputs.values()):
                        self.ready_to_run = True

    def save(self, filename):
        links = []
        for item in self.items():
            if isinstance(item, MultiLink):
                links.append(item.save())

        with open(filename, 'w') as f:
            f.write('.'.join([self.language, self.csv_separator]) + '\n')
            f.write('%d %d\n' % (len(list(self.adj_list.keys())), len(links)))
            for node in self.nodes.values():
                f.write(node.save())
                f.write('\n')
            for link in links:
                f.write(link)
                f.write('\n')
            f.write('%d\n' % len(self.ordered_input_indices))
            for node_index in self.ordered_input_indices:
                paths, name, job_ids = self.inputs[node_index]
                nb_files = str(len(paths))
                line = [str(node_index), nb_files, name, '|'.join(paths), '|'.join(job_ids)]
                f.write('|'.join(line))
                f.write('\n')

    def load(self, filename):
        self.clear()
        self.ready_to_run = False
        self.inputs = {}
        self.nodes = {}
        self.adj_list = {}
        self.ordered_input_indices = []
        try:
            with open(filename, 'r') as f:
                self.language, self.csv_separator = f.readline().rstrip().split('.')
                nb_nodes, nb_links = map(int, f.readline().split())
                for i in range(nb_nodes):
                    line = f.readline().rstrip().split('|')
                    category, name, index, x, y = line[:5]
                    index = int(index)
                    node = NODES[category][name](index)
                    node.load(line[5:])
                    self.nodes[index] = node
                    self.addItem(node)
                    node.moveBy(float(x), float(y))
                    self.adj_list[index] = set()

                    if category == 'Input/Output' and name == 'Load Serafin':
                        self.inputs[index] = []
                        self.ordered_input_indices.append(index)

                for i in range(nb_links):
                    from_node_index, from_port_index, \
                                     to_node_index, to_port_index = map(int, f.readline().rstrip().split('|'))
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
                self.table.update_rows(self.nodes, ordered_nodes)
                QApplication.processEvents()

                next_line = f.readline()
                if next_line:
                    nb_inputs = int(next_line)
                    for i in range(nb_inputs):
                        line = f.readline().rstrip().split('|')
                        node_index = int(line[0])
                        nb_files = int(line[1])
                        slf_name = line[2]
                        paths = line[3:3+nb_files]
                        job_ids = line[3+nb_files:]
                        self.inputs[node_index] = [paths, slf_name, job_ids]
                        downstream_nodes = visit(self.adj_list, node_index)
                        self.table.update_files(job_ids, downstream_nodes)
                        self.nodes[node_index].state = MultiNode.READY
                    self.update()
                    self.ready_to_run = True
                    QApplication.processEvents()

        except (IndexError, ValueError, KeyError):
            QMessageBox.critical(None, 'Error',
                                 'The workspace file is not valid.',
                                 QMessageBox.Ok)


