from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from workflow.MultiNode import MultiOneInOneOutNode


class MultiComputeMaxNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max'


class MultiComputeMinNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min'


class MultiSelectLastFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nLast\nFrame'
