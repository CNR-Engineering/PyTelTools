import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import logging
import shapefile
import geom.Shapefile as shp
from geom.transformation import load_transformation_map
import geom.conversion as convert
from gui.util import QPlainTextEditLogger, TelToolWidget


class FileConverterInputTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.transformation = None
        self.converter = None
        self.from_type = None

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        """!
        @brief (Used in __init__) Create widgets
        """
        # create the group box for coordinate transformation
        self.confBox = QGroupBox('Apply coordinate transformation (optional)')
        self.confBox.setStyleSheet('QGroupBox {font-size: 12px;font-weight: bold;}')
        self.btnConfig = QPushButton('Load\nTransformation', self)
        self.btnConfig.setToolTip('<b>Open</b> a transformation config file')
        self.btnConfig.setFixedSize(105, 50)
        self.confNameBox = QLineEdit()
        self.confNameBox.setReadOnly(True)
        self.confNameBox.setFixedHeight(30)
        self.fromBox = QComboBox()
        self.fromBox.setFixedWidth(150)
        self.toBox = QComboBox()
        self.toBox.setFixedWidth(150)

        # create the open button
        self.btnOpen = QPushButton('Open', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Open</b> a geometry file (.shp .xyz .i2s .i3s)')
        self.btnOpen.setFixedSize(105, 50)

        # create some text fields displaying the IO files info
        self.inNameBox = QLineEdit()
        self.inNameBox.setReadOnly(True)
        self.inNameBox.setFixedHeight(30)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnConfig)
        hlayout.addWidget(self.confNameBox)
        vlayout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('    Transform from'))
        hlayout.addWidget(self.fromBox)
        hlayout.addWidget(QLabel('to'))
        hlayout.addWidget(self.toBox)
        hlayout.setAlignment(Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.setSpacing(15)
        self.confBox.setLayout(vlayout)
        mainLayout.addWidget(self.confBox)

        mainLayout.addItem(QSpacerItem(10, 15))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpen)
        hlayout.addWidget(self.inNameBox)
        mainLayout.addLayout(hlayout)

        mainLayout.addItem(QSpacerItem(10, 10))

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnConfig.clicked.connect(self.btnConfigEvent)

    def _handleOpenShapefile(self, filename):
        try:
            with open(filename, 'r') as f:
                pass
        except PermissionError:
            QMessageBox.critical(None, 'Error', 'Permission denied.', QMessageBox.Ok)
            self.parent.reset()
            return False
        try:
            shape_type = shp.get_shape_type(filename)
        except shapefile.ShapefileException:
            QMessageBox.critical(None, 'Error', 'Failed to open shp file (is the .dbf file present?).', QMessageBox.Ok)
            self.parent.reset()
            return False

        if shape_type == 1:
            self.from_type = 'shp Point'
        elif shape_type == 11:
            self.from_type = 'shp PointZ'
        elif shape_type == 21:
            self.from_type = 'shp PointM'
        elif shape_type == 3:
            self.from_type = 'shp Polyline'
        elif shape_type == 13:
            self.from_type = 'shp PolylineZ'
        elif shape_type == 23:
            self.from_type = 'shp PolylineM'
        elif shape_type == 5:
            self.from_type = 'shp Polygon'
        elif shape_type == 15:
            self.from_type = 'shp PolygonZ'
        elif shape_type == 25:
            self.from_type = 'shp PolygonM'
        elif shape_type == 8:
            self.from_type = 'shp Multipoint'
        elif shape_type == 18:
            self.from_type = 'shp MultiPointZ'
        elif shape_type == 28:
            self.from_type = 'shp MultiPointM'
        elif shape_type == 0:
            QMessageBox.critical(None, 'Error', 'The shape type Null is currently not supported!', QMessageBox.Ok)
            self.parent.reset()
            return False
        else:
            QMessageBox.critical(None, 'Error', 'The shape type MultiPatch is currently not supported!', QMessageBox.Ok)
            self.parent.reset()
            return False
        if shape_type in (1, 11, 21):
            self.converter = convert.ShpPointConverter(filename, shape_type)
        elif shape_type in (3, 5, 13, 15, 23, 25):
            self.converter = convert.ShpLineConverter(filename, shape_type)
        else:
            self.converter = convert.ShpMultiPointConverter(filename, shape_type)
        return True

    def btnConfigEvent(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose the file name', '', 'All files (*)',
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        self.fromBox.clear()
        self.toBox.clear()
        self.confNameBox.clear()
        self.transformation = None

        success, self.transformation = load_transformation_map(filename)
        if not success:
            QMessageBox.critical(self, 'Error', 'The configuration is not valid.',
                                 QMessageBox.Ok)
            return
        self.confNameBox.setText(filename)
        for label in self.transformation.labels:
            self.fromBox.addItem(label)
            self.toBox.addItem(label)

    def btnOpenEvent(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, 'Open a geometry file', '',
                                                  'Geometry Files (*.shp *.xyz *.i2s *.i3s)', options=options)
        if not filename:
            return

        self.inNameBox.setText(filename)
        suffix = filename[-4:]
        if suffix == '.xyz':
            self.converter = convert.XYZConverter(filename)
            self.from_type = 'xyz'
        elif suffix == '.shp':
            if not self._handleOpenShapefile(filename):
                return
        elif suffix == '.i2s' or suffix == '.i3s':
            self.converter = convert.BKLineConverter(filename)
            self.from_type = suffix[1:]

        self.converter.set_csv_separator(self.parent.csv_separator)
        logging.info('Reading the input file...')
        QApplication.processEvents()
        try:
            self.converter.read()
        except PermissionError:
            QMessageBox.critical(None, 'Error', 'Permission denied (Is the file opened by another application?).',
                                 QMessageBox.Ok)
            self.parent.reset()
            return
        except ValueError:
            QMessageBox.critical(None, 'Error', 'The file is empty!', QMessageBox.Ok)
            self.parent.reset()
            return
        except RuntimeError:
            QMessageBox.critical(None, 'Error', 'Failed to read the shp file: Inconsistent bytes.',
                                 QMessageBox.Ok)
            self.parent.reset()
            return
        logging.info('Finished reading the input file: %s' % filename)
        self.parent.getInput()
        QMessageBox.information(self, 'Success',
                                'Finished reading the input file. The file converter is ready!',
                                QMessageBox.Ok)


class FileConverterOutputTab(QWidget):
    def __init__(self, inputTab):
        super().__init__()
        self.input = inputTab

        self.EMPTY = 0
        self.BK_SHP = 1
        self.Z_FROM_SHP = 2
        self.M_FROM_SHP = 3
        self.SHP_BK = 4
        self.Z_AND_BK = 5
        self.Z_AND_M = 6

        self.convert_type = {'xyz': {'xyz': self.EMPTY, 'shp PointZ': self.BK_SHP, 'csv': self.EMPTY},
                             'i2s': {'i2s': self.EMPTY, 'shp Polyline': self.BK_SHP,
                                                        'shp Polygon': self.BK_SHP, 'csv': self.EMPTY},
                             'i3s': {'i3s': self.EMPTY, 'i2s': self.EMPTY,
                                     'shp PolylineZ': self.BK_SHP,
                                     'shp PolygonZ': self.BK_SHP, 'csv': self.EMPTY},
                             'shp Point': {'shp Point': self.EMPTY, 'shp PointZ': self.Z_AND_M,
                                           'xyz': self.Z_FROM_SHP, 'csv': self.EMPTY},
                             'shp PointZ': {'shp Point': self.EMPTY, 'shp PointZ': self.Z_AND_M,
                                            'shp PointM': self.M_FROM_SHP,
                                            'xyz': self.Z_FROM_SHP, 'csv': self.EMPTY},
                             'shp PointM': {'shp Point': self.EMPTY, 'shp PointM': self.M_FROM_SHP,
                                            'shp PointZ': self.Z_AND_M, 'xyz': self.Z_FROM_SHP, 'csv': self.EMPTY},
                             'shp Polyline': {'shp Polyline': self.EMPTY, 'shp PolylineZ': self.Z_AND_M,
                                              'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp Polygon': {'shp Polygon': self.EMPTY, 'shp PolygonZ': self.Z_AND_M,
                                             'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp PolylineZ': {'shp PolylineZ': self.Z_AND_M, 'shp Polyline': self.EMPTY,
                                               'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp PolygonZ': {'shp PolygonZ': self.Z_AND_M, 'shp Polygon': self.EMPTY,
                                              'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp PolylineM': {'shp Polyline': self.EMPTY,
                                               'shp PolylineM': self.M_FROM_SHP, 'shp PolylineZ': self.Z_AND_M,
                                               'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp PolygonM': {'shp Polygon': self.EMPTY, 'shp PolygonM': self.M_FROM_SHP,
                                              'shp PolygonZ': self.Z_AND_M,
                                              'i2s': self.SHP_BK, 'i3s': self.Z_AND_BK, 'csv': self.EMPTY},
                             'shp MultiPoint': {'shp MultiPoint': self.EMPTY, 'shp Point': self.EMPTY,
                                                'csv': self.EMPTY},
                             'shp MultiPointZ': {'shp MultiPointZ': self.EMPTY, 'shp PointZ': self.EMPTY,
                                                 'csv': self.EMPTY},
                             'shp MultiPointM': {'shp MultiPointM': self.EMPTY, 'shp PointM': self.EMPTY,
                                                 'csv': self.EMPTY}}
        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create a text for input information
        self.inputBox = QPlainTextEdit()
        self.inputBox.setFixedHeight(60)
        self.inputBox.setReadOnly(True)

        # create the widget displaying message logs
        self.logTextBox = QPlainTextEditLogger(self)
        self.logTextBox.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - \n%(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # create a combo box for output file type
        self.outTypeBox = QComboBox()
        self.outTypeBox.setFixedHeight(30)

        # create a text box for output file name
        self.outNameBox = QLineEdit()
        self.outNameBox.setReadOnly(True)
        self.outNameBox.setFixedHeight(30)

        # create the option panel
        self.stack = QStackedLayout()

        self.empty = QWidget()

        self.bkshp = QWidget()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Attribute name'))
        self.bkshpname = QLineEdit('Value')
        self.bkshpname.setFixedHeight(30)
        hlayout.addWidget(self.bkshpname)
        self.bkshp.setLayout(hlayout)

        self.zfield = QWidget()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill Z with'))
        self.zfieldchoice = QComboBox()
        self.zfieldchoice.setFixedHeight(30)
        hlayout.addWidget(self.zfieldchoice, Qt.AlignLeft)
        self.zfield.setLayout(hlayout)

        self.mfield = QWidget()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill M with'))
        self.mfieldchoice = QComboBox()
        self.mfieldchoice.setFixedHeight(30)
        hlayout.addWidget(self.mfieldchoice, Qt.AlignLeft)
        self.mfield.setLayout(hlayout)

        self.shpbk = QWidget()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill attribute with'))
        self.shpbkmethod = QComboBox()
        self.shpbkmethod.setFixedHeight(30)
        hlayout.addWidget(self.shpbkmethod, Qt.AlignLeft)
        self.shpbk.setLayout(hlayout)

        self.shpbkz = QWidget()
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill Z with'))
        self.zfieldchoicebis = QComboBox()
        self.zfieldchoicebis.setFixedHeight(30)
        hlayout.addWidget(self.zfieldchoicebis, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill attribute with'))
        self.shpbkmethodbis = QComboBox()
        self.shpbkmethodbis.setFixedHeight(30)
        hlayout.addWidget(self.shpbkmethodbis, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        self.shpbkz.setLayout(vlayout)

        self.shpzm = QWidget()
        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill Z with'))
        self.zfieldchoiceter = QComboBox()
        self.zfieldchoiceter.setFixedHeight(30)
        hlayout.addWidget(self.zfieldchoiceter, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Fill M with'))
        self.mfieldchoicebis = QComboBox()
        self.mfieldchoicebis.setFixedHeight(30)
        hlayout.addWidget(self.mfieldchoicebis, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        self.shpzm.setLayout(vlayout)

        for panel in [self.empty, self.bkshp, self.zfield, self.mfield, self.shpbk, self.shpbkz, self.shpzm]:
            self.stack.addWidget(panel)

        self.stackbis = QStackedLayout()
        self.emptybis = QWidget()

        self.resample = QGroupBox('Re-sample lines by Maximum Length')
        self.resample.setCheckable(True)
        vlayout = QVBoxLayout()
        self.valueButton = QRadioButton('Use constant')
        self.valueBox = QLineEdit('1')
        self.choiceButton = QRadioButton('Use attribute')
        self.choiceBox = QComboBox()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.valueButton)
        hlayout.addWidget(self.valueBox)
        vlayout.addLayout(hlayout)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.choiceButton)
        hlayout.addWidget(self.choiceBox, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        self.resample.setLayout(vlayout)
        self.choiceBox.setVisible(False)
        self.valueBox.setVisible(False)
        self.resample.setChecked(False)
        self.valueButton.toggled.connect(lambda checked: self.valueBox.setVisible(checked))
        self.choiceButton.toggled.connect(lambda checked: self.choiceBox.setVisible(checked))
        self.valueButton.setChecked(True)

        self.stackbis.addWidget(self.emptybis)
        self.stackbis.addWidget(self.resample)
        self.stackbis.setCurrentIndex(1)
        # create the submit button
        self.btnSubmit = QPushButton('Submit', self, icon=self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btnSubmit.setToolTip('<b>Submit</b>')
        self.btnSubmit.setFixedSize(105, 50)

    def _bindEvents(self):
        self.btnSubmit.clicked.connect(self.btnSubmitEvent)
        self.outTypeBox.currentIndexChanged.connect(self.changeOutType)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(50, 20))
        mainLayout.addWidget(self.inputBox)
        mainLayout.addItem(QSpacerItem(50, 20))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Output file type'))
        hlayout.addWidget(self.outTypeBox, Qt.AlignLeft)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addLayout(self.stack)
        mainLayout.addItem(QSpacerItem(50, 10))
        mainLayout.addLayout(self.stackbis)
        mainLayout.addItem(QSpacerItem(50, 10))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnSubmit)
        hlayout.addWidget(self.outNameBox)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(30, 15))
        mainLayout.addWidget(QLabel('   Message logs'))
        mainLayout.addWidget(self.logTextBox.widget)
        self.setLayout(mainLayout)

    def reset(self):
        self.inputBox.clear()
        self.outTypeBox.clear()
        self.outNameBox.clear()
        self.bkshpname.setText('Value')
        self.zfieldchoice.clear()
        self.zfieldchoicebis.clear()
        self.zfieldchoiceter.clear()
        self.mfieldchoice.clear()
        self.mfieldchoicebis.clear()
        self.shpbkmethod.clear()
        self.shpbkmethod.addItem('0')
        self.shpbkmethod.addItem('Iteration')
        self.shpbkmethodbis.clear()
        self.shpbkmethodbis.addItem('0')
        self.shpbkmethodbis.addItem('Iteration')
        self.choiceBox.clear()

    def changeOutType(self, index):
        if self.outTypeBox.currentText():
            self.stack.setCurrentIndex(self.convert_type[self.input.from_type][self.outTypeBox.currentText()])

    def _check_options(self):
        current_type = self.stack.currentIndex()
        if current_type == self.BK_SHP:
            attribute_name = self.bkshpname.text()
            if not attribute_name:
                QMessageBox.critical(None, 'Error', 'The attribute name cannot be empty!', QMessageBox.Ok)
                return False, []
            options = [attribute_name]
        elif current_type == self.Z_FROM_SHP:
            options = [self.zfieldchoice.currentText()]
        elif current_type == self.M_FROM_SHP:
            options = [self.mfieldchoice.currentText()]
        elif current_type == self.SHP_BK:
            options = [self.shpbkmethod.currentText()]
        elif current_type == self.Z_AND_BK:
            options = [self.zfieldchoicebis.currentText(), self.shpbkmethodbis.currentText()]
        elif current_type == self.Z_AND_M:
            options = [self.zfieldchoiceter.currentText(), self.mfieldchoicebis.currentText()]
        else:
            options = []
        if self.stackbis.currentIndex() == 1:
            if self.resample.isChecked():
                if self.valueButton.isChecked():
                    value = self.valueBox.text()
                    try:
                        value = float(value)
                    except ValueError:
                        QMessageBox.critical(None, 'Error', 'Re-sampling Maximum Length must be a number!',
                                             QMessageBox.Ok)
                        return False, []
                    if value <= 0:
                        QMessageBox.critical(None, 'Error', 'Re-sampling Maximum Length must be a positive!',
                                             QMessageBox.Ok)
                        return False, []
                    options.append('v|' + str(value))
                else:
                    attribute = self.choiceBox.currentText()
                    if not attribute:
                        QMessageBox.critical(None, 'Error', 'No numeric attribute available for re-sampling.',
                                             QMessageBox.Ok)
                        return False, []
                    options.append('a|' + attribute)
            else:
                options.append('')
        return True, options

    def getInput(self):
        self.reset()

        from_type = self.input.from_type
        message = 'The input format is of type {}.\n'.format(from_type)
        is_line = False
        possible_types = self.convert_type[from_type].keys()

        if from_type == 'i2s' or from_type == 'i3s':
            is_line = True
            self.choiceBox.addItem('Attribute')
            nb_closed, nb_open = self.input.converter.nb_closed, self.input.converter.nb_open
            if nb_closed > 0 and nb_open > 0:
                possible_types = self.convert_type[from_type].keys()
            elif nb_closed == 0:
                if from_type == 'i2s':
                    possible_types = ['i2s', 'shp Polyline', 'csv']
                else:
                    possible_types = ['i3s', 'i2s', 'shp PolylineZ', 'csv']
            else:
                if from_type == 'i2s':
                    possible_types = ['i2s', 'shp Polygon', 'csv']
                else:
                    possible_types = ['i3s', 'i2s', 'shp PolygonZ', 'csv']
            message += 'It has {} polygon{} and {} open polyline{}.\n'.format(nb_closed, 's' if nb_closed > 1 else '',
                                                                              nb_open, 's' if nb_open > 1 else '')
        elif from_type == 'shp Point':
            numeric_fields = self.input.converter.numeric_fields
            if numeric_fields:
                self.mfieldchoicebis.addItem('0')
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.zfieldchoice.addItem(item)
                    self.zfieldchoiceter.addItem(item)
                    self.mfieldchoicebis.addItem(item)
            else:
                possible_types = ['shp Point', 'csv']

        elif from_type == 'shp PointM':
            numeric_fields = self.input.converter.numeric_fields
            self.mfieldchoice.addItem('M')
            self.mfieldchoicebis.addItem('M')
            if numeric_fields:
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.zfieldchoice.addItem(item)
                    self.zfieldchoiceter.addItem(item)
                    self.mfieldchoice.addItem(item)
                    self.mfieldchoicebis.addItem(item)
            else:
                possible_types = ['shp PointM', 'shp Point', 'csv']

        elif from_type == 'shp PointZ':
            self.zfieldchoice.addItem('Z')
            self.zfieldchoiceter.addItem('Z')
            self.mfieldchoice.addItem('M')
            self.mfieldchoicebis.addItem('M')
            numeric_fields = self.input.converter.numeric_fields
            if numeric_fields:
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.zfieldchoice.addItem(item)
                    self.zfieldchoiceter.addItem(item)
                    self.mfieldchoice.addItem(item)
                    self.mfieldchoicebis.addItem(item)

        elif from_type == 'shp Polyline' or from_type == 'shp Polygon':
            is_line = True
            numeric_fields = self.input.converter.numeric_fields
            if numeric_fields:
                self.mfieldchoicebis.addItem('0')
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.zfieldchoiceter.addItem(item)
                    self.mfieldchoicebis.addItem(item)
                    self.zfieldchoicebis.addItem(item)
                    self.shpbkmethod.addItem(item)
                    self.shpbkmethodbis.addItem(item)
                    self.choiceBox.addItem(item)
            else:
                possible_types = [from_type, 'i2s', 'csv']

        elif from_type == 'shp PolylineZ' or from_type == 'shp PolygonZ':
            is_line = True
            self.zfieldchoiceter.addItem('Z')
            self.zfieldchoicebis.addItem('Z')
            self.mfieldchoicebis.addItem('M')
            numeric_fields = self.input.converter.numeric_fields
            if numeric_fields:
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.zfieldchoiceter.addItem(item)
                    self.zfieldchoicebis.addItem(item)
                    self.mfieldchoicebis.addItem(item)
                    self.shpbkmethod.addItem(item)
                    self.shpbkmethodbis.addItem(item)
                    self.choiceBox.addItem(item)

        elif from_type == 'shp PolylineM' or from_type == 'shp PolygonM':
            is_line = True
            numeric_fields = self.input.converter.numeric_fields
            self.mfieldchoice.addItem('M')
            self.mfieldchoicebis.addItem('M')
            if numeric_fields:
                for index, name in numeric_fields:
                    item = '%d - %s' % (index, name)
                    self.mfieldchoice.addItem(item)
                    self.zfieldchoiceter.addItem(item)
                    self.zfieldchoicebis.addItem(item)
                    self.mfieldchoicebis.addItem(item)
                    self.shpbkmethod.addItem(item)
                    self.shpbkmethodbis.addItem(item)
                    self.choiceBox.addItem(item)
            else:
                possible_types = [from_type, from_type[:-1], 'i2s', 'csv']

        for to_type in possible_types:
            self.outTypeBox.addItem(to_type)

        if is_line:
            self.stackbis.setCurrentIndex(1)
        else:
            self.stackbis.setCurrentIndex(0)

        message += 'It can be converted to the following types: {}.'.format(', '.join(list(possible_types)))
        self.inputBox.appendPlainText(message)

    def btnSubmitEvent(self):
        # check the transformations options
        valid, options = self._check_options()
        if not valid:
            return

        # getting the converter options right
        if self.input.transformation is not None:
            from_index, to_index = self.input.fromBox.currentIndex(), self.input.toBox.currentIndex()
            trans = self.input.transformation.get_transformation(from_index, to_index)
            self.input.converter.set_transformations(trans)

        out_type = self.outTypeBox.currentText()
        if out_type[:3] == 'shp':
            out_type = 'shp'
        filename, _ = QFileDialog.getSaveFileName(self, 'Choose the output file name', '',
                                                  '%s Files (*.%s)' % (out_type, out_type),
                                                  options=QFileDialog.Options() | QFileDialog.DontUseNativeDialog)
        if not filename:
            return
        if len(filename) < 5 or filename[-3:] != out_type:
            filename += '.' + out_type
        if filename == self.input.converter.from_file:
            QMessageBox.critical(self, 'Error', 'Cannot overwrite to the input file.',
                                 QMessageBox.Ok)
            return
        try:
            with open(filename, 'w') as f:
                pass
        except PermissionError:
            QMessageBox.critical(self, 'Error',
                                 'Permission denied (Is the file opened by another application?).', QMessageBox.Ok)
            return None

        self.outNameBox.setText(filename)
        logging.info('Start conversion from %s\nto %s' % (self.input.converter.from_file, filename))
        QApplication.processEvents()
        try:
            self.input.converter.write(self.outTypeBox.currentText(), filename, options)
        except RuntimeError:
            QMessageBox.critical(self, 'Error',
                                 'The attribute used for re-sampling contains non-positive number.', QMessageBox.Ok)
            logging.info('Failed.')
            return None
        logging.info('Done.')
        QMessageBox.information(self, 'Success',
                                'File conversion finished successfully!', QMessageBox.Ok)


class FileConverterGUI(TelToolWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.input = FileConverterInputTab(self)
        self.output = FileConverterOutputTab(self.input)

        self.setWindowTitle('Transform and convert geometry files')

        self.tab = QTabWidget()
        self.tab.addTab(self.input, 'Input')
        self.tab.addTab(self.output, 'Output')

        self.tab.setTabEnabled(1, False)

        self.tab.setStyleSheet('QTabBar::tab { height: 40px; min-width: 200px; }')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tab)
        self.setLayout(mainLayout)

    def reset(self):
        self.output.reset()
        self.tab.setTabEnabled(1, False)

    def getInput(self):
        self.output.getInput()
        self.tab.setTabEnabled(1, True)


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
    widget = FileConverterGUI()
    widget.show()
    app.exec_()
