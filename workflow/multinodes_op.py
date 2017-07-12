from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from workflow.MultiNode import MultiOneInOneOutNode


class MultiConvertToSinglePrecisionNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Convert to\nSingle\nPrecision'


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


class MultiComputeMeanNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Mean'


class MultiSelectFirstFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nFirst\nFrame'


class MultiSelectLastFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nLast\nFrame'
