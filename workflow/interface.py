import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from workflow.Tree import TreeScene, NODES


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
            category, label = event.mimeData().text().split('|')
            node = NODES[category][label](self.scene().nb_nodes)
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
        self.save_act = QAction('Save workspace\n(Ctrl+S)', self, triggered=self.save, shortcut='Ctrl+S')
        self.load_act = QAction('Load workspace\n(Ctrl+O)', self, triggered=self.load, shortcut='Ctrl+O')

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
        for act in [self.save_act, self.load_act, self.run_all_act]:
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
        nb_cc, labels = count_cc(list(self.view.scene().adj_list.keys()), self.view.scene().adj_list)
        if nb_cc > 1:
            QMessageBox.critical(None, 'Error',
                                 'You have disconnected nodes. The workspace cannot be saved.',
                                 QMessageBox.Ok)
            return

        filename, _ = QFileDialog.getSaveFileName(None, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.view.scene().save(filename)

    def load(self):
        msg = QMessageBox.warning(None, 'Confirm load',
                                  'Do you want to load workspace file?\n(Your current workspace will be erased)',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        filename, _ = QFileDialog.getOpenFileName(None, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.view.scene().load(filename)

    def run_all(self):
        self.view.scene().run_all()
        self.view.scene().update()

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
        self.setMaximumWidth(230)
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


class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        tree = TreePanel()
        node_list = NodeTree()

        left_panel = QWidget()
        config_button = QPushButton('Global\nConfiguration')
        config_button.setMinimumHeight(40)
        config_button.setMaximumWidth(230)
        config_button.clicked.connect(tree.view.scene().global_config)

        vlayout = QVBoxLayout()
        vlayout.addWidget(config_button)
        vlayout.addWidget(node_list)
        vlayout.setContentsMargins(0, 0, 0, 0)
        left_panel.setLayout(vlayout)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(tree)
        splitter.setHandleWidth(10)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(1, 1)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)


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
    widget = MyMainWindow()
    widget.showMaximized()
    app.exec_()




