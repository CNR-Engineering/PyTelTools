"""!
Handle 2D variables and their relationships in .slf files for additional variable computation
"""

import numpy as np

from slf.variables_utils import cubic_root, build_variables, COMMON_OPERATIONS, Equation, get_available_variables,\
    MINUS, NORM2, PLUS, square_root, TIMES, Variable


KARMAN = 0.4
RHO_WATER = 1000.
GRAVITY = 9.80665


spec = """S,SURFACE LIBRE,FREE SURFACE,M
B,FOND,BOTTOM,M
H,HAUTEUR D'EAU,WATER DEPTH,M
M,VITESSE SCALAIRE,SCALAR VELOCITY,M/S
C,CELERITE,CELERITY,M/S
F,FROUDE,FROUDE NUMBER,
I,DEBIT SUIVANT X,FLOWRATE ALONG X,M2/S
J,DEBIT SUIVANT Y,FLOWRATE ALONG Y,M2/S
Q,DEBIT SCALAIRE,SCALAR FLOWRATE,M2/S
US,VITESSE DE FROT.,FRICTION VEL.,M/S
TAU,CONTRAINTE,BED SHEAR STRESS,PASCAL
DMAX,DIAMETRE,DIAMETER,MM
W,FROTTEMENT,BOTTOM FRICTION,
ROUSE,NOMBRE DE ROUSE,ROUSE NUMBER,
FROTP,FROT. PEAU,FROT. PEAU,PASCAL
QS,DEBIT SOLIDE,SOLID DISCH,M2/S
QSX,DEBIT SOLIDE X,SOLID DISCH X,M2/S
QSY,DEBIT SOLIDE Y,SOLID DISCH Y,M2/S
QSBL,QS CHARRIAGE,QS BEDLOAD,M2/S
QSBLX,QS CHARRIAGE X,QS BEDLOAD X,M2/S
QSBLY,QS CHARRIAGE Y,QS BEDLOAD Y,M2/S
QSSUSP,QS SUSPENSION,QS SUSPENSION,M2/S
QSSUSPX,QS SUSPENSION X,QS SUSPENSION X,M2/S
QSSUSPY,QS SUSPENSION Y,QS SUSPENSION Y,M2/S
U,VITESSE U,VELOCITY U,M/S
V,VITESSE V,VELOCITY V,M/S
HD,EPAISSEUR DU LIT,BED THICKNESS,M
RB,FOND RIGIDE,RIGID BED,M
EF,FLUX D'EROSION,EROSION FLUX,KG/M2/S
DF,FLUX DE DEPOT,DEPOSITION FLUX,KG/M2/S
MU,CORR FROTT PEAU,FROT. PEAU MU,"""

# all 2D variable entities involved in computations are stored as constants in a dictionary with ordered keys
basic_2D_vars_IDs = ['H', 'U', 'V', 'M', 'S', 'B', 'I', 'J', 'Q', 'C', 'F', 'US', 'TAU', 'DMAX', 'HD', 'RB',
                     'QS', 'QSX', 'QSY', 'QSBL', 'QSBLX', 'QSBLY', 'QSSUSP', 'QSSUSPX', 'QSSUSPY', 'EF',
                     'DF', 'MU', 'FROTP']
VARIABLES_2D = build_variables(spec)

H, U, V, M, S, B, I, J, Q, C, F, US, TAU, DMAX, HD, RB, \
QS, QSX, QSY, QSBL, QSBLX, QSBLY, QSSUSP, QSSUSPX, QSSUSPY, EF, DF, MU, FROTP, W, ROUSE =\
    [VARIABLES_2D[var] for var in basic_2D_vars_IDs + ['W', 'ROUSE']]


# define some special operators
def compute_NIKURADSE(w, h, m):
    with np.errstate(divide='ignore', invalide='ignore'):
        return np.sqrt(np.power(m, 2) * KARMAN**2 / np.power(np.log(30 * h / np.exp(1) / w), 2))


def compute_DMAX(tau):
    return np.where(tau > 0.34, 1.4593 * np.power(tau, 0.979),
                    np.where(tau > 0.1, 1.2912 * np.power(tau, 2) + 1.3572 * tau - 0.1154,
                             0.9055 * np.power(tau, 1.3178)))


COMPUTE_TAU, COMPUTE_DMAX = 5, 6
COMPUTE_CHEZY, COMPUTE_STRICKLER, COMPUTE_MANNING, COMPUTE_NIKURADSE = 7, 8, 9, 10
COMPUTE_C, COMPUTE_F = 11, 12

OPERATIONS_2D = {
    COMPUTE_TAU: lambda x: RHO_WATER * np.square(x),
    COMPUTE_DMAX: compute_DMAX,
    COMPUTE_CHEZY: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w)),
    COMPUTE_STRICKLER: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY / np.square(w) / cubic_root(h)),
    COMPUTE_MANNING: lambda w, h, m: np.sqrt(np.power(m, 2) * GRAVITY * np.power(w, 2) / cubic_root(h)),
    COMPUTE_NIKURADSE: compute_NIKURADSE,
    COMPUTE_C: lambda h: square_root(GRAVITY * h),
    COMPUTE_F: lambda m, c: m / c
}
OPERATIONS_2D.update(COMMON_OPERATIONS)

# define basic equations
BASIC_2D_EQUATIONS = {'H': Equation((S, B), H, MINUS), 'S': Equation((H, B), S, PLUS),
                      'B': Equation((S, H), B, MINUS), 'M': Equation((U, V), M, NORM2),
                      'I': Equation((H, U), I, TIMES), 'J': Equation((H, V), J, TIMES),
                      'Q': Equation((I, J), Q, NORM2), 'C': Equation((H,), C, COMPUTE_C),
                      'F': Equation((M, C), F, COMPUTE_F), 'HD': Equation((B, RB), HD, MINUS),
                      'RB': Equation((B, HD), RB, MINUS), 'Bbis': Equation((HD, RB), B, PLUS),
                      'QS': Equation((QSX, QSY), QS, NORM2),
                      'QSbis': Equation((EF, DF), QS, PLUS),
                      'QSBL': Equation((QSBLX, QSBLY), QSBL, NORM2),
                      'QSSUSP': Equation((QSSUSP, QSSUSPY), QSSUSP, NORM2),
                      'TAU': Equation((US,), TAU, COMPUTE_TAU),
                      'DMAX': Equation((TAU,), DMAX, COMPUTE_DMAX),
                      'FROTP': Equation((TAU, MU), FROTP, TIMES)}

# define special equations
CHEZY_EQUATION = Equation((W, H, M), US, COMPUTE_CHEZY)
STRICKLER_EQUATION = Equation((W, H, M), US, COMPUTE_STRICKLER)
MANNING_EQUATION = Equation((W, H, M), US, COMPUTE_MANNING)
NIKURADSE_EQUATION = Equation((W, H, M), US, COMPUTE_NIKURADSE)


# a very special equation
class RouseEquation():
    """!
    needed a pickle-able top-level equation object when computing Rouse in multi-process
    """
    def __init__(self, ws, ws_id):
        var = Variable(ws_id, None, None, None, -1)
        self.input = (var, US)
        self.output = ROUSE
        self.ws = ws
        self.operator = self.compute_rouse

    def compute_rouse(self, us):
        with np.errstate(divide='ignore'):
            return np.where(us != 0, self.ws / us / KARMAN, float('Inf'))


def is_basic_2d_variable(var_ID):
    """!
    @brief Determine if the input variable is a basic 2D variable
    @param var_ID <str>: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the basic variables
    """
    return var_ID in basic_2D_vars_IDs


def do_2d_calculation(equation, input_values):
    """!
    @brief Apply an equation on input values
    @param equation <Equation>: an equation object
    @param input_values <[numpy 1D-array]>: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    operation = OPERATIONS_2D[equation.operator]
    nb_operands = len(input_values)
    if nb_operands == 1:
        return operation(input_values[0])
    elif nb_operands == 2:
        return operation(input_values[0], input_values[1])
    return operation(input_values[0], input_values[1], input_values[2])


def get_available_2d_variables(input_var_IDs):
    """!
    @brief Determine the list of new 2D variables computable from the input variables by basic relations
    @param input_var_IDs <[str]>: the list of 2D variable IDs contained in the input file
    @return <[Variable]>: the list of variables computable from the input variables by basic relations
    """
    computables = list(map(VARIABLES_2D.get, filter(is_basic_2d_variable, input_var_IDs)))
    return get_available_variables(computables, BASIC_2D_EQUATIONS)


def get_necessary_2d_equations(known_var_IDs, needed_var_IDs, us_equation):
    """!
    @brief Determine the list of 2D equations needed to compute all user-selected variables, with precedence handling
    @param known_var_IDs <[str]>: the list of variable IDs contained in the input file
    @param needed_var_IDs <[str]>: the list of variable IDs selected by the user
    @return <[Equation]>: the list of equations needed to compute all user-selected variables
    """
    selected_unknown_var_IDs = list(filter(lambda x: x not in known_var_IDs, needed_var_IDs))
    is_rouse = any(map(lambda x: x[:5] == 'ROUSE', selected_unknown_var_IDs))
    necessary_equations = []

    # add S
    if 'S' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['S'])

    # add B
    if 'B' in selected_unknown_var_IDs:
        if 'S' in known_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['B'])
        else:
            necessary_equations.append(BASIC_2D_EQUATIONS['Bbis'])

    # add H
    if 'H' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['H'])
    elif 'H' not in known_var_IDs:
        if 'I' in selected_unknown_var_IDs \
                or 'J' in selected_unknown_var_IDs \
                or 'C' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['H'])
        elif 'Q' in selected_unknown_var_IDs and ('I' not in known_var_IDs or 'J' not in known_var_IDs):
            necessary_equations.append(BASIC_2D_EQUATIONS['H'])
        elif 'C' not in known_var_IDs and 'F' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['H'])
        elif 'US' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['H'])
        elif 'US' not in known_var_IDs:
            if 'TAU' in selected_unknown_var_IDs:
                necessary_equations.append(BASIC_2D_EQUATIONS['H'])
            elif 'TAU' not in known_var_IDs:
                if 'FROTP' in selected_unknown_var_IDs or 'DMAX' in selected_unknown_var_IDs:
                    necessary_equations.append(BASIC_2D_EQUATIONS['H'])
            elif is_rouse:
                necessary_equations.append(BASIC_2D_EQUATIONS['H'])

    # add M
    if 'M' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['M'])
    elif 'M' not in known_var_IDs:
        if 'F' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['M'])
        elif 'US' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['M'])
        elif 'US' not in known_var_IDs:
            if 'TAU' in selected_unknown_var_IDs:
                necessary_equations.append(BASIC_2D_EQUATIONS['M'])
            elif 'TAU' not in known_var_IDs:
                if 'FROTP' in selected_unknown_var_IDs or 'DMAX' in selected_unknown_var_IDs:
                    necessary_equations.append(BASIC_2D_EQUATIONS['M'])
            elif is_rouse:
                necessary_equations.append(BASIC_2D_EQUATIONS['M'])

    # add C
    if 'C' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['C'])
    elif 'C' not in known_var_IDs and 'F' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['C'])

    # add F
    if 'F' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['F'])

    # add I and J
    if 'I' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['I'])
    else:
        if 'Q' in selected_unknown_var_IDs and 'I' not in known_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['I'])
    if 'J' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['J'])
    else:
        if 'Q' in selected_unknown_var_IDs and 'J' not in known_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['J'])

    # add Q
    if 'Q' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['Q'])

    # add US
    if 'US' in selected_unknown_var_IDs:
        necessary_equations.append(us_equation)
    elif 'US' not in known_var_IDs:
        if 'TAU' in selected_unknown_var_IDs:
            necessary_equations.append(us_equation)
        elif 'TAU' not in known_var_IDs:
            if 'FROTP' in selected_unknown_var_IDs or 'DMAX' in selected_unknown_var_IDs:
                necessary_equations.append(us_equation)
        elif is_rouse:
            necessary_equations.append(us_equation)

    # add TAU
    if 'TAU' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['TAU'])
    elif 'TAU' not in known_var_IDs:
        if 'FROTP' in selected_unknown_var_IDs or 'DMAX' in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['TAU'])

    # add DMAX
    if 'DMAX' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['DMAX'])

    # add FROTP
    if 'FROTP' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['FROTP'])

    # add ROUSE
    for var_ID in selected_unknown_var_IDs:
        if var_ID[:5] == 'ROUSE':
            rouse_value = float(var_ID[6:])
            necessary_equations.append(RouseEquation(rouse_value, var_ID))

    # add QS
    if 'QS' in selected_unknown_var_IDs:
        if 'QSX' in known_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS['QS'])
        else:
            necessary_equations.append(BASIC_2D_EQUATIONS['QSbis'])

    # add QSBL
    if 'QSBL' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['QSBL'])

    # add QSSUSP
    if 'QSSUSP' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_2D_EQUATIONS['QSSUSP'])

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


def add_US(available_vars, known_vars):
    """!
    @brief Add US, TAU and DMAX Variable objects to the list
    @param available_vars <[Variable]>: the target list
    @param known_vars <[str]>: known variables IDs
    """
    available_vars.append(US)
    available_vars.append(TAU)
    available_vars.append(DMAX)
    if 'MU' in known_vars:
        available_vars.append(FROTP)


def do_2d_calculations_in_frame(equations, us_equation, input_serafin, time_index, selected_output_IDs, \
                                output_float_type):
    """!
    @brief Return the selected 2D variables values in a single time frame
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

        # handle the special case for US (user-specified equation)
        if equation.output.ID() == 'US':
            computed_values['US'] = do_2d_calculation(us_equation, [computed_values['W'],
                                                                    computed_values['H'],
                                                                    computed_values['M']])
        # handle the very special case for ROUSE (equation depending on user-specified value)
        elif equation.output.ID() == 'ROUSE':
            computed_values[equation.input[0].ID()] = equation.operator(computed_values['US'])
            continue

        # handle the normal case
        output_values = do_2d_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
        computed_values[equation.output.ID()] = output_values

    # reconstruct the output values array in the order of the selected IDs
    nb_selected_vars = len(selected_output_IDs)

    output_values = np.empty((nb_selected_vars, input_serafin.header.nb_nodes),
                             dtype=output_float_type)
    for i in range(nb_selected_vars):
        var_ID = selected_output_IDs[i]
        if var_ID not in computed_values:
            output_values[i, :] = input_serafin.read_var_in_frame(time_index, var_ID)
        else:
            output_values[i, :] = computed_values[var_ID]
    return output_values
