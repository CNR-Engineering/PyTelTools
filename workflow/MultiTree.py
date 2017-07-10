from collections import defaultdict
from workflow.MultiNode import Box, MultiLink
from workflow.multinodes_io import *
from workflow.multinodes_op import *


NODES = {'Input/Output': {'Load Serafin': MultiLoadSerafinNode, 'Write Serafin': MultiWriteSerafinNode},
         'Basic operations': {'Select Last Frame': MultiSelectLastFrameNode},
         'Operators': {'Max': MultiComputeMaxNode}}


class MultiTreeScene(QGraphicsScene):
    def __init__(self):
        super().__init__()

        self.language = 'fr'
        self.csv_separator = ';'

        self.setSceneRect(QRectF(0, 0, 800, 600))
        self.transform = QTransform()

        self.nodes = {0: MultiLoadSerafinNode(0)}
        self.nodes[0].moveBy(50, 50)
        self.job_ids = []

        self.io_info = defaultdict(list)

        for node in self.nodes.values():
            self.addItem(node)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        target_item = self.itemAt(event.scenePos(), self.transform)
        if isinstance(target_item, Box):
            node = target_item.parentItem()
            if isinstance(node, MultiLoadSerafinNode):
                success, options = node.configure(self.io_info[node.index()])
                if success:
                    self.io_info[node.index()] = options
                    self.job_ids = options[2]
            elif isinstance(node, MultiWriteSerafinNode):
                success, options = node.configure()
                # self.io_info[node.index()] = node.configure()

    def add_node(self, node, pos):
        self.addItem(node)
        self.nodes[node.index()] = node
        self.nb_nodes += 1
        node.moveBy(pos.x(), pos.y())

    def save(self, filename):
        pass
        # links = []
        # for item in self.items():
        #     if isinstance(item, MultiLink):
        #         links.append(item.save())
        #
        # with open(filename, 'w') as f:
        #     f.write('.'.join([self.language, self.csv_separator]) + '\n')
        #     f.write('%d %d\n' % (self.nb_nodes, len(links)))
        #     for node in self.nodes.values():
        #         f.write(node.save())
        #         f.write('\n')
        #     for link in links:
        #         f.write(link)
        #         f.write('\n')

    def load(self, filename):
        self.clear()

        self.nodes = {}
        try:
            with open(filename, 'r') as f:
                self.language, self.csv_separator = f.readline().rstrip().split('.')
                nb_nodes, nb_links = map(int, f.readline().split())
                for i in range(nb_nodes):
                    line = f.readline().rstrip().split('|')
                    category, name, index, x, y = line[:5]
                    node = NODES[category][name](int(index))
                    node.load(line[5:])
                    self.nodes[int(index)] = node
                    self.addItem(node)
                    node.moveBy(float(x), float(y))
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
        except (IndexError, ValueError, KeyError):
            QMessageBox.critical(None, 'Error',
                                 'The workspace file is not valid.',
                                 QMessageBox.Ok)
        self.update()


