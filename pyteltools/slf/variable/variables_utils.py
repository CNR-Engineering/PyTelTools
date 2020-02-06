"""!
Handle 2D and 3D additional variables
"""

import numpy as np


# define constants
KARMAN = 0.4
RHO_WATER = 1000.
GRAVITY = 9.80665


class Variable:
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


class Equation:
    """!
    @brief Data type for an equation consisting of N input variables, 1 output variables and (N-1) operators
    """
    def __init__(self, input_variables, output_variable, operator):
        self.input = input_variables
        self.output = output_variable
        self.operator = operator

    def __repr__(self):
        return "%s -> %s (%s)" % (self.input, self.output, self.operator)


def build_variables(spec):
    """!
    @brief Initialize the BASIC_VARIABLES
    """
    variables = {}
    for i, row in enumerate(spec.split('\n')):
        ID, name_fr, name_en, unit = row.split(',')
        variables[ID] = Variable(ID, name_fr, name_en, unit, i)
    return variables


def square_root(x):
    with np.errstate(invalid='ignore'):
        return np.sqrt(x)


def cubic_root(x):
    with np.errstate(invalid='ignore'):
        return np.where(x < 0, np.power(-x, 1/3.), np.power(x, 1/3.))


def compute_NIKURADSE(w, h, m):
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.sqrt(np.power(m, 2) * KARMAN**2 / np.power(np.log(30 * h / np.exp(1) / w), 2))


def compute_DMAX(tau):
    return np.where(tau > 0.34, 1.4593 * np.power(tau, 0.979),
                    np.where(tau > 0.1, 1.2912 * np.power(tau, 2) + 1.3572 * tau - 0.1154,
                             0.9055 * np.power(tau, 1.3178)))


def compute_COMPONENT_X(scalar, x, y):
    magnitude = np.sqrt(np.power(x, 2) + np.power(y, 2))
    return np.where(magnitude > 0, scalar * x/magnitude, 0)


def compute_COMPONENT_Y(scalar, x, y):
    return compute_COMPONENT_X(scalar, y, x)


PLUS, MINUS, TIMES, NORM2, NORM2_3D = 1, 2, 3, 4, 104
COMPUTE_TAU, COMPUTE_DMAX = 5, 6
COMPUTE_CHEZY, COMPUTE_STRICKLER, COMPUTE_MANNING, COMPUTE_NIKURADSE = 7, 8, 9, 10
COMPUTE_C, COMPUTE_F = 11, 12
COMPUTE_COMPONENT_X, COMPUTE_COMPONENT_Y = 20, 21

OPERATIONS = {
    PLUS: lambda a, b: a + b,
    MINUS: lambda a, b: a-b,
    TIMES: lambda a, b: a*b,
    NORM2: lambda a, b: np.sqrt(np.square(a) + np.square(b)),
    NORM2_3D: lambda a, b, c: np.sqrt(np.square(a) + np.square(b) + np.square(c)),
    COMPUTE_TAU: lambda x: RHO_WATER * np.square(x),
    COMPUTE_DMAX: compute_DMAX,
    COMPUTE_CHEZY: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w)),
    COMPUTE_STRICKLER: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w) / cubic_root(h)),
    COMPUTE_MANNING: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY * np.power(w, 2) / cubic_root(h)),
    COMPUTE_NIKURADSE: compute_NIKURADSE,
    COMPUTE_COMPONENT_X: compute_COMPONENT_X,
    COMPUTE_COMPONENT_Y: compute_COMPONENT_Y,
    COMPUTE_C: lambda h: square_root(GRAVITY * h),
    COMPUTE_F: lambda m, c: m / c
}


def do_calculation(equation, input_values):
    """!
    @brief Apply an equation on input values
    @param equation <Equation>: an equation object
    @param input_values <[numpy 1D-array]>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    nb_operands = len(input_values)
    if nb_operands == 1:
        with np.errstate(divide='ignore', invalid='ignore'):
            return operation(input_values[0])
    elif nb_operands == 2:
        with np.errstate(divide='ignore', invalid='ignore'):
            return operation(input_values[0], input_values[1])
    with np.errstate(divide='ignore', invalid='ignore'):
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
