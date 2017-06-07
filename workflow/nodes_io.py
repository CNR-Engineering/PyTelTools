from workflow.Node import SingleOutputNode, SingleInputNode


class ReadSerafinNode(SingleOutputNode):
    def __init__(self, index):
        super().__init__(index, 'Load Serafin')
        self.out_port.data_type = 'slf'


class WriteSerafinNode(SingleInputNode):
    def __init__(self, index):
        super().__init__(index, 'Write Serafin')
        self.in_port.data_type = 'slf'
