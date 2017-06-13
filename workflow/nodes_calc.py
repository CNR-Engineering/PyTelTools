from workflow.Node import OneInOneOutNode


class ComputeVolumeNode(OneInOneOutNode):
    def __init__(self, index):
        super().__init__(index, 'Compute\nVolume')
        self.out_port.data_type = 'csv'
        self.in_port.data_type = 'slf'


