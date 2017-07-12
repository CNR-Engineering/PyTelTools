import os
from workflow.MultiNode import MultiNode, MultiDoubleInputNode


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


