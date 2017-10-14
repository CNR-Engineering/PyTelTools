"""!
Unittest for slf.variables module
"""

import unittest

from slf.variables import get_necessary_equations
from slf.variable.variables_2d import CHEZY_EQUATION, MANNING_EQUATION, NIKURADSE_EQUATION, STRICKLER_EQUATION

eq_name = lambda eqs: list(map(lambda x: x.output.ID(), eqs))


class VariablesTestCase(unittest.TestCase):
    def test_no_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V'], ['U'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'Q'], ['Q'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['US'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['US', 'U'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['V', 'US', 'M'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'RANDOM NAME', 'H', 'US'], ['RANDOM NAME'], True, None)), [])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'H', 'C', 'Q', 'F', 'US'], ['C'], True, None)), [])

    def test_H_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'H'], True, None)), ['H'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'S', 'V', 'B'], ['S', 'U', 'H'], True, None)), ['H'])
        self.assertEqual(eq_name(get_necessary_equations(['S', 'B'], ['H', 'U', 'S'], True, None)), ['H'])

    def test_S_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['U', 'S'], True, None)), ['S'])
        self.assertEqual(eq_name(get_necessary_equations(['H', 'Q', 'B'], ['S'], True, None)), ['S'])
        self.assertEqual(eq_name(get_necessary_equations(['Q', 'I', 'H', 'U', 'V', 'B'], ['S', 'U', 'H'], True, None)), ['S'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'B', 'J', 'I', 'Q', 'TAU', 'H', 'B'], ['H', 'S'], True, None)), ['S'])

    def test_B_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['HD', 'RB', 'H'], ['B', 'H'], True, None)), ['B'])
        self.assertEqual(eq_name(get_necessary_equations(['HD', 'H', 'S', 'TAU'], ['B', 'S'], True, None)), ['B'])
        self.assertEqual(eq_name(get_necessary_equations(['S', 'U', 'H', 'V', 'H'], ['S', 'B', 'H'], True, None)), ['B'])
        self.assertEqual(eq_name(get_necessary_equations(['DMAX', 'US', 'RB', 'H', 'Q', 'TAU', 'S', 'I'], ['H', 'B'], True, None)), ['B'])

    def test_C_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['U', 'C', 'H'], True, None)), ['C'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'S', 'Q', 'B'], ['U', 'C', 'H'], True, None)), ['H', 'C'])

    def test_F_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'M', 'B'], ['U', 'F', 'H'], True, None)), ['C', 'F'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'C', 'F'], True, None)), ['H', 'M', 'C', 'F'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'C', 'F', 'I', 'Q'], True, None)), ['H', 'M', 'C', 'F', 'I', 'J', 'Q'])

    def test_IJ_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['I'], True, None)), ['I'])
        self.assertEqual(eq_name(get_necessary_equations(['I', 'J'], ['Q'], True, None)), ['Q'])
        self.assertEqual(eq_name(get_necessary_equations(['H', 'U', 'Q', 'J'], ['H', 'I', 'Q'], True, None)), ['I'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'B', 'M'], ['J'], True, None)), ['J'])
        self.assertEqual(eq_name(get_necessary_equations(['H', 'U', 'Q', 'V', 'M'], ['M', 'Q', 'J', 'U'], True, None)), ['J'])
        self.assertEqual(eq_name(get_necessary_equations(['S', 'U', 'B', 'V', 'I'], ['M', 'Q', 'U'], True, None)), ['H', 'M', 'J', 'Q'])
        self.assertEqual(eq_name(get_necessary_equations(['S', 'U', 'B', 'V', 'M'], ['M', 'Q', 'J', 'U'], True, None)), ['H', 'I', 'J', 'Q'])

    def test_Q_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H'], ['Q'], True, None)), ['I', 'J', 'Q'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H'], ['U', 'Q', 'V'], True, None)), ['I', 'J', 'Q'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'I', 'H'], ['Q', 'I', 'U'], True, None)), ['J', 'Q'])
        self.assertEqual(eq_name(get_necessary_equations(['I', 'J', 'H', 'U', 'V', 'TAU'], ['I', 'J', 'Q'], True, None)), ['Q'])
        self.assertEqual(eq_name(get_necessary_equations(['I', 'S', 'B', 'V'], ['Q'], True, None)), ['H', 'J', 'Q'])

    def test_M_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'J', 'H', 'B', 'I'], ['U', 'H', 'V', 'M'], True, None)), ['M'])
        self.assertEqual(eq_name(get_necessary_equations(['H', 'Q', 'I', 'J', 'B'], ['M', 'U', 'B', 'H', 'Q'], True, None)), ['M'])
        self.assertEqual(eq_name(get_necessary_equations(['H', 'U', 'V', 'S', 'J', 'B'], ['Q', 'U', 'M', 'H'], True, None)), ['M', 'I', 'Q'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'S', 'J', 'B'], ['Q', 'U', 'M', 'H'], True, None)), ['H', 'M', 'I', 'Q'])

    def test_TAU_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'B', 'I'], ['TAU'], True, CHEZY_EQUATION)), ['M', 'US', 'TAU'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'Q', 'W', 'H'], ['TAU', 'Q', 'U', 'V'], True, NIKURADSE_EQUATION)), ['US', 'TAU'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'US', 'Q', 'W', 'H'], ['I', 'TAU', 'Q', 'U', 'V'], True, STRICKLER_EQUATION)), ['I', 'TAU'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'US', 'W', 'H'], ['Q', 'TAU', 'US'], True, MANNING_EQUATION)), ['I', 'J', 'Q', 'TAU'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'US', 'W', 'S', 'B'], ['Q', 'TAU'], True, STRICKLER_EQUATION)), ['H', 'I', 'J', 'Q', 'TAU'])

    def test_DMAX_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['US'], ['DMAX'], True, None)), ['TAU', 'DMAX'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'H', 'W', 'TAU', 'US'], ['DMAX'], True, None)), ['DMAX'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'B', 'I'], ['DMAX'], True, CHEZY_EQUATION)), ['M', 'US', 'TAU', 'DMAX'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'M', 'B', 'Q', 'W', 'S'], ['DMAX', 'H', 'Q', 'TAU', 'U', 'V'], True, STRICKLER_EQUATION)), ['H', 'US', 'TAU', 'DMAX'])
        self.assertEqual(eq_name(get_necessary_equations(['US', 'I', 'H', 'U', 'V'], ['M', 'DMAX', 'Q'], True, None)), ['M', 'J', 'Q', 'TAU', 'DMAX'])
        self.assertEqual(eq_name(get_necessary_equations(['US', 'I', 'H', 'U', 'V'], ['M', 'DMAX', 'Q'], True, None)), ['M', 'J', 'Q', 'TAU', 'DMAX'])

    def test_FROPT_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['US', 'MU'], ['FROTP'], True, None)), ['TAU', 'FROTP'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'MU', 'H', 'W', 'TAU', 'US'], ['FROTP'], True, None)), ['FROTP'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'MU', 'I'], ['FROTP'], True, CHEZY_EQUATION)), ['M', 'US', 'TAU', 'FROTP'])
        self.assertEqual(eq_name(get_necessary_equations(['U', 'MU', 'M', 'B', 'Q', 'W', 'S'], ['FROTP', 'DMAX', 'H', 'Q', 'TAU', 'U', 'V'], True, STRICKLER_EQUATION)), ['H', 'US', 'TAU', 'DMAX', 'FROTP'])
        self.assertEqual(eq_name(get_necessary_equations(['US', 'I', 'H', 'MU', 'V'], ['M', 'DMAX', 'Q', 'FROTP'], True, None)), ['M', 'J', 'Q', 'TAU', 'DMAX', 'FROTP'])
        self.assertEqual(eq_name(get_necessary_equations(['US', 'MU', 'H', 'U', 'V'], ['FROTP', 'M', 'DMAX', 'Q'], True, None)), ['M', 'I', 'J', 'Q', 'TAU', 'DMAX', 'FROTP'])

    def test_QS_equation(self):
        self.assertEqual(eq_name(get_necessary_equations(['HD', 'EF', 'B', 'DF'], ['B', 'QS'], True, None)), ['QS'])
        self.assertEqual(eq_name(get_necessary_equations(['EF', 'H', 'S', 'DF'], ['QS', 'S'], True, None)), ['QS'])
        self.assertEqual(eq_name(get_necessary_equations(['QSX', 'EF', 'H', 'DF', 'QSY', 'B'], ['S', 'QS', 'H'], True, None)), ['S', 'QS'])
        self.assertEqual(eq_name(get_necessary_equations(['DMAX', 'US', 'QSX', 'EF', 'Q', 'DF', 'S', 'B'], ['H', 'QS'], True, None)), ['H', 'QS'])

