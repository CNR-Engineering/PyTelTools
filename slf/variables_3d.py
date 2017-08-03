"""!
Handle 3D variables and their relationships in .slf files for additional variable computation
"""

import numpy as np

from slf.variables_utils import build_variables, COMMON_OPERATIONS, Equation, get_available_variables, \
    NORM2_3D, do_calculation


spec = """Z,COTE Z,ELEVATION Z,M
U,VITESSE U,VELOCITY U,M/S
V,VITESSE V,VELOCITY V,M/S
W,VITESSE W,VELOCITY W,M/S
NUX,NUX POUR VITESSE,NUX FOR VELOCITY,M2/S
NUY,NUY POUR VITESSE,NUY FOR VELOCITY,M2/S
NUZ,NUZ POUR VITESSE,NUZ FOR VELOCITY,M2/S
M,VITESSE SCALAIRE,SCALAR VELOCITY,M/S
NU,NU POUR VITESSE,NU FOR VELOCITY,M2/S"""

# all 3D variable entities involved in computations are stored as constants in a dictionary with ordered keys
basic_3D_vars_IDs = ['Z', 'U', 'V', 'W', 'NUX', 'NUY', 'NUZ', 'M', 'NU']
VARIABLES_3D = build_variables(spec)

Z, U, V, W, NUX, NUY, NUZ, M, NU = [VARIABLES_3D[var] for var in basic_3D_vars_IDs]


OPERATIONS_3D = {}
OPERATIONS_3D.update(COMMON_OPERATIONS)

# define basic equations
BASIC_3D_EQUATIONS = {
    'M': Equation((U, V, W), M, NORM2_3D),
    'NU': Equation((NUX, NUY, NUZ), NU, NORM2_3D),
}


def is_basic_3d_variable(var_ID):
    """!
    @brief Determine if the input variable is a basic 3D variable
    @param <str> var_ID: the ID (short name) of the variable
    @return <bool>: True if the variable is one of the basic variables
    """
    return var_ID in basic_3D_vars_IDs


def do_3d_calculation(equation, input_values):
    """!
    @brief Apply an equation on input values
    @param <Equation> equation: an equation object
    @param <[numpy 1D-array]> input_values: the values of the input variables
    @return <numpy 1D-array>: the values of the output variable
    """
    return do_calculation(OPERATIONS_3D, equation, input_values)


def get_available_3d_variables(input_var_IDs):
    """!
    @brief Determine the list of new 3D variables computable from the input variables by basic relations
    @param <[str]> input_var_IDs: the list of 3D variable IDs contained in the input file
    @return <[Variable]>: the list of variables computable from the input variables by basic relations
    """
    computables = list(map(VARIABLES_3D.get, filter(is_basic_3d_variable, input_var_IDs)))
    return get_available_variables(computables, BASIC_3D_EQUATIONS)


def get_necessary_3d_equations(known_var_IDs, needed_var_IDs):
    """!
    @brief Determine the list of 3D equations needed to compute all user-selected variables, with precedence handling
    @param <[str]> known_var_IDs: the list of variable IDs contained in the input file
    @param <[str]> needed_var_IDs: the list of variable IDs selected by the user
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


def do_3d_calculations_in_frame(equations, input_serafin, time_index, selected_output_IDs, output_float_type):
    """!
    @brief Return the selected 3D variables values in a single time frame
    @param <[Equation]> equations: list of all equations necessary to compute selected variables
    @param <Serafin.Read> input_serafin: input stream for reading necessary variables
    @param <int> time_index: the position of time frame to read
    @param <[str]> selected_output_IDs: the short names of the selected output variables
    @param <numpy.dtype> output_float_type: float32 or float64 according to the output file type
    @return <numpy.ndarray>: the values of the selected output variables
    """
    computed_values = {}
    for equation in equations:
        input_var_IDs = list(map(lambda x: x.ID(), equation.input))

        # read (if needed) input variables values
        for input_var_ID in input_var_IDs:
            if input_var_ID not in computed_values:
                computed_values[input_var_ID] = input_serafin.read_var_in_frame(time_index, input_var_ID)

        # handle the normal case
        output_values = do_3d_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
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
