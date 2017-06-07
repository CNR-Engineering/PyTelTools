"""!
Unittest for slf.variables module
"""


import unittest
from slf.variables import *

equation_name = lambda eqs: list(map(lambda x: x.output.ID(), eqs))


class VariablesTestCase(unittest.TestCase):
    def test_no_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V'], ['U'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'Q'], ['Q'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['US'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['US', 'U'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'H', 'US'], ['V', 'US', 'M'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'RANDOM NAME', 'H', 'US'], ['RANDOM NAME'], None)), [])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'H', 'C', 'Q', 'F', 'US'], ['C'], None)), [])

    def test_H_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'H'], None)), ['H'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'S', 'V', 'B'], ['S', 'U', 'H'], None)), ['H'])
        self.assertEqual(equation_name(get_necessary_equations(['S', 'B'], ['H', 'U', 'S'], None)), ['H'])

    def test_S_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['U', 'S'], None)), ['S'])
        self.assertEqual(equation_name(get_necessary_equations(['H', 'Q', 'B'], ['S'], None)), ['S'])
        self.assertEqual(equation_name(get_necessary_equations(['Q', 'I', 'H', 'U', 'V', 'B'], ['S', 'U', 'H'], None)), ['S'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'B', 'J', 'I', 'Q', 'TAU', 'H', 'B'], ['H', 'S'], None)), ['S'])

    def test_B_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['HD', 'RB', 'H'], ['B', 'H'], None)), ['B'])
        self.assertEqual(equation_name(get_necessary_equations(['HD', 'H', 'S', 'TAU'], ['B', 'S'], None)), ['B'])
        self.assertEqual(equation_name(get_necessary_equations(['S', 'U', 'H', 'V', 'H'], ['S', 'B', 'H'], None)), ['B'])
        self.assertEqual(equation_name(get_necessary_equations(['DMAX', 'US', 'RB', 'H', 'Q', 'TAU', 'S', 'I'], ['H', 'B'], None)), ['B'])

    def test_C_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['U', 'C', 'H'], None)), ['C'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'S', 'Q', 'B'], ['U', 'C', 'H'], None)), ['H', 'C'])

    def test_F_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'M', 'B'], ['U', 'F', 'H'], None)), ['C', 'F'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'C', 'F'], None)), ['H', 'M', 'C', 'F'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'S', 'B'], ['U', 'C', 'F', 'I', 'Q'], None)), ['H', 'M', 'C', 'F', 'I', 'J', 'Q'])

    def test_IJ_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'B'], ['I'], None)), ['I'])
        self.assertEqual(equation_name(get_necessary_equations(['I', 'J'], ['Q'], None)), ['Q'])
        self.assertEqual(equation_name(get_necessary_equations(['H', 'U', 'Q', 'J'], ['H', 'I', 'Q'], None)), ['I'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'B', 'M'], ['J'], None)), ['J'])
        self.assertEqual(equation_name(get_necessary_equations(['H', 'U', 'Q', 'V', 'M'], ['M', 'Q', 'J', 'U'], None)), ['J'])
        self.assertEqual(equation_name(get_necessary_equations(['S', 'U', 'B', 'V', 'I'], ['M', 'Q', 'U'], None)), ['H', 'M', 'J', 'Q'])
        self.assertEqual(equation_name(get_necessary_equations(['S', 'U', 'B', 'V', 'M'], ['M', 'Q', 'J', 'U'], None)), ['H', 'I', 'J', 'Q'])

    def test_Q_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H'], ['Q'], None)), ['I', 'J', 'Q'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H'], ['U', 'Q', 'V'], None)), ['I', 'J', 'Q'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'I', 'H'], ['Q', 'I', 'U'], None)), ['J', 'Q'])
        self.assertEqual(equation_name(get_necessary_equations(['I', 'J', 'H', 'U', 'V', 'TAU'], ['I', 'J', 'Q'], None)), ['Q'])
        self.assertEqual(equation_name(get_necessary_equations(['I', 'S', 'B', 'V'], ['Q'], None)), ['H', 'J', 'Q'])

    def test_M_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'J', 'H', 'B', 'I'], ['U', 'H', 'V', 'M'], None)), ['M'])
        self.assertEqual(equation_name(get_necessary_equations(['H', 'Q', 'I', 'J', 'B'], ['M', 'U', 'B', 'H', 'Q'], None)), ['M'])
        self.assertEqual(equation_name(get_necessary_equations(['H', 'U', 'V', 'S', 'J', 'B'], ['Q', 'U', 'M', 'H'], None)), ['M', 'I', 'Q'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'S', 'J', 'B'], ['Q', 'U', 'M', 'H'], None)), ['H', 'M', 'I', 'Q'])

    def test_TAU_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'B', 'I'], ['TAU'], CHEZY_EQUATION)), ['M', 'US', 'TAU'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'Q', 'W', 'H'], ['TAU', 'Q', 'U', 'V'], NIKURADSE_EQUATION)), ['US', 'TAU'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'US', 'Q', 'W', 'H'], ['I', 'TAU', 'Q', 'U', 'V'], STRICKLER_EQUATION)), ['I', 'TAU'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'US', 'W', 'H'], ['Q', 'TAU', 'US'], MANNING_EQUATION)), ['I', 'J', 'Q', 'TAU'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'US', 'W', 'S', 'B'], ['Q', 'TAU'], STRICKLER_EQUATION)), ['H', 'I', 'J', 'Q', 'TAU'])

    def test_DMAX_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['US'], ['DMAX'], None)), ['TAU', 'DMAX'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'H', 'W', 'TAU', 'US'], ['DMAX'], None)), ['DMAX'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'B', 'I'], ['DMAX'], CHEZY_EQUATION)), ['M', 'US', 'TAU', 'DMAX'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'M', 'B', 'Q', 'W', 'S'], ['DMAX', 'H', 'Q', 'TAU', 'U', 'V'], STRICKLER_EQUATION)), ['H', 'US', 'TAU', 'DMAX'])
        self.assertEqual(equation_name(get_necessary_equations(['US', 'I', 'H', 'U', 'V'], ['M', 'DMAX', 'Q'], None)), ['M', 'J', 'Q', 'TAU', 'DMAX'])
        self.assertEqual(equation_name(get_necessary_equations(['US', 'I', 'H', 'U', 'V'], ['M', 'DMAX', 'Q'], None)), ['M', 'J', 'Q', 'TAU', 'DMAX'])

    def test_FROPT_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['US', 'MU'], ['FROTP'], None)), ['TAU', 'FROTP'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'MU', 'H', 'W', 'TAU', 'US'], ['FROTP'], None)), ['FROTP'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'V', 'J', 'W', 'H', 'MU', 'I'], ['FROTP'], CHEZY_EQUATION)), ['M', 'US', 'TAU', 'FROTP'])
        self.assertEqual(equation_name(get_necessary_equations(['U', 'MU', 'M', 'B', 'Q', 'W', 'S'], ['FROTP', 'DMAX', 'H', 'Q', 'TAU', 'U', 'V'], STRICKLER_EQUATION)), ['H', 'US', 'TAU', 'DMAX', 'FROTP'])
        self.assertEqual(equation_name(get_necessary_equations(['US', 'I', 'H', 'MU', 'V'], ['M', 'DMAX', 'Q', 'FROTP'], None)), ['M', 'J', 'Q', 'TAU', 'DMAX', 'FROTP'])
        self.assertEqual(equation_name(get_necessary_equations(['US', 'MU', 'H', 'U', 'V'], ['FROTP', 'M', 'DMAX', 'Q'], None)), ['M', 'I', 'J', 'Q', 'TAU', 'DMAX', 'FROTP'])

    def test_QS_equation(self):
        self.assertEqual(equation_name(get_necessary_equations(['HD', 'EF', 'B', 'DF'], ['B', 'QS'], None)), ['QS'])
        self.assertEqual(equation_name(get_necessary_equations(['EF', 'H', 'S', 'DF'], ['QS', 'S'], None)), ['QS'])
        self.assertEqual(equation_name(get_necessary_equations(['QSX', 'EF', 'H', 'DF', 'QSY', 'B'], ['S', 'QS', 'H'], None)), ['S', 'QS'])
        self.assertEqual(equation_name(get_necessary_equations(['DMAX', 'US', 'QSX', 'EF', 'Q', 'DF', 'S', 'B'], ['H', 'QS'], None)), ['H', 'QS'])

