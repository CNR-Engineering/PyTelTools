import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from workflow.Tree import TreeScene
from workflow.nodes_io import *
from workflow.nodes_op import *
from workflow.nodes_calc import *

_NODES = {'Load Serafin': LoadSerafinNode, 'Write Serafin': WriteSerafinNode,
          'Select Variables': SelectVariablesNode, 'Select Time': SelectTimeNode,
          'Add Rouse': AddRouseNode,
          'Compute Volume': ComputeVolumeNode}


class TreeView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(TreeScene())
        self.parent = parent
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setAcceptDrops(True)
        self.current_node = None

    def resizeEvent(self, event):
        self.scene().setSceneRect(QRectF(0, 0, self.width()-10, self.height()-10))

    def dropEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            label = event.mimeData().text()
            node = _NODES[label](self.scene().nb_nodes)
            pos = self.mapToScene(event.pos())
            self.scene().add_node(node, pos)
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


class TreePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.view = TreeView(self)

        self.toolbar = QToolBar()
        self.node_label = QLineEdit()
        self.configure_act = QAction('Configure', self, triggered=self.configure_node, enabled=False)
        self.delete_act = QAction('Delete', self, triggered=self.delete_node, enabled=False)
        self.run_act = QAction('Run', self, triggered=self.run_node, enabled=False)
        self.init_toolbar()

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def init_toolbar(self):
        self.toolbar.addWidget(QLabel('Selected node  '))
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

    def configure_node(self):
        self.view.current_node.configure()
        if self.view.current_node.ready_to_run():
            self.run_act.setEnabled(True)

    def delete_node(self):
        self.view.scene().handle_remove_node(self.view.current_node)
        self.view.deselect_node()

    def run_node(self):
        self.view.current_node.run()

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


class NodeItem(QTreeWidgetItem):
    def __init__(self, label):
        super().__init__([label], QTreeWidgetItem.Type)
        self.label = label


class NodeTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        nodes_io = QTreeWidgetItem(self, ['Input/Output'])
        for text in ['Load Serafin', 'Write Serafin']:
            item = NodeItem(text)
            nodes_io.addChild(item)

        nodes_op = QTreeWidgetItem(self, ['Basic operations'])
        for text in ['Select Variables', 'Select Time', 'Add Rouse']:
            item = NodeItem(text)
            nodes_op.addChild(item)

        nodes_calc = QTreeWidgetItem(self, ['Calculations'])
        nodes_calc.addChild(NodeItem('Compute Volume'))

        for item in [nodes_io, nodes_calc]:
            self.addTopLevelItem(item)

        self.setDragEnabled(True)
        self.setMaximumWidth(200)
        self.setColumnCount(1)
        self.setHeaderLabel('Add Nodes')
        self.setContentsMargins(0, 0, 0, 0)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        current_item = self.currentItem()
        if current_item.parent() is not None:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.currentItem().text(0))
            drag.setMimeData(mime_data)
            drag.exec(Qt.MoveAction | Qt.CopyAction)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.tree = TreePanel()

        node_list = NodeTree()
        splitter = QSplitter()
        splitter.addWidget(node_list)
        splitter.addWidget(self.tree)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)
        self.resize(self.sizeHint())


def exception_hook(exctype, value, traceback):
    """!
    @brief Needed for suppressing traceback silencing in newer version of PyQt5
    """
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == '__main__':
    # suppress explicitly traceback silencing
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    view = MainWindow()
    view.show()
    app.exec_()




