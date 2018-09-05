"""!
Handle 2D variables and their relationships in Serafin files for additional variable computation
"""

from .variables_utils import *


# define variables
spec = """S,SURFACE LIBRE,FREE SURFACE,M
B,FOND,BOTTOM,M
EV,EVOLUTION FOND,BED EVOLUTION,M
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

basic_2D_vars_IDs = ['H', 'U', 'V', 'M', 'S', 'B', 'I', 'J', 'Q', 'C', 'F', 'US', 'TAU', 'DMAX', 'HD', 'RB',
                     'QS', 'QSX', 'QSY', 'QSBL', 'QSBLX', 'QSBLY', 'QSSUSP', 'QSSUSPX', 'QSSUSPY', 'EF',
                     'DF', 'MU', 'FROTP']
VARIABLES_2D = build_variables(spec)

H, U, V, M, S, B, I, J, Q, C, F, US, TAU, DMAX, HD, RB, \
QS, QSX, QSY, QSBL, QSBLX, QSBLY, QSSUSP, QSSUSPX, QSSUSPY, EF, DF, MU, FROTP, W, ROUSE =\
    [VARIABLES_2D[var] for var in basic_2D_vars_IDs + ['W', 'ROUSE']]


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
                      'FROTP': Equation((TAU, MU), FROTP, TIMES),
                      # Deduce one vector component assuming that the it has same direction of (U, V) vector
                      'QSX': Equation((QS, U, V), QSX, COMPUTE_COMPONENT_X),
                      'QSY': Equation((QS, U, V), QSY, COMPUTE_COMPONENT_Y),
                      'QSBLX': Equation((QSBL, U, V), QSBLX, COMPUTE_COMPONENT_X),
                      'QSBLY': Equation((QSBL, U, V), QSBLY, COMPUTE_COMPONENT_Y),
                      'QSSUSPX': Equation((QSSUSP, U, V), QSSUSPX, COMPUTE_COMPONENT_X),
                      'QSSUSPY': Equation((QSSUSP, U, V), QSSUSPY, COMPUTE_COMPONENT_Y)}

# define special friction law identifiers
CHEZY_ID, STRICKLER_ID, MANNING_ID, NIKURADSE_ID = 0, 1, 2, 3
FRICTION_LAWS = ['Chézy', 'Strickler', 'Manning', 'Nikuradse']


# a very special equation
class RouseEquation:
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
    @param us_equation <Equation>: user-specified equation for friction velocity
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

    # add vector component computations
    for var_ID in ('QSX', 'QSY', 'QSBLX', 'QSBLY', 'QSSUSPX', 'QSSUSPY'):
        if var_ID in selected_unknown_var_IDs:
            necessary_equations.append(BASIC_2D_EQUATIONS[var_ID])

    return necessary_equations


def get_US_equation(friction_law):
    """!
    @brief Convert integer code to friction law equation
    @param friction_law <int>: an integer specifying the friction law to use
    @return <Equation>: the corresponding friction law equation
    """
    if friction_law == CHEZY_ID:
        return Equation((W, H, M), US, COMPUTE_CHEZY)
    elif friction_law == STRICKLER_ID:
        return Equation((W, H, M), US, COMPUTE_STRICKLER)
    elif friction_law == MANNING_ID:
        return Equation((W, H, M), US, COMPUTE_MANNING)
    elif friction_law == NIKURADSE_ID:
        return Equation((W, H, M), US, COMPUTE_NIKURADSE)
    else:
        return None


def new_variables_from_US(known_vars):
    """!
    @brief Add US, TAU and DMAX and eventually FROTP Variable objects to the list
    @param available_vars <[Variable]>: the target list
    @param known_vars <[str]>: known variables IDs
    """
    new_vars = [US, TAU, DMAX]
    if 'MU' in known_vars:
        new_vars.append(FROTP)
    return new_vars
