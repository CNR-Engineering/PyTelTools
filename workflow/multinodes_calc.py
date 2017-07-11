
from workflow.MultiNode import MultiNode, MultiTwoInOneOutNode


class MultiComputeVolumeNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nVolume'
        self.auxiliary_data = None

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
        self.options = (first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite)

    def update_input(self, nb_input):
        self.expected_input = (nb_input, 1)

    def get_auxiliary_data(self, data):
        self.auxiliary_data = data
