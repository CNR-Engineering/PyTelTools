"""
Handle variables and their relationships in .slf files
"""


import numpy as np


class Variable():
    """
    @brief: Data type for a single variable with ID (short name), Name (fr or en) and Unit
    """
    def __init__(self, ID, name_fr, name_en, unit):
        self._ID = ID
        self.name_fr = name_fr
        self.name_en = name_en
        self._unit = unit

    def __repr__(self):
        return ', '.join([self.ID, self.name_fr.decode('utf-8'),
                          self.name_en.decode('utf-8'), self.unit.decode('utf-8')])

    def name(self, language):
        if language == 'fr':
            return self.name_fr
        return self.name_en

    def ID(self):
        return self._ID

    def unit(self):
        return self._unit


class Equation():
    """
    @brief: Data type for an equation consisting of N input variables, 1 output variables and (N-1) operators
    """
    def __init__(self, input_variables, output_variable, operators):
        self.input = input_variables
        self.output = output_variable
        self.operators = operators


def build_basic_variables():
    """
    @brief: Initialize the BASIC_VARIABLES constant
    """
    spec = """U,VITESSE U,VELOCITY U,M/S
V,VITESSE V,VELOCITY V,M/S
H,HAUTEUR D'EAU,WATER DEPTH,M
S,SURFACE LIBRE,FREE SURFACE,M
B,FOND ,BOTTOM,M
Q,DEBIT SCALAIRE,SCALAR FLOWRATE,M2/S
I,DEBIT SUIVANT X,FLOWRATE ALONG X,M2/S
J,DEBIT SUIVANT Y,FLOWRATE ALONG Y,M2/S
M,VITESSE SCALAIRE,SCALAR VELOCITY,M/S"""

    for i, row in enumerate(spec.split('\n')):
        ID, name_fr, name_en, unit = row.split(',')
        BASIC_VARIABLES[ID] = Variable(ID, bytes(name_fr, 'utf-8').ljust(16), bytes(name_en, 'utf-8').ljust(16),
                                       bytes(unit, 'utf-8').ljust(16))


# basic variables are stored as constants in a dictionary with ordered keys
BASIC_VARIABLES = {}
ordered_IDs = ['H', 'U', 'V', 'M', 'S', 'B', 'I', 'J', 'Q']


# construct the variable types as constants
build_basic_variables()
H, U, V, M, S, B, I, J, Q = [BASIC_VARIABLES[var] for var in ordered_IDs]


# construct the equations (relations between variables) as constants
MINUS, TIMES, NORM2 = 0, 1, 2
OPERATIONS = {MINUS: lambda a, b: a-b,
              TIMES: lambda a, b: a*b,
              NORM2: lambda a, b: np.sqrt(np.square(a) + np.square(b))}


EQUATIONS = [Equation((S, B), H, (MINUS,)), Equation((H, B), S, (MINUS,)),
             Equation((U, V), M, (NORM2,)), Equation((H, U), I, (TIMES,)),
             Equation((H, V), J, (TIMES,)), Equation((I, J), Q, (NORM2,))]


def is_basic_variable(var_ID):
    """
    @brief: determine if the input variable is a basic variable
    @param var_ID <str>: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the nine basic variables
    """
    return var_ID in ordered_IDs


def get_additional_computations(input_var_IDs):
    computables = list(map(BASIC_VARIABLES.get, filter(is_basic_variable, input_var_IDs)))
    computations = []
    while True:
        found_new_computable = False
        for equation in EQUATIONS:
            unknown = equation.output
            needed_variables = equation.input
            if unknown in computables:  # not a new variable
                continue
            is_solvable = all(map(lambda x: x in computables, needed_variables))
            if is_solvable:
                found_new_computable = True
                computables.append(unknown)
                computations.append(equation)
        if not found_new_computable:
            break
    return computations


