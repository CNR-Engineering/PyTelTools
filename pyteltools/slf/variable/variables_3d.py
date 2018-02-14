"""!
Handle 3D variables and their relationships in Serafin files for additional variable computation
"""

from .variables_utils import *


# define variables
spec = """Z,COTE Z,ELEVATION Z,M
U,VITESSE U,VELOCITY U,M/S
V,VITESSE V,VELOCITY V,M/S
W,VITESSE W,VELOCITY W,M/S
NUX,NUX POUR VITESSE,NUX FOR VELOCITY,M2/S
NUY,NUY POUR VITESSE,NUY FOR VELOCITY,M2/S
NUZ,NUZ POUR VITESSE,NUZ FOR VELOCITY,M2/S
M,VITESSE SCALAIRE,SCALAR VELOCITY,M/S
NU,NU POUR VITESSE,NU FOR VELOCITY,M2/S"""

basic_3D_vars_IDs = ['Z', 'U', 'V', 'W', 'NUX', 'NUY', 'NUZ', 'M', 'NU']
VARIABLES_3D = build_variables(spec)

Z, U, V, W, NUX, NUY, NUZ, M, NU = [VARIABLES_3D[var] for var in basic_3D_vars_IDs]


# define equations
BASIC_3D_EQUATIONS = {
    'M': Equation((U, V, W), M, NORM2_3D),
    'NU': Equation((NUX, NUY, NUZ), NU, NORM2_3D),
}


def is_basic_3d_variable(var_ID):
    """!
    @brief Determine if the input variable is a basic 3D variable
    @param var_ID <str>: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the basic variables
    """
    return var_ID in basic_3D_vars_IDs


def get_available_3d_variables(input_var_IDs):
    """!
    @brief Determine the list of new 3D variables computable from the input variables by basic relations
    @param input_var_IDs <[str]>: the list of 3D variable IDs contained in the input file
    @return <[Variable]>: the list of variables computable from the input variables by basic relations
    """
    computables = list(map(VARIABLES_3D.get, filter(is_basic_3d_variable, input_var_IDs)))
    return get_available_variables(computables, BASIC_3D_EQUATIONS)


def get_necessary_3d_equations(known_var_IDs, needed_var_IDs):
    """!
    @brief Determine the list of 3D equations needed to compute all user-selected variables, with precedence handling
    @param known_var_IDs <[str]>: the list of variable IDs contained in the input file
    @param needed_var_IDs <[str]>: the list of variable IDs selected by the user
    @return <[Equation]>: the list of equations needed to compute all user-selected variables
    """
    selected_unknown_var_IDs = list(filter(lambda x: x not in known_var_IDs, needed_var_IDs))
    necessary_equations = []

    # add M
    if 'M' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_3D_EQUATIONS['M'])

    # add NU
    if 'NU' in selected_unknown_var_IDs:
        necessary_equations.append(BASIC_3D_EQUATIONS['NU'])

    return necessary_equations
