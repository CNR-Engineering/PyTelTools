import sys
import os
os.chdir(os.path.dirname(os.path.realpath(__file__)))
import shutil
import uuid
import subprocess

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import slf.misc as convert


class LandXMLtoTinDialog(QDialog):
    def __init__(self, dir_names, dir_paths, slf_name, slf_headers, var):
        super().__init__()

        self.dir_paths = dir_paths
        self.slf_name = slf_name
        self.headers = slf_headers
        self.var = var

        self.table = QTableWidget()
        self.table.setRowCount(len(dir_names))
        self.table.setColumnCount(3)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['dossier', 'LandXML', 'tin'])

        yellow = QColor(245, 255, 207, 255)

        for i, name in enumerate(dir_names):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            for j in range(1, 3):
                self.table.setItem(i, j, QTableWidgetItem(''))
                self.table.item(i, j).setBackground(yellow)

        self.btnClose = QPushButton('Fermer', None)
        self.btnClose.setEnabled(False)
        self.btnClose.setFixedSize(120, 30)
        self.btnClose.clicked.connect(self.accept)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel("Patientez jusqu'à ce que toutes les cases jaunes deviennet vertes..."))
        vlayout.addWidget(self.table)
        vlayout.addStretch()
        vlayout.addWidget(self.btnClose, Qt.AlignRight)
        self.setLayout(vlayout)
        self.resize(500, 300)
        self.setWindowTitle('Convertir une variable en LandXML puis en tin')
        self.show()
        QApplication.processEvents()
        self.success = self._run()
        self.btnClose.setEnabled(True)

    def _run(self):
        green = QColor(180, 250, 165, 255)

        python_path = 'C:\\Python27\\ArcGIS10.1\\python.exe'
        if not os.path.exists(python_path):
            QMessageBox.critical(self, 'Erreur', "ArcGIS10.1 n'est pas disponible!",
                                 QMessageBox.Ok)
            return False

        script_name = os.path.abspath(os.path.join('slf', 'data', 'landxml_to_tin.py'))

        for i, (dir_path, file_header) in enumerate(zip(self.dir_paths, self.headers)):
            if not os.path.exists(os.path.join(dir_path, 'sig')):
                os.mkdir(os.path.join(dir_path, 'sig'))

            # LandXML
            xml_name = os.path.join(dir_path, 'sig', self.slf_name[:-4] + '_scalar_%s.xml' % self.var)
            if not os.path.exists(xml_name):
                convert.scalar_to_xml(os.path.join(dir_path, self.slf_name),
                                      file_header, xml_name, self.var)

            self.table.item(i, 1).setBackground(green)
            QApplication.processEvents()

            # tin
            if os.path.exists(os.path.join(dir_path, 'sig', self.slf_name[:-4] + '_scalar_%s' % self.var)):
                self.table.item(i, 2).setBackground(green)
                QApplication.processEvents()
                continue

            out = subprocess.Popen([python_path, script_name, xml_name, os.path.join(dir_path, 'sig'),
                                    self.slf_name[:-4] + '_scalar_%s' % self.var],
                                    stdout=subprocess.PIPE)
            result, returncode = out.communicate()[0], out.returncode
            if returncode == 1:
                QMessageBox.critical(self, 'Erreur', "arcpy n'est pas disponible !",
                                     QMessageBox.Ok)
                return False
            elif returncode == 2:
                QMessageBox.critical(self, 'Erreur', "L'extension ArcGIS 3D Analyst n'est pas disponible !",
                                     QMessageBox.Ok)
                return False
            elif returncode == 3:
                QMessageBox.critical(self, 'Erreur', 'LandXML_to_tin a échoué !',
                                     QMessageBox.Ok)
                return False
            self.table.item(i, 2).setBackground(green)
            QApplication.processEvents()

        return True


class MxdDialog(QDialog):
    def __init__(self, mxds):
        super().__init__()
        self.mxdBox = QComboBox()
        self.choices = []
        for name in mxds:
            for mxd, path in mxds[name]:
                item = '%s/sig/%s' % (name, mxd)
                self.mxdBox.addItem(item)
                self.choices.append((os.path.join(path, mxd), mxd[:-4]))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        vlayout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('Choisir un .mxd'))
        hlayout.addWidget(self.mxdBox, Qt.AlignLeft)
        vlayout.addLayout(hlayout)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.resize(400, 300)
        self.setWindowTitle('Choisir un .mxd')
        self.show()


class PngDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.openButton = QPushButton('Parcourir')
        self.openButton.setEnabled(False)
        self.openButton.setFixedWidth(100)
        self.openButton.clicked.connect(self._open)
        self.pathBox = QLineEdit()
        self.pathBox.setReadOnly(True)

        self.pngBox = QGroupBox('Choisir où sauvegarder les .PNG')
        self.separateButton = QRadioButton('Séparément : dans les dossiers source')
        self.separateButton.setChecked(True)
        self.togetherButton = QRadioButton('Ensemble : dans un même dossier\n'
                                           '(les images porteront le nom du dossier source)')
        self.togetherButton.toggled.connect(lambda checked: self.openButton.setEnabled(checked))
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.separateButton)
        vlayout.addWidget(self.togetherButton)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.openButton)
        hlayout.addWidget(self.pathBox)
        vlayout.addLayout(hlayout)
        self.pngBox.setLayout(vlayout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                   Qt.Horizontal, self)
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.pngBox)
        vlayout.addStretch()
        vlayout.addWidget(buttons)
        self.setLayout(vlayout)
        self.resize(400, 300)
        self.setWindowTitle('Sauvegarder les .PNG')
        self.show()

    def check(self):
        if self.togetherButton.isChecked():
            if not self.pathBox.text():
                QMessageBox.critical(self, 'Erreur', 'Choisir un dossier.',
                                     QMessageBox.Ok)
                return
        self.accept()

    def _open(self):
        path = QFileDialog.getExistingDirectory(None, 'Choisir un dossier', '',
                                                options=QFileDialog.Options() | QFileDialog.ShowDirsOnly |
                                                        QFileDialog.DontUseNativeDialog)
        if not path:
            return
        self.pathBox.setText(path)


class MxdToPngDialog(QDialog):
    def __init__(self, dir_names, dir_paths, mxd_name, mxd_path, png_together, png_path):
        super().__init__()

        self.dir_names = dir_names
        self.dir_paths = dir_paths
        self.mxd_name = mxd_name
        self.mxd_path = mxd_path
        self.png_together = png_together
        self.png_path = png_path

        self.table = QTableWidget()
        self.table.setRowCount(len(dir_names))
        self.table.setColumnCount(2)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.setHorizontalHeaderLabels(['dossier', 'png'])

        yellow = QColor(245, 255, 207, 255)

        for i, name in enumerate(dir_names):
            self.table.setItem(i, 0, QTableWidgetItem(name))

            self.table.setItem(i, 1, QTableWidgetItem(''))
            self.table.item(i, 1).setBackground(yellow)

        self.btnClose = QPushButton('Fermer', None)
        self.btnClose.setEnabled(False)
        self.btnClose.setFixedSize(120, 30)
        self.btnClose.clicked.connect(self.accept)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel("Patientez jusqu'à ce que toutes les cases jaunes deviennet vertes..."))
        vlayout.addWidget(self.table)
        vlayout.addStretch()
        vlayout.addWidget(self.btnClose, Qt.AlignRight)
        self.setLayout(vlayout)
        self.resize(500, 300)
        self.setWindowTitle('Produire les cartes sous format PNG')
        self.show()
        QApplication.processEvents()

        self.success = self._run()
        self.btnClose.setEnabled(True)

    def _png_path(self, dir_name, dir_path):
        if self.png_together:
            return self.png_path, '%s_%s.png' % (dir_name, self.mxd_name)
        return os.path.join(dir_path, 'sig'), '%s.png' % self.mxd_name

    def _run(self):
        green = QColor(180, 250, 165, 255)

        python_path = 'C:\\Python27\\ArcGIS10.1\\python.exe'
        if not os.path.exists(python_path):
            QMessageBox.critical(self, 'Erreur', "ArcGIS10.1 n'est pas disponible!",
                                 QMessageBox.Ok)
            return False

        script_name = os.path.abspath(os.path.join('slf', 'data', 'mxd_to_png.py'))
        tmp_id = str(uuid.uuid4())

        for i, (dir_name, dir_path) in enumerate(zip(self.dir_names, self.dir_paths)):
            png_folder, png_name = self._png_path(dir_name, dir_path)
            if os.path.exists(os.path.join(png_folder, png_name)):
                self.table.item(i, 1).setBackground(green)
                QApplication.processEvents()
                continue

            # copy .mxd to sig folder
            tmp_mxd = os.path.join(dir_path, 'sig', tmp_id + '.mxd')
            shutil.copy(self.mxd_path, tmp_mxd)

            # mxd to png
            out = subprocess.Popen([python_path, script_name, tmp_mxd, png_name],
                                   stdout=subprocess.PIPE)
            result, returncode = out.communicate()[0], out.returncode

            # move .png to the specified folder
            if self.png_together:
                old_path = os.path.join(dir_path, 'sig', png_name)
                shutil.move(old_path, png_folder)

            # remove .mxd
            os.remove(tmp_mxd)

            if returncode == 1:
                QMessageBox.critical(self, 'Erreur', "arcpy.mapping n'est pas disponible !",
                                     QMessageBox.Ok)
                return False
            elif returncode == 2:
                QMessageBox.critical(self, 'Erreur', "Lecture de .mxd a échoué !",
                                     QMessageBox.Ok)
                return False
            elif returncode == 3:
                QMessageBox.critical(self, 'Erreur', 'ExportToPNG a échoué !',
                                     QMessageBox.Ok)
                return False

            self.table.item(i, 1).setBackground(green)
            QApplication.processEvents()

        QMessageBox.information(self, 'Succès', 'Toutes les .PNG sont sauvegardées avec succès !',
                                QMessageBox.Ok)
        return True


class FirstStep(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.transformation = None

        self.dir_names = []
        self.dir_paths = []
        self.slf_name = ''

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create the open button
        self.btnOpen = QPushButton('Ouvrir', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Ouvrir</b> des fichiers .xml')
        self.btnOpen.setFixedSize(105, 50)

        # create a combo box for input file name
        self.fileBox = QComboBox()
        self.fileBox.setFixedSize(200, 30)

        # create the next button
        self.btnNext = QPushButton('Suivant', self, icon=self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self.btnNext.setFixedSize(105, 50)
        self.btnNext.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpen)
        hlayout.addWidget(self.btnNext)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Étape 1</b>: Choisir un ou plusieurs dossiers contenant un sous-dossier nommé gis.<br>'
                                    'Chaque dossier gis doit contenir un fichier .xml avec le même nom.<br>'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel('   Choisir les fichiers .xml  '))
        hlayout.addWidget(self.fileBox, Qt.AlignLeft)
        hlayout.addStretch()
        mainLayout.addLayout(hlayout)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnNext.clicked.connect(self.parent.first_to_second)

    def btnOpenEvent(self):
        self.btnNext.setEnabled(False)
        w = QFileDialog()
        w.setWindowTitle('Choisir un ou plusieurs dossiers contenant un sous-dossier gis')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionMode(QAbstractItemView.MultiSelection)
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        self.dir_names = []
        self.dir_paths = []
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            self.dir_names.append(name)
            self.dir_paths.append(os.path.join(current_dir, name))
        for name, path in zip(self.dir_names, self.dir_paths):
            if not os.path.exists(os.path.join(path, 'gis')):
                QMessageBox.critical(self, 'Erreur', 'Pas de sous-dossier gis dans le dossier %s !' % name,
                                     QMessageBox.Ok)
                return
        all_slfs = set()
        for name, path in zip(self.dir_names, self.dir_paths):
            slfs = set()
            for f in os.listdir(os.path.join(path, 'gis')):
                if os.path.isfile(os.path.join(path, 'gis', f)) and f[-4:] == '.xml':
                    slfs.add(f)
            if not slfs:
                QMessageBox.critical(self, 'Erreur', "Le dossier '%s/gis' ne contient pas de fichier .xml !" % name,
                                     QMessageBox.Ok)
                return
            if not all_slfs:
                all_slfs = slfs.copy()
            else:
                all_slfs.intersection_update(slfs)
            if not all_slfs:
                QMessageBox.critical(self, 'Erreur', 'Pas de fichier .xml avec un nom identique !',
                                     QMessageBox.Ok)
                return

        self.fileBox.clear()
        for slf in all_slfs:
            self.fileBox.addItem(slf)
        self.btnNext.setEnabled(True)


class SecondStep(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self._initWidgets()
        self._setLayout()
        self._bindEvents()

    def _initWidgets(self):
        # create the back button
        self.btnBack = QPushButton('Précédent', self, icon=self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self.btnBack.setFixedSize(105, 50)

        # create the next button
        self.btnNext = QPushButton('Suivant', self, icon=self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self.btnNext.setFixedSize(105, 50)

        # create a combo box for variable selection
        self.varBox = QComboBox()
        self.varBox.setFixedSize(200, 30)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnBack)
        hlayout.addWidget(self.btnNext)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Étape 2</b>: Conversion vers tin.<br>'
                                    'Les fichiers tin seront dans le dossier <i>sig/nom_entrée/</i>.'))
        mainLayout.addLayout(hlayout)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def _bindEvents(self):
        self.btnBack.clicked.connect(lambda _: self.parent.steps.setCurrentIndex(1))
        self.btnNext.clicked.connect(self.next)

    def first_to_second(self):
        self.varBox.clear()
        self.varBox.addItem('None')

    def next(self):
        dlg = LandXMLtoTinDialog(self.parent.first_step.dir_names, self.parent.first_step.dir_paths)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.success:
                self.parent.steps.setCurrentIndex(3)


class FinalStep(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self._initWidgets()
        self._setLayout()

    def _initWidgets(self):
        # create the back button
        self.btnBack = QPushButton('Précédent', self, icon=self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self.btnBack.setFixedSize(105, 50)
        self.btnBack.clicked.connect(lambda _: self.parent.steps.setCurrentIndex(2))

        # create the carto button
        self.btnCarto = QPushButton('Carto', self, icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCarto.setFixedSize(105, 50)
        self.btnCarto.clicked.connect(self.carto)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnBack)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Étape 4</b>: Préparer le fichier .mxd dans un des dossiers.<br>'
                                    'Enregister les propriétés de la carte en utilisant les chemins relatifs<br>'
                                    'puis cliquer sur <b>Carto</b>'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnCarto)
        mainLayout.addLayout(hlayout)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def carto(self):
        mxds = {}
        found = False
        for name, path in zip(self.parent.first_step.dir_names, self.parent.first_step.dir_paths):
            mxds[name] = []
            sig_path = os.path.join(path, 'sig')
            for f in os.listdir(sig_path):
                if os.path.isfile(os.path.join(sig_path, f)) and f[-4:] == '.mxd':
                    found = True
                    mxds[name].append((f, sig_path))
        if not found:
            QMessageBox.critical(self, 'Erreur', 'Les dossiers sig/ ne contiennent aucun .mxd !',
                                 QMessageBox.Ok)
            return

        first_dialog = MxdDialog(mxds)
        if first_dialog.exec_() == QDialog.Rejected:
            return
        mxd_path, mxd_name = first_dialog.choices[first_dialog.mxdBox.currentIndex()]

        second_diaglog = PngDialog()
        if second_diaglog.exec_() == QDialog.Rejected:
            return
        together, png_path = False, ''
        if second_diaglog.togetherButton.isChecked():
            together = True
            png_path = second_diaglog.pathBox.text()

        final_dialog = MxdToPngDialog(self.parent.first_step.dir_names, self.parent.first_step.dir_paths,
                                      mxd_name, mxd_path, together, png_path)
        final_dialog.exec_()


class FourStepsGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.first_step = FirstStep(self)
        self.second_step = SecondStep(self)
        self.last_step = FinalStep(self)

        self.steps = QStackedLayout()
        self.steps.addWidget(self.first_step)
        self.steps.addWidget(self.second_step)
        self.steps.addWidget(self.third_step)
        self.steps.addWidget(self.last_step)

        self.steps.setCurrentIndex(0)
        self.setLayout(self.steps)
        self.setWindowTitle('Transformer and convertir les fichiers .xml en .PNG')

        self.headers = []

    def first_to_second(self):
        self.steps.setCurrentIndex(1)

    def second_to_third(self):
        self.third_step.second_to_third()
        self.steps.setCurrentIndex(2)


class OneStepGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.dir_names = []
        self.dir_paths = []

        self._initWidgets()
        self._setLayout()
        self.btnOpen.clicked.connect(self.btnOpenEvent)
        self.btnCarto.clicked.connect(self.carto)

    def _initWidgets(self):
        self.btnOpen = QPushButton('Ouvrir', self, icon=self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btnOpen.setToolTip('<b>Ouvrir</b> des dossiers sources contenant les dossiers sig')
        self.btnOpen.setFixedSize(105, 50)

        # create the carto button
        self.btnCarto = QPushButton('Carto', self, icon=self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btnCarto.setFixedSize(105, 50)
        self.btnCarto.clicked.connect(self.carto)
        self.btnCarto.setEnabled(False)

    def _setLayout(self):
        mainLayout = QVBoxLayout()
        mainLayout.addItem(QSpacerItem(10, 10))
        mainLayout.setSpacing(15)

        mainLayout.addItem(QSpacerItem(10, 15))
        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Étape 1</b>: Choisir un ou plusieurs dossiers.<br>'
                                    'Chaque dossier doit contenir un sous-dossier sig contenant les couches.<br>'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnOpen)
        mainLayout.addLayout(hlayout)
        mainLayout.addItem(QSpacerItem(10, 10))

        mainLayout.addWidget(QLabel('<p style="font-size:10pt">'
                                    '<b>Étape 2</b>: Préparer le fichier .mxd dans un des dossiers.<br>'
                                    'Enregister les propriétés de la carte en utilisant les chemins relatifs<br>'
                                    'puis cliquer sur <b>Carto</b>'))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btnCarto)
        mainLayout.addLayout(hlayout)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def btnOpenEvent(self):
        self.btnCarto.setEnabled(False)
        w = QFileDialog()
        w.setWindowTitle('Choisir un ou plusieurs dossiers')
        w.setFileMode(QFileDialog.DirectoryOnly)
        w.setOption(QFileDialog.DontUseNativeDialog, True)
        tree = w.findChild(QTreeView)
        if tree:
            tree.setSelectionMode(QAbstractItemView.MultiSelection)
            tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        if w.exec_() != QDialog.Accepted:
            return
        current_dir = w.directory().path()
        self.dir_names = []
        self.dir_paths = []
        for index in tree.selectionModel().selectedRows():
            name = tree.model().data(index)
            self.dir_names.append(name)
            self.dir_paths.append(os.path.join(current_dir, name))
            if not os.path.exists(os.path.join(current_dir, name, 'sig')):
                QMessageBox.critical(self, 'Erreur', "Le dossier %s n'a pas de sous-dossier sig!" % name,
                                     QMessageBox.Ok)
                return
        self.btnCarto.setEnabled(True)

    def carto(self):
        mxds = {}
        found = False
        for name, path in zip(self.dir_names, self.dir_paths):
            mxds[name] = []
            sig_path = os.path.join(path, 'sig')
            for f in os.listdir(sig_path):
                if os.path.isfile(os.path.join(sig_path, f)) and f[-4:] == '.mxd':
                    found = True
                    mxds[name].append((f, sig_path))
        if not found:
            QMessageBox.critical(self, 'Erreur', 'Les dossiers sig/ ne contiennent aucun .mxd !',
                                 QMessageBox.Ok)
            return

        first_dialog = MxdDialog(mxds)
        if first_dialog.exec_() == QDialog.Rejected:
            return
        mxd_path, mxd_name = first_dialog.choices[first_dialog.mxdBox.currentIndex()]

        second_diaglog = PngDialog()
        if second_diaglog.exec_() == QDialog.Rejected:
            return
        together, png_path = False, ''
        if second_diaglog.togetherButton.isChecked():
            together = True
            png_path = second_diaglog.pathBox.text()

        final_dialog = MxdToPngDialog(self.dir_names, self.dir_paths,
                                      mxd_name, mxd_path, together, png_path)
        final_dialog.exec_()


class WelcomeToCarto(QDialog):
    def __init__(self):
        super().__init__()
        self.choice = None
        left_button = QPushButton("J'ai des dossiers contenant des fichiers .xml\n"
                                  "J'aimerais produire les fichiers tin\npuis produire des cartes")
        right_button = QPushButton("J'ai déjà toutes les couches .shp et tin\n"
                                   "J'aimerais refaire d'autres cartes avec différents .mxd")
        for bt in [left_button, right_button]:
            bt.setFixedSize(300, 150)

        left_button.clicked.connect(self.choose_left)
        right_button.clicked.connect(self.choose_right)

        vlayout = QVBoxLayout()
        vlayout.addWidget(left_button)
        vlayout.addWidget(right_button)
        self.setLayout(vlayout)
        self.setWindowTitle("Bienvenue à l'outil Carto !")

    def choose_left(self):
        self.choice = 1
        self.accept()

    def choose_right(self):
        self.choice = 2
        self.accept()


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
    dlg = WelcomeToCarto()
    value = dlg.exec_()
    if value == QDialog.Accepted:
        if dlg.choice == 1:
            widget = FourStepsGUI()
        else:
            widget = OneStepGUI()
        widget.show()
    else:
        sys.exit(0)
    app.exec_()


