import numpy as np

from pyteltools.slf import Serafin


class TestHeader(Serafin.SerafinHeader):
    def __init__(self):
        super().__init__(title='DUMMY SERAFIN', format_type='SERAFIND')

        self.nb_elements = 3
        self.nb_nodes = 4
        self.nb_nodes_2d = self.nb_nodes
        self.nb_nodes_per_elem = 3

        self.ikle = np.array([1, 2, 4, 1, 3, 4, 2, 3, 4], dtype=np.int)
        self.x_stored = np.array([3, 0, 6, 3], dtype=np.float)
        self.y_stored = np.array([6, 0, 0, 2], dtype=np.float)

        self._compute_mesh_coordinates()
        self._build_ikle_2d()
        self.build_ipobo()
