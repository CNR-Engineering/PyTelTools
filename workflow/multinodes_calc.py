import os
import slf.misc as operations
from workflow.MultiNode import MultiNode, MultiOneInOneOutNode, MultiDoubleInputNode


class MultiArrivalDurationNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nArrival\nDuration'

    def load(self, options):
        table = []
        conditions = []
        str_conditions, str_table, time_unit = options
        str_table = str_table.split(',')
        for i in range(int(len(str_table)/3)):
            line = []
            for j in range(3):
                line.append(str_table[3*i+j])
            table.append(line)
        str_conditions = str_conditions.split(',')
        for i, condition in zip(range(len(table)), str_conditions):
            literal = table[i][0]
            condition = condition.split()
            expression = condition[:-2]
            comparator = condition[-2]
            threshold = float(condition[-1])
            conditions.append(operations.Condition(expression, literal, comparator, threshold))
        self.options = (table, conditions, time_unit)


class MultiComputeVolumeNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nVolume'

    def load(self, options):
        first, second, sup = options[0:3]
        suffix = options[3]
        in_source_folder = bool(int(options[4]))
        dir_path = options[5]
        double_name = bool(int(options[6]))
        overwrite = bool(int(options[7]))
        if first:
            first_var = first
        else:
            self.state = MultiNode.NOT_CONFIGURED
            return
        if second:
            second_var = second
        else:
            second_var = None
        sup_volume = bool(int(sup))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiComputeFluxNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nFlux'

    def load(self, options):
        flux_options = options[0]
        if not flux_options:
            self.state = MultiNode.NOT_CONFIGURED
            return
        suffix = options[1]
        in_source_folder = bool(int(options[2]))
        dir_path = options[3]
        double_name = bool(int(options[4]))
        overwrite = bool(int(options[5]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (flux_options, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiInterpolateOnPointsNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\non\nPoints'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiInterpolateAlongLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\nalong\nLines'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiProjectLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Project\nLines'

    def load(self, options):
        suffix = options[0]
        in_source_folder = bool(int(options[1]))
        dir_path = options[2]
        double_name = bool(int(options[3]))
        overwrite = bool(int(options[4]))
        if not in_source_folder:
            if not os.path.exists(dir_path):
                self.state = MultiNode.NOT_CONFIGURED
                return
        reference_index = int(options[5])
        if reference_index == -1:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite, reference_index)


