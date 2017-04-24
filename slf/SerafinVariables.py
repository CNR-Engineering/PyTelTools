"""
Handle variables and their relationships in .slf files
"""


import numpy as np

KARMAN = 0.4
RHO_EAU = 1000.
GRAVITY = 9.80665


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
    def __init__(self, input_variables, output_variable, operator):
        self.input = input_variables
        self.output = output_variable
        self.operator = operator


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
US = Variable('US', bytes('VITESSE DE FROT.', 'utf-8').ljust(16), bytes('FRICTION VEL.', 'utf-8').ljust(16), bytes('M/S', 'utf-8').ljust(16))
TAU = Variable('TAU', bytes('CONTRAINTE', 'utf-8').ljust(16), bytes('CONSTRAINT', 'utf-8').ljust(16), bytes('PA', 'utf-8').ljust(16))
DMAX = Variable('DMAX', bytes('DIAMETRE', 'utf-8').ljust(16), bytes('DIAMETER', 'utf-8').ljust(16), bytes('MM', 'utf-8').ljust(16))
W = Variable('W', bytes('FROTTEMEN', 'utf-8').ljust(16), bytes('BOTTOM FRICTION', 'utf-8').ljust(16), bytes('  ', 'utf-8').ljust(16))


# define a special operator
def compute_DMAX(tau):
    return np.where(tau > 0.34, 1.4593 * np.power(tau, 0.979),
                                np.where(tau > 0.1, 1.2912 * np.power(tau, 2) + 1.3572 * tau - 0.1154,
                                                    0.9055 * np.power(tau, 1.3178)))

# define the operators (relations between variables) as constants
MINUS, TIMES, NORM2 = 0, 1, 2
COMPUTE_TAU, COMPUTE_DMAX = 3, 4
COMPUTE_CHEZY, COMPUTE_STRICKLER, COMPUTE_MANNING, COMPUTE_NIKURADSE = 5, 6, 7, 8
OPERATIONS = {MINUS: lambda a, b: a-b,
              TIMES: lambda a, b: a*b,
              NORM2: lambda a, b: np.sqrt(np.square(a) + np.square(b)),
              COMPUTE_TAU: lambda x: RHO_EAU * np.square(x),
              COMPUTE_DMAX: compute_DMAX,
              COMPUTE_CHEZY: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w)),
              COMPUTE_STRICKLER: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w) / np.power(h, 1/3.)),
              COMPUTE_MANNING: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY * np.power(w, 2) / np.power(h, 1/3.)),
              COMPUTE_NIKURADSE: lambda w, h, m: np.sqrt(np.power(m, 2) * KARMAN**2 / np.power(np.log(30 * h / np.exp(1) / w), 2))}

# define basic equations (binary) and special equations (unary and ternary)
BASIC_EQUATIONS = {'H': Equation((S, B), H, MINUS), 'S': Equation((H, B), S, MINUS),
                   'M': Equation((U, V), M, NORM2), 'I': Equation((H, U), I, TIMES),
                   'J': Equation((H, V), J, TIMES), 'Q': Equation((I, J), Q, NORM2)}
TAU_EQUATION = Equation((US,), TAU, COMPUTE_TAU)
DMAX_EQUATION = Equation((TAU,), DMAX, COMPUTE_DMAX)

CHEZY_EQUATION = Equation((W, H, M), US, COMPUTE_CHEZY)
STRICKLER_EQUATION = Equation((W, H, M), US, COMPUTE_STRICKLER)
MANNING_EQUATION = Equation((W, H, M), US, COMPUTE_MANNING)
NIKURADSE_EQUATION = Equation((W, H, M), US, COMPUTE_NIKURADSE)


def is_basic_variable(var_ID):
    """
    @brief: determine if the input variable is a basic variable
    @param var_ID <str>: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the nine basic variables
    """
    return var_ID in ordered_IDs


def do_unary_calculation(equation, input_values):
    """
    @brief: Apply explicitly a unary operator on input values
    @param equation <Equation>: an equation containing a unary operator
    @param input_values <numpy 1D-array>: the values of the input variable
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values)


def do_binary_calculation(equation, input_values):
    """
    @brief: Apply explicitly a binary operator on input values
    @param equation <Equation>: an equation containing a binary operator
    @param input_values <list of 2 numpy 1D-array>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values[0], input_values[1])


def do_ternary_calculation(equation, input_values):
    """
    @brief: Apply explicitly a ternary operator on input values
    @param equation <Equation>: an equation containing a ternary operator
    @param input_values <list of 3 numpy 1D-array>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values[0], input_values[1], input_values[2])


def get_available_variables(input_var_IDs):
    """
    @brief: Determine the list of new variables computable from the input variables by basic relations
    @param input_var_IDs <list of str>: the list of variable IDs contained in the input file
    @return <list of Variable>: the list of variables computable from the input variables by basic relations
    """
    available_vars = []
    computables = list(map(BASIC_VARIABLES.get, filter(is_basic_variable, input_var_IDs)))

    while True:
        found_new_computable = False
        for equation in BASIC_EQUATIONS.values():
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
    # handle the special case for TAU and DMAX
    if 'US' in input_var_IDs:
        available_vars.append(TAU)
        available_vars.append(DMAX)
    return available_vars


def get_necessary_equations(known_var_IDs, needed_var_IDs):
    """
    @brief: Determine the list of equations needed to compute all user-selected variables
    @param known_var_IDs <list of str>: the list of variable IDs contained in the input file
    @param needed_var_IDs <list of str>: the list of variable IDs selected by the user
    @return <list of Equation>: the list of equations needed to compute all user-selected variables
    """
    unknown_var_IDs = list(filter(lambda x: x not in known_var_IDs, needed_var_IDs))
    necessary_equations = []
    if 'H' in unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['H'])
    if 'S' in unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['S'])
    if 'M' in unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['M'])

    if 'Q' in unknown_var_IDs:
        if 'I' not in known_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['I'])
        if 'J' not in known_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['J'])
        necessary_equations.append(BASIC_EQUATIONS['Q'])
    else:
        if 'I' in unknown_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['I'])
        if 'J' in unknown_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['J'])

    if 'US' in known_var_IDs:
        if 'TAU' in unknown_var_IDs:
            necessary_equations.append(TAU_EQUATION)
        if 'DMAX' in unknown_var_IDs:
            necessary_equations.append(DMAX_EQUATION)
    return necessary_equations


def get_US_equation(friction_law):
    if friction_law == 0:
        return CHEZY_EQUATION
    elif friction_law == 1:
        return STRICKLER_EQUATION
    elif friction_law == 2:
        return MANNING_EQUATION
    return NIKURADSE_EQUATION


def do_calculations_in_frame(equations, input_serafin, time_index, selected_output_IDs):
    computed_values = {}
    for equation in equations:
        # handle the special case for TAU and DMAX
        if equation.output.ID() == 'TAU':
            computed_values['US'] = input_serafin.read_var_in_frame(time_index, 'US')
            computed_values['TAU'] = do_unary_calculation(TAU_EQUATION, computed_values['US'])
            continue
        elif equation.output.ID() == 'DMAX':
            computed_values['DMAX'] = do_unary_calculation(DMAX_EQUATION, computed_values['TAU'])
            continue

        # handle the normal case (binary operation)
        input_var_IDs = map(lambda x: x.ID(), equation.input)
        input_values = []

        # read (if needed) input variables values
        for input_var_ID in input_var_IDs:
            if input_var_ID not in computed_values:
                computed_values[input_var_ID] = input_serafin.read_var_in_frame(time_index, input_var_ID)
            input_values.append(computed_values[input_var_ID])

        # do calculation for the output variable
        output_values = do_binary_calculation(equation, input_values)
        computed_values[equation.output.ID()] = output_values

    # reconstruct the output values array in the order of the selected IDs
    nb_selected_vars = len(selected_output_IDs)
    output_values = np.empty((nb_selected_vars, input_serafin.header.nb_nodes),
                             dtype=input_serafin.header.float_type)
    for i in range(nb_selected_vars):
        var_ID = selected_output_IDs[i]
        if var_ID not in computed_values:
            output_values[i, :] = input_serafin.read_var_in_frame(time_index, var_ID)
        else:
            output_values[i, :] = computed_values[var_ID]
    return output_values


