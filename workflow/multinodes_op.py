from datetime import datetime
from workflow.MultiNode import MultiNode, MultiOneInOneOutNode
import slf.variables as variables


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


class MultiSelectTimeNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nTime'

    def load(self, options):
        str_start_date, str_end_date = options[0:2]
        if not str_start_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        start_date = datetime.strptime(str_start_date, '%Y/%m/%d %H:%M:%S')
        end_date = datetime.strptime(str_end_date, '%Y/%m/%d %H:%M:%S')
        sampling_frequency = int(options[2])
        self.options = (start_date, end_date, sampling_frequency)


class MultiSelectSingleFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nSingle\nFrame'

    def load(self, options):
        str_date = options[0]
        if not str_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (datetime.strptime(str_date, '%Y/%m/%d %H:%M:%S'),)


class MultiSelectVariablesNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nVariables'

    def load(self, options):
        friction_law, vars, names, units = options
        friction_law = int(friction_law)
        if friction_law > -1:
            us_equation = variables.get_US_equation(friction_law)
        else:
            us_equation = None

        if not vars:
            self.state = MultiNode.NOT_CONFIGURED
            return

        selected_vars = []
        selected_vars_names = {}
        for var, name, unit in zip(vars.split(','), names.split(','), units.split(',')):
            selected_vars.append(var)
            selected_vars_names[var] = (bytes(name, 'utf-8').ljust(16), bytes(unit, 'utf-8').ljust(16))
        self.options = (us_equation, selected_vars, selected_vars_names)


class MultiAddRouseNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nRouse'

    def load(self, options):
        values, str_table = options
        str_table = str_table.split(',')
        table = []
        if not values:
            self.state = MultiNode.NOT_CONFIGURED
            return
        for i in range(0, len(str_table), 3):
            table.append([str_table[i], str_table[i+1], str_table[i+2]])
        self.options = (table,)

