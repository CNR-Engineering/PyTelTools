"""!
Handle variables and their relationships in .slf files
"""


import numpy as np

KARMAN = 0.4
RHO_EAU = 1000.
GRAVITY = 9.80665


class Variable():
    """!
    @brief Data type for a single variable with ID (short name), Name (fr or en) and Unit
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
    """!
    @brief Data type for an equation consisting of N input variables, 1 output variables and (N-1) operators
    """
    def __init__(self, input_variables, output_variable, operator):
        self.input = input_variables
        self.output = output_variable
        self.operator = operator


def build_basic_variables():
    """!
    @brief Initialize the BASIC_VARIABLES constant
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
ROUSE = Variable('ROUSE', bytes('NOMBRE DE ROUSE', 'utf-8').ljust(16), bytes('ROUSE NUMBER', 'utf-8').ljust(16), bytes('  ', 'utf-8').ljust(16))  # just a dummy

# define some special operators
def compute_DMAX(tau):
    return np.where(tau > 0.34, 1.4593 * np.power(tau, 0.979),
                                np.where(tau > 0.1, 1.2912 * np.power(tau, 2) + 1.3572 * tau - 0.1154,
                                                    0.9055 * np.power(tau, 1.3178)))


def cubic_root(x):
    with np.errstate(invalid='ignore'):
        return np.where(x < 0, np.power(-x, 1/3.), np.power(x, 1/3.))


def compute_NIKURADSE(w, h, m):
    with np.errstate(divide='ignore', invalide='ignore'):
        return np.sqrt(np.power(m, 2) * KARMAN**2 / np.power(np.log(30 * h / np.exp(1) / w), 2))


def compute_ROUSE(ws):
    def _compute_ROUSE(us):
        with np.errstate(divide='ignore'):
            return np.where(us != 0, ws / us / KARMAN, float('Inf'))
    return _compute_ROUSE

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
              COMPUTE_STRICKLER: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w) / cubic_root(h)),
              COMPUTE_MANNING: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY * np.power(w, 2) / cubic_root(h)),
              COMPUTE_NIKURADSE: compute_NIKURADSE}

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

# a very special equation
rouse_equation = lambda ws_id, ws: Equation((Variable(ws_id, None, None, None), US), ROUSE, compute_ROUSE(ws))


def is_basic_variable(var_ID):
    """!
    @brief Determine if the input variable is a basic variable
    @param var_ID <str>: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the nine basic variables
    """
    return var_ID in ordered_IDs


def do_unary_calculation(equation, input_values):
    """!
    @brief Apply explicitly a unary operator on input values
    @param equation <Equation>: an equation containing a unary operator
    @param input_values <[numpy 1D-array]>: the values of the input variable
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values)


def do_binary_calculation(equation, input_values):
    """!
    @brief Apply explicitly a binary operator on input values
    @param equation <Equation>: an equation containing a binary operator
    @param input_values <[numpy 1D-array]>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values[0], input_values[1])


def do_ternary_calculation(equation, input_values):
    """!
    @brief Apply explicitly a ternary operator on input values
    @param equation <Equation>: an equation containing a ternary operator
    @param input_values <[numpy 1D-array]>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS[equation.operator]
    return operation(input_values[0], input_values[1], input_values[2])


def get_available_variables(input_var_IDs):
    """!
    @brief Determine the list of new variables computable from the input variables by basic relations
    @param input_var_IDs <[str]>: the list of variable IDs contained in the input file
    @return <[Variable]>: the list of variables computable from the input variables by basic relations
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
        if 'TAU' not in input_var_IDs:
            available_vars.append(TAU)
        if 'DIAMETRE' not in input_var_IDs and 'DIAMETER' not in input_var_IDs:
            available_vars.append(DMAX)
    return available_vars


def get_necessary_equations(known_var_IDs, needed_var_IDs, us_equation):
    """!
    @brief Determine the list of equations needed to compute all user-selected variables, with precedence handling
    @param known_var_IDs <[str]>: the list of variable IDs contained in the input file
    @param needed_var_IDs <[str]>: the list of variable IDs selected by the user
    @return <[Equation]>: the list of equations needed to compute all user-selected variables
    """
    selected_unknown_var_IDs = list(filter(lambda x: x not in known_var_IDs, needed_var_IDs))
    is_rouse = any(map(lambda x: x[:5] == 'ROUSE', selected_unknown_var_IDs))
    necessary_equations = []

    # add S
    if 'S' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['S'])

    # add H
    if 'H' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['H'])
    elif 'H' not in known_var_IDs:
        if 'I' in selected_unknown_var_IDs \
                or 'J' in selected_unknown_var_IDs or 'Q' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['H'])
        elif 'US' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['H'])
        elif 'US' not in known_var_IDs:
             if 'TAU' in selected_unknown_var_IDs:
                necessary_equations.append(BASIC_EQUATIONS['H'])
             elif 'DMAX' in selected_unknown_var_IDs and 'TAU' not in known_var_IDs:
                necessary_equations.append(BASIC_EQUATIONS['H'])
             elif is_rouse:
                 necessary_equations.append(BASIC_EQUATIONS['H'])

    # add M
    if 'M' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['M'])
    elif 'M' not in known_var_IDs:
        if 'US' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['M'])
        elif 'US' not in known_var_IDs:
             if 'TAU' in selected_unknown_var_IDs:
                necessary_equations.append(BASIC_EQUATIONS['M'])
             elif 'DMAX' in selected_unknown_var_IDs and 'TAU' not in known_var_IDs:
                necessary_equations.append(BASIC_EQUATIONS['M'])
             elif is_rouse:
                 necessary_equations.append(BASIC_EQUATIONS['M'])

    # add I and J
    if 'I' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['I'])
    else:
        if 'Q' in selected_unknown_var_IDs and 'I' not in known_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['I'])
    if 'J' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['J'])
    else:
        if 'Q' in selected_unknown_var_IDs and 'J' not in known_var_IDs:
            necessary_equations.append(BASIC_EQUATIONS['J'])

    # add Q
    if 'Q' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_EQUATIONS['Q'])

    # add US
    if 'US' in selected_unknown_var_IDs:
        necessary_equations.append(us_equation)
    elif 'US' not in known_var_IDs:
        if 'TAU' in selected_unknown_var_IDs:
            necessary_equations.append(us_equation)
        elif 'DMAX' in selected_unknown_var_IDs and 'TAU' not in known_var_IDs:
            necessary_equations.append(us_equation)
        elif is_rouse:
            necessary_equations.append(us_equation)

    # add TAU
    if 'TAU' in selected_unknown_var_IDs:
        necessary_equations.append(TAU_EQUATION)
    elif 'DMAX' in selected_unknown_var_IDs and 'TAU' not in known_var_IDs:
        necessary_equations.append(TAU_EQUATION)

    # add DMAX
    if 'DMAX' in selected_unknown_var_IDs:
        necessary_equations.append(DMAX_EQUATION)

    # add ROUSE
    for var_ID in selected_unknown_var_IDs:
        if var_ID[:5] == 'ROUSE':
            rouse_value = float(var_ID[6:])
            necessary_equations.append(rouse_equation(var_ID, rouse_value))

    return necessary_equations


def get_US_equation(friction_law):
    """!
    @brief Convert integer code to friction law equation
    @param friction_law <int>: an integer specifying the friction law to use
    @return <Equation>: the corresponding friction law equation
    """
    if friction_law == 0:
        return CHEZY_EQUATION
    elif friction_law == 1:
        return STRICKLER_EQUATION
    elif friction_law == 2:
        return MANNING_EQUATION
    return NIKURADSE_EQUATION


def add_US(available_vars):
    """!
    @brief Add US, TAU and DMAX Variable objects to the list
    @param available_vars <[Variable]>: the target list
    """
    available_vars.append(US)
    available_vars.append(TAU)
    available_vars.append(DMAX)


def do_calculations_in_frame(equations, us_equation, input_serafin, time_index, selected_output_IDs, output_float_type):
    """!
    @brief Return the selected variables values in a single time frame
    @param equations <[Equation]>: list of all equations necessary to compute selected variables
    @param us_equation <Equation>: user-specified friction law equation
    @param input_serafin <Serafin.Read>: input stream for reading necessary variables
    @param time_index <int>: the position of time frame to read
    @param selected_output_IDs <[str]>: the short names of the selected output variables
    @param output_float_type <numpy.dtype>: float32 or float64 according to the output file type
    @return <numpy.ndarray>: the values of the selected output variables
    """
    computed_values = {}
    for equation in equations:
        input_var_IDs = list(map(lambda x: x.ID(), equation.input))

        # read (if needed) input variables values
        for input_var_ID in input_var_IDs:
            if input_var_ID not in computed_values and input_var_ID[:5] != 'ROUSE':
                computed_values[input_var_ID] = input_serafin.read_var_in_frame(time_index, input_var_ID)

        # handle the special case for TAU, DMAX and US
        if equation.output.ID() == 'US':
            computed_values['US'] = do_ternary_calculation(us_equation, [computed_values['W'],
                                                                         computed_values['H'],
                                                                         computed_values['M']])
            continue
        elif equation.output.ID() == 'TAU':
            computed_values['TAU'] = do_unary_calculation(TAU_EQUATION, computed_values['US'])
            continue
        elif equation.output.ID() == 'DMAX':
            computed_values['DMAX'] = do_unary_calculation(DMAX_EQUATION, computed_values['TAU'])
            continue
        # handle the very special case for ROUSE
        elif equation.output.ID() == 'ROUSE':
            computed_values[equation.input[0].ID()] = equation.operator(computed_values['US'])
            continue

        # handle the normal case (binary operation)
        output_values = do_binary_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
        computed_values[equation.output.ID()] = output_values

    # reconstruct the output values array in the order of the selected IDs
    nb_selected_vars = len(selected_output_IDs)

    # handle the special case when only one output variable selected (numpy 1D-array)
    if nb_selected_vars == 1:
        var_ID = selected_output_IDs[0]
        if var_ID not in computed_values:
            return np.array(input_serafin.read_var_in_frame(time_index, var_ID), dtype=output_float_type)
        return np.array(computed_values[var_ID], dtype=output_float_type)
    # handle the general case
    output_values = np.empty((nb_selected_vars, input_serafin.header.nb_nodes),
                             dtype=output_float_type)
    for i in range(nb_selected_vars):
        var_ID = selected_output_IDs[i]
        if var_ID not in computed_values:
            output_values[i, :] = input_serafin.read_var_in_frame(time_index, var_ID)
        else:
            output_values[i, :] = computed_values[var_ID]
    return output_values


