import numpy as np
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from geom.transformation import Transformation, transformation_optimization as optimize


def is_connected(nodes, edge_list):
    """ad hoc function for checking if an undirected graph is connected"""
    adj = {}
    for i in nodes:
        adj[i] = set()
    for u, v in edge_list:
        adj[u].add(v)

    visited = {}
    for node in nodes:
        visited[node] = False

    stack = [nodes[0]]
    while stack:
        current_node = stack.pop()
        if not visited[current_node]:
            visited[current_node] = True
            for neighbor in adj[current_node]:
                stack.append(neighbor)
    return all(visited.values())


class OptimizationDialog(QDialog):
    def __init__(self, from_label, to_label):
        super().__init__()
        self.from_label = from_label
        self.to_label = to_label
        self.trans = None
        self.success = False

        self.pointBox = QGroupBox('Coordinate format')
        hlayout = QHBoxLayout()
        self.xyButton = QRadioButton('XY')
        hlayout.addWidget(self.xyButton)
        hlayout.addWidget(QRadioButton('XYZ'))
        self.pointBox.setLayout(hlayout)
        self.pointBox.setMaximumHeight(80)
        self.pointBox.setMaximumWidth(150)
        self.xyButton.setChecked(True)

        self.separatorBox = QGroupBox('Column separator')
        hlayout = QHBoxLayout()
        self.spaceButton = QRadioButton('Space/Tab')
        self.commaButton = QRadioButton('Comma ,')
        hlayout.addWidget(self.spaceButton)
        hlayout.addWidget(self.commaButton)
        hlayout.addWidget(QRadioButton('Semicolon ;'))
        self.separatorBox.setLayout(hlayout)
        self.separatorBox.setMaximumHeight(80)
        self.separatorBox.setMaximumWidth(300)
        self.spaceButton.setChecked(True)

        self.fromPoints = QPlainTextEdit()
        self.toPoints = QPlainTextEdit()

        self.runButton = QPushButton('Run')
        self.runButton.setFixedSize(130, 50)
        self.runButton.clicked.connect(self.run)
        self.resultBox = QPlainTextEdit()
        self.resultBox.setFixedHeight(120)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Help</b>: type or copy/paste coordinates (2 or 3 columns) '
                                    'in both coordinate systems<br>then click <b>Run</b>.'))
        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.pointBox)
        hlayout.addWidget(self.separatorBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(50, 20))

        hlayout = QHBoxLayout()
        vlayout = QVBoxLayout()
        lb = QLabel('Coordinates in %s' % from_label)
        vlayout.addWidget(lb)
        vlayout.addWidget(self.fromPoints)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addLayout(vlayout)
        vlayout = QVBoxLayout()
        lb = QLabel('Coordinates in %s' % to_label)
        vlayout.addWidget(lb)
        vlayout.addWidget(self.toPoints)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        hlayout.addLayout(vlayout)
        hlayout.setSpacing(15)

        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.runButton)
        hlayout.addWidget(self.resultBox)
        hlayout.setAlignment(self.runButton, Qt.AlignTop)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Create transformation from known points')
        self.resize(self.sizeHint())

    def check(self):
        if self.trans is None:
            self.reject()
        else:
            if self.success:
                self.accept()
            else:
                msg = QMessageBox.warning(None, 'Confirm new transformation',
                                          'Do you want to use the optimization result?',
                                          QMessageBox.Ok | QMessageBox.Cancel,
                                          QMessageBox.Ok)
                if msg == QMessageBox.Cancel:
                    return
                self.accept()

    def _getPoints(self):
        format_xy = self.xyButton.isChecked()
        separator = None if self.spaceButton.isChecked() else (',' if self.commaButton.isChecked() else ';')

        from_points = []
        to_points = []
        try:
            for line in self.fromPoints.toPlainText().splitlines():
                if not line:
                    continue
                if separator is None:
                    coord = tuple(map(float, line.split()))
                else:
                    coord = tuple(map(float, line.split(separator)))

                if format_xy:
                    from_points.append(np.array([coord[0], coord[1], 0]))
                else:
                    from_points.append(np.array([coord[0], coord[1], coord[2]]))
        except (ValueError, IndexError):
            QMessageBox.critical(self, 'Error', 'Invalid coordinates in %s.' % self.from_label,
                                 QMessageBox.Ok)
            return False, [], []
        if not from_points:
            QMessageBox.critical(self, 'Error', 'Empty input in %s.' % self.from_label,
                                 QMessageBox.Ok)
            return False, [], []
        try:
            for line in self.toPoints.toPlainText().splitlines():
                if not line:
                    continue
                if separator is None:
                    coord = tuple(map(float, line.split()))
                else:
                    coord = tuple(map(float, line.split(separator)))

                if format_xy:
                    to_points.append(np.array([coord[0], coord[1], 0]))
                else:
                    to_points.append(np.array([coord[0], coord[1], coord[2]]))
        except (ValueError, IndexError):
            QMessageBox.critical(self, 'Error', 'Invalid coordinates in %s.' % self.to_label,
                                 QMessageBox.Ok)
            return False, [], []
        if not to_points:
            QMessageBox.critical(self, 'Error', 'Empty input in %s.' % self.to_label,
                                 QMessageBox.Ok)
            return False, [], []
        if len(from_points) != len(to_points):
            QMessageBox.critical(self, 'Error', 'Two systems should have the same number of coordinates!',
                                 QMessageBox.Ok)
            return False, [], []
        return True, from_points, to_points

    def run(self):
        ready, from_points, to_points = self._getPoints()
        if not ready:
            return
        ignore_z = self.xyButton.isChecked()
        self.trans, error, self.success, message = optimize(from_points, to_points, ignore_z)
        self.resultBox.clear()
        self.resultBox.appendPlainText('Success: %s' % str(self.success))
        self.resultBox.appendPlainText('Final square error: %s' % str(error))
        self.resultBox.appendPlainText(message)
        self.resultBox.appendPlainText('Result:\n%s' % str(self.trans))


class AddTransformationDialog(QDialog):
    def __init__(self, from_label, to_label):
        super().__init__()
        self.transformation = None
        self.from_label = from_label
        self.to_label = to_label

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        defaultButton = QPushButton('Default')
        defaultButton.setFixedSize(110, 50)
        defaultButton.clicked.connect(self.default)

        optimizeButton = QPushButton('Use known\npoints')
        optimizeButton.setFixedSize(110, 50)
        optimizeButton.clicked.connect(self.optimize)

        self.dx = QLineEdit('0')
        self.dy = QLineEdit('0')
        self.dz = QLineEdit('0')
        self.angle = QLineEdit('0')
        self.scalexy = QLineEdit('1')
        self.scalez = QLineEdit('1')

        mainLayout = QVBoxLayout()
        lb = QLabel('<b>Transformation from %s to %s<b>' % (self.from_label, self.to_label))
        mainLayout.addWidget(lb)
        mainLayout.setAlignment(lb, Qt.AlignHCenter)
        mainLayout.addItem(QSpacerItem(10, 10))
        glayout = QGridLayout()

        glayout.addWidget(QLabel('<b>Rotation<b>'), 1, 1)
        glayout.addWidget(QLabel('angle (rad)'), 2, 2, Qt.AlignRight)
        glayout.addWidget(self.angle, 2, 3)

        glayout.addWidget(QLabel('<b>Scaling<b>'), 3, 1)
        glayout.addWidget(QLabel('XY factor'), 4, 2, Qt.AlignRight)
        glayout.addWidget(self.scalexy, 4, 3)
        glayout.addWidget(QLabel('Z factor'), 4, 4, Qt.AlignRight)
        glayout.addWidget(self.scalez, 4, 5)

        glayout.addWidget(QLabel('<b>Translation<b>'), 5, 1)
        glayout.addWidget(QLabel('translate X'), 6, 2, Qt.AlignRight)
        glayout.addWidget(self.dx, 6, 3)
        glayout.addWidget(QLabel('translate Y'), 6, 4, Qt.AlignRight)
        glayout.addWidget(self.dy, 6, 5)
        glayout.addWidget(QLabel('translate Z'), 6, 6, Qt.AlignRight)
        glayout.addWidget(self.dz, 6, 7)

        mainLayout.addLayout(glayout)
        mainLayout.setAlignment(glayout, Qt.AlignTop)

        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addWidget(defaultButton)
        hlayout.addWidget(optimizeButton)
        hlayout.setAlignment(Qt.AlignLeft)
        hlayout.setSpacing(10)
        mainLayout.addLayout(hlayout, Qt.AlignLeft)
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Add new transformation')
        self.resize(self.sizeHint())

    def default(self):
        for box in [self.dx, self.dy, self.dz, self.angle]:
            box.setText('0')
        self.scalexy.setText('1')
        self.scalez.setText('1')

    def optimize(self):
        dlg = OptimizationDialog(self.from_label, self.to_label)
        if dlg.exec_() == QDialog.Rejected:
            return
        trans = dlg.trans
        self.dx.setText(str(trans.translation.dx))
        self.dy.setText(str(trans.translation.dy))
        self.dz.setText(str(trans.translation.dz))
        self.angle.setText(str(trans.rotation.angle))
        self.scalexy.setText(str(trans.scaling.horizontal_factor))
        self.scalez.setText(str(trans.scaling.vertical_factor))

    def check(self):
        try:
            angle, scalexy, scalez, dx, dy, dz = map(float, [box.text() for box in [self.angle,
                                                                                    self.scalexy, self.scalez,
                                                                                    self.dx, self.dy, self.dz]])
        except ValueError:
            QMessageBox.critical(self, 'Error', 'The transformation parameters should be numbers!',
                                 QMessageBox.Ok)
            return
        if scalexy == 0 or scalez == 0:
            QMessageBox.critical(self, 'Error', 'The scaling factors cannot be equal to zero!',
                                 QMessageBox.Ok)
            return
        self.transformation = Transformation(angle, scalexy, scalez, dx, dy, dz)
        self.accept()


class EditTransformationDialog(QDialog):
    def __init__(self, from_label, to_label, trans, inverse_trans):
        super().__init__()
        self.transformation = None
        self.deleted = False

        self.trans = trans
        self.inverse_trans = inverse_trans
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.editDone)
        buttons.rejected.connect(self.reject)

        deleteButton = QPushButton('Delete')
        deleteButton.setFixedSize(110, 30)
        deleteButton.clicked.connect(self.deleteEvent)

        self.dx = QLineEdit(str(trans.translation.dx))
        self.dy = QLineEdit(str(trans.translation.dy))
        self.dz = QLineEdit(str(trans.translation.dz))
        self.angle = QLineEdit(str(trans.rotation.angle))
        self.scalexy = QLineEdit(str(trans.scaling.horizontal_factor))
        self.scalez = QLineEdit(str(trans.scaling.vertical_factor))

        self.inv_dx = QLineEdit(str(inverse_trans.translation.dx))
        self.inv_dy = QLineEdit(str(inverse_trans.translation.dy))
        self.inv_dz = QLineEdit(str(inverse_trans.translation.dz))
        self.inv_angle = QLineEdit(str(inverse_trans.rotation.angle))
        self.inv_scalexy = QLineEdit(str(inverse_trans.scaling.horizontal_factor))
        self.inv_scalez = QLineEdit(str(inverse_trans.scaling.vertical_factor))

        self.dx.editingFinished.connect(self.edit_dx)
        self.dy.editingFinished.connect(self.edit_dy)
        self.dz.editingFinished.connect(self.edit_dz)
        self.angle.editingFinished.connect(self.edit_angle)
        self.scalexy.editingFinished.connect(self.edit_scalexy)
        self.scalez.editingFinished.connect(self.edit_scalez)

        self.inv_dx.editingFinished.connect(self.edit_inv_dx)
        self.inv_dy.editingFinished.connect(self.edit_inv_dy)
        self.inv_dz.editingFinished.connect(self.edit_inv_dz)
        self.inv_angle.editingFinished.connect(self.edit_inv_angle)
        self.inv_scalexy.editingFinished.connect(self.edit_inv_scalexy)
        self.inv_scalez.editingFinished.connect(self.edit_inv_scalez)

        mainLayout = QVBoxLayout()

        vlayout = QVBoxLayout()
        lb = QLabel('<b>Transformation from %s to %s<b>' % (from_label, to_label))
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addItem(QSpacerItem(10, 10))
        glayout = QGridLayout()

        glayout.addWidget(QLabel('<b>Rotation<b>'), 1, 1)
        glayout.addWidget(QLabel('angle (rad)'), 2, 2, Qt.AlignRight)
        glayout.addWidget(self.angle, 2, 3)

        glayout.addWidget(QLabel('<b>Scaling<b>'), 3, 1)
        glayout.addWidget(QLabel('XY factor'), 4, 2, Qt.AlignRight)
        glayout.addWidget(self.scalexy, 4, 3)
        glayout.addWidget(QLabel('Z factor'), 4, 4, Qt.AlignRight)
        glayout.addWidget(self.scalez, 4, 5)

        glayout.addWidget(QLabel('<b>Translation<b>'), 5, 1)
        glayout.addWidget(QLabel('translate X'), 6, 2, Qt.AlignRight)
        glayout.addWidget(self.dx, 6, 3)
        glayout.addWidget(QLabel('translate Y'), 6, 4, Qt.AlignRight)
        glayout.addWidget(self.dy, 6, 5)
        glayout.addWidget(QLabel('translate Z'), 6, 6, Qt.AlignRight)
        glayout.addWidget(self.dz, 6, 7)
        vlayout.addLayout(glayout)
        mainLayout.addLayout(vlayout)
        mainLayout.setAlignment(vlayout, Qt.AlignTop)
        mainLayout.addItem(QSpacerItem(10, 20))

        vlayout = QVBoxLayout()
        lb = QLabel('<b>Transformation from %s to %s<b>' % (to_label, from_label))
        vlayout.addWidget(lb)
        vlayout.setAlignment(lb, Qt.AlignHCenter)
        vlayout.addItem(QSpacerItem(10, 10))
        glayout = QGridLayout()

        glayout.addWidget(QLabel('<b>Rotation<b>'), 1, 1)
        glayout.addWidget(QLabel('angle (rad)'), 2, 2, Qt.AlignRight)
        glayout.addWidget(self.inv_angle, 2, 3)

        glayout.addWidget(QLabel('<b>Scaling<b>'), 3, 1)
        glayout.addWidget(QLabel('XY factor'), 4, 2, Qt.AlignRight)
        glayout.addWidget(self.inv_scalexy, 4, 3)
        glayout.addWidget(QLabel('Z factor'), 4, 4, Qt.AlignRight)
        glayout.addWidget(self.inv_scalez, 4, 5)

        glayout.addWidget(QLabel('<b>Translation<b>'), 5, 1)
        glayout.addWidget(QLabel('translate X'), 6, 2, Qt.AlignRight)
        glayout.addWidget(self.inv_dx, 6, 3)
        glayout.addWidget(QLabel('translate Y'), 6, 4, Qt.AlignRight)
        glayout.addWidget(self.inv_dy, 6, 5)
        glayout.addWidget(QLabel('translate Z'), 6, 6, Qt.AlignRight)
        glayout.addWidget(self.inv_dz, 6, 7)
        vlayout.addLayout(glayout)
        mainLayout.addLayout(vlayout)
        mainLayout.setAlignment(vlayout, Qt.AlignTop)

        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(deleteButton, Qt.AlignLeft)
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Edit transformation')
        self.resize(self.sizeHint())

    def edit_dx(self):
        try:
            dx = float(self.dx.text())
            self.inv_dx.setText(str(-dx))
        except ValueError:
            self.dx.setText(str(self.trans.translation.dx))

    def edit_dy(self):
        try:
            dy = float(self.dy.text())
            self.inv_dy.setText(str(-dy))
        except ValueError:
            self.dy.setText(str(self.trans.translation.dy))

    def edit_dz(self):
        try:
            dz = float(self.dz.text())
            self.inv_dz.setText(str(-dz))
        except ValueError:
            self.dz.setText(str(self.trans.translation.dz))

    def edit_angle(self):
        try:
            angle = float(self.angle.text())
            self.inv_angle.setText(str(-angle))
        except ValueError:
            self.angle.setText(str(self.trans.rotation.angle))

    def edit_scalexy(self):
        try:
            scalexy = float(self.scalexy.text())
            if scalexy == 0:
                self.scalexy.setText(str(self.trans.scaling.horizontal_factor))
            else:
                self.inv_scalexy.setText(str(1/scalexy))
        except ValueError:
            self.scalexy.setText(str(self.trans.scaling.horizontal_factor))

    def edit_scalez(self):
        try:
            scalez = float(self.scalez.text())
            if scalez == 0:
                self.scalexy.setText(str(self.trans.scaling.vertical_factor))
            else:
                self.inv_scalez.setText(str(1/scalez))
        except ValueError:
            self.scalez.setText(str(self.trans.scaling.vertical_factor))

    def edit_inv_dx(self):
        try:
            dx = float(self.inv_dx.text())
            self.dx.setText(str(-dx))
        except ValueError:
            self.inv_dx.setText(str(self.inverse_trans.translation.dx))

    def edit_inv_dy(self):
        try:
            dy = float(self.inv_dy.text())
            self.dy.setText(str(-dy))
        except ValueError:
            self.inv_dy.setText(str(self.inverse_trans.translation.dy))

    def edit_inv_dz(self):
        try:
            dz = float(self.inv_dz.text())
            self.dz.setText(str(-dz))
        except ValueError:
            self.inv_dz.setText(str(self.inverse_trans.translation.dz))

    def edit_inv_angle(self):
        try:
            angle = float(self.inv_angle.text())
            self.angle.setText(str(-angle))
        except ValueError:
            self.inv_angle.setText(str(self.inverse_trans.rotation.angle))

    def edit_inv_scalexy(self):
        try:
            scalexy = float(self.inv_scalexy.text())
            if scalexy == 0:
                self.inv_scalexy.setText(str(self.inverse_trans.scaling.horizontal_factor))
            else:
                self.scalexy.setText(str(1/scalexy))
        except ValueError:
            self.inv_scalexy.setText(str(self.inverse_trans.scaling.horizontal_factor))

    def edit_inv_scalez(self):
        try:
            scalez = float(self.inv_scalez.text())
            if scalez == 0:
                self.inv_scalez.setText(str(self.inverse_trans.scaling.vertical_factor))
            else:
                self.scalez.setText(str(1/scalez))
        except ValueError:
            self.inv_scalez.setText(str(self.inverse_trans.scaling.vertical_factor))

    def editDone(self):
        angle, scalexy, scalez, dx, dy, dz = map(float, [box.text() for box in [self.angle,
                                                                                self.scalexy, self.scalez,
                                                                                self.dx, self.dy, self.dz]])
        self.transformation = Transformation(angle, scalexy, scalez, dx, dy, dz)
        self.accept()

    def deleteEvent(self):
        msg = QMessageBox.warning(None, 'Confirm delete',
                                  'Do you want to delete this transformation?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        self.deleted = True
        self.reject()


class EditSystemDialog(QDialog):
    def __init__(self, old_label, can_delete):
        super().__init__()
        self.deleted = False

        self.labelBox = QLineEdit(old_label)
        self.labelBox.setFixedHeight(30)

        deleteButton = QPushButton('Delete')
        deleteButton.setFixedSize(110, 30)
        deleteButton.setEnabled(can_delete)
        deleteButton.clicked.connect(self.deleteEvent)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 15))
        mainLayout.addWidget(QLabel('Edit coordinate system label'))
        mainLayout.addWidget(self.labelBox)
        mainLayout.addStretch()
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(deleteButton, Qt.AlignLeft)
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(buttons)

        self.setLayout(mainLayout)
        self.setWindowTitle('Edit coordinate system')
        self.setMinimumWidth(300)
        self.resize(self.sizeHint())

    def deleteEvent(self):
        msg = QMessageBox.warning(None, 'Confirm delete',
                                  'Do you want to delete this coordinate system?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        self.deleted = True
        self.reject()


class TransformationMap(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle('Define transformations between coordinate systems')

        self.recWidth = 80
        self.recHeight = 50
        self.circleRadius = 20

        self.rectangles = [QRect(int(self.width()/2-40), int(self.height()/2-25), self.recWidth, self.recHeight),
                           QRect(int(self.width()/2-40), int(self.height()/2+95), self.recWidth, self.recHeight)]
        self.labels = ['System 1', 'System 2']
        self.transformations = {}

        self.statusbar = QStatusBar()
        self.btnAddRect = QPushButton('Add\nSystem', self)
        self.btnAddRect.clicked.connect(self.addRect)
        self.btnAddRect.setFixedSize(110, 50)

        self.btnClear = QPushButton('Clear', self)
        self.btnClear.clicked.connect(self.clear)
        self.btnClear.setFixedSize(110, 50)

        self.btnAddConnect = QPushButton('Add\nTransformation', self)
        self.btnAddConnect.clicked.connect(self.addConnection)
        self.btnAddConnect.setFixedSize(110, 50)
        self.btnAddConnect.setCheckable(True)
        self.btnAddConnect.setChecked(False)

        self.btnSave = QPushButton('Save', self)
        self.btnSave.clicked.connect(self.save)
        self.btnSave.setFixedSize(110, 50)
        self.btnSave.setEnabled(False)

        self.btnLoad = QPushButton('Load', self)
        self.btnLoad.clicked.connect(self.load)
        self.btnLoad.setFixedSize(110, 50)

        layout = QVBoxLayout()
        layout.addWidget(self.btnAddConnect)
        layout.addWidget(self.btnAddRect)
        layout.addWidget(self.btnClear)

        layout.addItem(QSpacerItem(10, 15))
        layout.addStretch()
        layout.addWidget(self.btnSave)
        layout.addWidget(self.btnLoad)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.statusbar)
        self.setLayout(layout)
        self.resize(800, 600)

        self.pen = QPen(QColor(0, 0, 0))
        self.pen.setWidth(2)

        self.blackBrush = QBrush(QColor(255, 255, 255, 255))
        self.highlight = QColor(255, 255, 180, 255)
        self.blueBrush = QBrush(QColor(200, 230, 250, 255))

        self.add_connection_mode = False
        self.connection_point = None
        self.current_rectangle = -1
        self.setMouseTracking(True)

    def clear(self):
        msg = QMessageBox.warning(None, 'Confirm clear',
                                  'Do you want to clear all systems and transformations?',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        self.rectangles = [QRect(self.width()/2-40, self.height()/2-25, self.recWidth, self.recHeight),
                           QRect(self.width()/2-40, self.height()/2+95, self.recWidth, self.recHeight)]
        self.labels = ['System 1', 'System 2']
        self.btnAddConnect.setEnabled(True)
        self.btnSave.setEnabled(False)
        self.transformations = {}
        self.repaint()

    def addRect(self):
        self.rectangles.append(QRect(int(self.width()/2-40), int(self.height()/2-25), self.recWidth, self.recHeight))
        self.labels.append('System %d' % len(self.rectangles))
        self.btnAddConnect.setEnabled(True)
        self.btnSave.setEnabled(False)
        self.repaint()

    def addConnection(self):
        self.btnAddConnect.setChecked(True)
        self.add_connection_mode = True
        self.statusbar.showMessage('Draw a line between two systems')

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        with open(filename, 'w') as f:
            f.write('|'.join(self.labels))
            f.write('\n')
            f.write('|'.join(map(lambda p: '%d,%d' % (p.x(), p.y()), [rec.topLeft() for rec in self.rectangles])))
            f.write('\n')
            for (i, j), t in self.transformations.items():
                if i > j:
                    continue
                f.write('%d|%d|%s' % (i, j, repr(t)))
                f.write('\n')

    def load(self):
        msg = QMessageBox.warning(None, 'Confirm load',
                                  'Do you want to load configuration file?\n(Your current workspace will be erased)',
                                  QMessageBox.Ok | QMessageBox.Cancel,
                                  QMessageBox.Ok)
        if msg == QMessageBox.Cancel:
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        try:
            with open(filename, 'r') as f:
                new_labels = f.readline().rstrip().split('|')
                coords = f.readline().rstrip().split('|')
                new_rectangles = []
                for coord in coords:
                    x, y = map(int, coord.split(','))
                    new_rectangles.append(QRect(x, y, self.recWidth, self.recHeight))
                new_transformations = {}
                for line in f.readlines():
                    i, j, params = line.rstrip().split('|')
                    i, j = int(i), int(j)
                    angle, scalexy, scalez, dx, dy, dz = map(float, params.split())
                    new_transformations[i, j] = Transformation(angle, scalexy, scalez, dx, dy, dz)
                    new_transformations[j, i] = new_transformations[i, j].inverse()
        except (ValueError, IndexError):
            QMessageBox.critical(self, 'Error', 'The configuration is not valid.',
                                 QMessageBox.Ok)
            return

        self.labels = new_labels
        self.rectangles = new_rectangles
        self.transformations = new_transformations
        self.repaint()

    def mousePressEvent(self, event):
        pos = event.pos()
        for index, rec in enumerate(self.rectangles):
            if rec.contains(pos):
                self.current_rectangle = index
                if self.add_connection_mode:
                    self.connection_point = pos
                break

    def mouseMoveEvent(self, event):
        if self.current_rectangle > -1:
            if self.add_connection_mode:
                self.connection_point = event.pos()
            else:
                self.rectangles[self.current_rectangle].moveCenter(event.pos())
        self.repaint()

    def mouseReleaseEvent(self, event):
        pos = event.pos()
        if self.current_rectangle > -1 and self.add_connection_mode:
            for index, rec in enumerate(self.rectangles):
                if rec.contains(pos):
                    if self.current_rectangle != index and (self.current_rectangle, index) not in self.transformations:
                        dlg = AddTransformationDialog(self.labels[self.current_rectangle], self.labels[index])
                        value = dlg.exec_()
                        if value == QDialog.Accepted:
                            self.transformations[self.current_rectangle, index] = dlg.transformation
                            self.transformations[index, self.current_rectangle] = dlg.transformation.inverse()

                            if is_connected(list(range(len(self.rectangles))), self.transformations.keys()):
                                self.btnAddConnect.setEnabled(False)
                                self.btnSave.setEnabled(True)
                        break
        self.add_connection_mode = False
        self.btnAddConnect.setChecked(False)

        self.current_rectangle = -1
        self.repaint()
        self.statusbar.clearMessage()

    def mouseDoubleClickEvent(self, event):
        current_index = -1
        pos = event.pos()
        for index, rec in enumerate(self.rectangles):
            if rec.contains(pos):
                current_index = index
                break
        if current_index > -1:
            dlg = EditSystemDialog(self.labels[current_index], len(self.labels) > 2)
            value = dlg.exec_()
            if value == QDialog.Accepted:
                self.labels[current_index] = dlg.labelBox.text()
            elif value == QDialog.Rejected and dlg.deleted:
                self.rectangles = [self.rectangles[i] for i in range(len(self.rectangles)) if i != current_index]
                self.labels = [self.labels[i] for i in range(len(self.labels)) if i != current_index]
                new_transformation = {}
                for i, j in self.transformations:
                    if i == current_index or j == current_index:
                        continue
                    new_i, new_j = i-1 if i > current_index else i, j-1 if j > current_index else j
                    new_transformation[new_i, new_j] = self.transformations[i, j]

                self.transformations = new_transformation
                if is_connected(list(range(len(self.rectangles))), self.transformations.keys()):
                    self.btnAddConnect.setEnabled(False)
                    self.btnSave.setEnabled(True)
                else:
                    self.btnAddConnect.setEnabled(True)
                    self.btnSave.setEnabled(False)

            self.repaint()
        else:
            for i, j in self.transformations:
                if i > j:
                    continue
                p1, p2 = self.rectangles[i].center(), self.rectangles[j].center()
                x_center, y_center = (p1.x()+p2.x())/2, (p1.y()+p2.y())/2
                if max(abs(x_center-event.x()), abs(y_center-event.y())) < self.circleRadius:
                    dlg = EditTransformationDialog(self.labels[i], self.labels[j],
                                                   self.transformations[i, j], self.transformations[j, i])
                    value = dlg.exec_()
                    if value == QDialog.Accepted:
                        self.transformations[i, j] = dlg.transformation
                        self.transformations[j, i] = dlg.transformation.inverse()
                    elif value == QDialog.Rejected and dlg.deleted:
                        del self.transformations[i, j]
                        del self.transformations[j, i]

                        self.btnAddConnect.setEnabled(True)
                        self.btnSave.setEnabled(False)
                    break

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.pen)
        painter.setBrush(self.blackBrush)
        for i in range(len(self.rectangles)-1):
            for j in range(i+1, len(self.rectangles)):
                if (i, j) in self.transformations:
                    p1 = self.rectangles[i].center()
                    p2 = self.rectangles[j].center()
                    painter.drawLine(p1, p2)
                    painter.setBrush(self.blueBrush)
                    painter.drawEllipse(QPoint((p1.x()+p2.x())/2, (p1.y()+p2.y())/2),
                                        self.circleRadius, self.circleRadius)
                    painter.setBrush(self.blackBrush)

        for i, rec in enumerate(self.rectangles):
            painter.drawRect(rec)
            painter.drawText(rec, Qt.AlignCenter, self.labels[i])
        if self.current_rectangle > -1:
            if self.add_connection_mode:
                painter.drawLine(self.rectangles[self.current_rectangle].center(), self.connection_point)
            else:
                painter.fillRect(self.rectangles[self.current_rectangle], self.highlight)
                painter.drawText(self.rectangles[self.current_rectangle], Qt.AlignCenter,
                                 self.labels[self.current_rectangle])


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
    widget = TransformationMap()
    widget.show()
    app.exec_()

