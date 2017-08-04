"""!
Handle 2D and 3D additional variables
"""

import numpy as np


class Variable():
    """!
    @brief Data type for a single variable with ID (short name), Name (fr or en) and Unit
    """
    def __init__(self, ID, name_fr, name_en, unit, order):
        self._ID = ID
        self.name_fr = name_fr
        self.name_en = name_en
        self._unit = unit
        self.order = order

    def __repr__(self):
        return ', '.join([self.ID(), self.name_fr,
                          self.name_en, self.unit()])

    def name(self, language):
        if language == 'fr':
            return self.name_fr
        return self.name_en

    def ID(self):
        return self._ID

    def unit(self):
        return self._unit


class Equation():
    """!
    @brief Data type for an equation consisting of N input variables, 1 output variables and (N-1) operators
    """
    def __init__(self, input_variables, output_variable, operator):
        self.input = input_variables
        self.output = output_variable
        self.operator = operator


def build_variables(spec):
    """!
    @brief Initialize the BASIC_VARIABLES
    """
    variables = {}
    for i, row in enumerate(spec.split('\n')):
        ID, name_fr, name_en, unit = row.split(',')
        variables[ID] = Variable(ID, name_fr, name_en, unit, i)
    return variables


# define common operators
def square_root(x):
    with np.errstate(invalid='ignore'):
        return np.sqrt(x)


def cubic_root(x):
    with np.errstate(invalid='ignore'):
        return np.where(x < 0, np.power(-x, 1/3.), np.power(x, 1/3.))


# define the operators (relations between variables) as constants
PLUS, MINUS, TIMES, NORM2, NORM2_3D = 1, 2, 3, 4, 104

COMMON_OPERATIONS = {
    PLUS: lambda a, b: a + b,
    MINUS: lambda a, b: a-b,
    TIMES: lambda a, b: a*b,
    NORM2: lambda a, b: np.sqrt(np.square(a) + np.square(b)),
    NORM2_3D: lambda a, b, c: np.sqrt(np.square(a) + np.square(b) + np.square(c)),
}


def do_calculation(operation_dict, equation, input_values):
    """!
    @brief Apply an equation on input values
    @param equation <Equation>: an equation object
    @param input_values <[numpy 1D-array]>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = operation_dict[equation.operator]
    nb_operands = len(input_values)
    if nb_operands == 1:
        return operation(input_values[0])
    elif nb_operands == 2:
        return operation(input_values[0], input_values[1])
    return operation(input_values[0], input_values[1], input_values[2])


def get_available_variables(computables, basic_equations):
    """!
    @brief Determine the list of new variables (2D or 3D) computable from the input variables by basic relations
    @return <[Variable]>: the list of variables computable from the input variables by basic relations
    """
    available_vars = []
    while True:
        found_new_computable = False
        for equation in basic_equations.values():
            unknown = equation.output
            needed_variables = equation.input
            if unknown in computables:  # not a new variable
                continue
            is_solvable = all(map(lambda x: x in computables, needed_variables))
            if is_solvable:
                found_new_computable = True
                computables.append(unknown)
                available_vars.append(equation.output)
        if not found_new_computable:
            break
    return available_vars

