"""
API for computing additional variables
"""

import numpy as np
from slf.variables_utils import do_calculation
from slf.variables_2d import get_available_2d_variables, get_necessary_2d_equations, \
                             get_US_equation, new_variables_from_US
from slf.variables_3d import get_available_3d_variables, get_necessary_3d_equations


def get_available_variables(input_variables, is_2d):
    if is_2d:
        return get_available_2d_variables(input_variables)
    return get_available_3d_variables(input_variables)


def get_necessary_equations(known_var_IDs, needed_var_IDs, is_2d, us_equation=None):
    if is_2d:
        return get_necessary_2d_equations(known_var_IDs, needed_var_IDs, us_equation)
    return get_necessary_3d_equations(known_var_IDs, needed_var_IDs)


def do_calculations_in_frame(equations, input_serafin, time_index, selected_output_IDs,
                             output_float_type, is_2d, us_equation):
    """!
    @brief Return the selected 2D variables values in a single time frame
    @param equations <[slf.variables_utils.Equation]>: list of all equations necessary to compute selected variables
    @param input_serafin <Serafin.Read>: input stream for reading necessary variables
    @param time_index <int>: the position of time frame to read
    @param selected_output_IDs <[str]>: the short names of the selected output variables
    @param output_float_type <numpy.dtype>: float32 or float64 according to the output file type
    @param is_2d <bool>: True if input data is 2D
    @param us_equation <slf.variables_utils.Equation>: user-specified friction law equation
    @return <numpy.ndarray>: the values of the selected output variables
    """
    computed_values = {}
    for equation in equations:
        input_var_IDs = list(map(lambda x: x.ID(), equation.input))

        # read (if needed) input variables values
        for input_var_ID in input_var_IDs:
            if is_2d:  # check for ROUSE variable
                if input_var_ID not in computed_values and input_var_ID[:5] != 'ROUSE':
                    computed_values[input_var_ID] = input_serafin.read_var_in_frame(time_index, input_var_ID)

        if is_2d:
            # handle the special case for US (user-specified equation)
            if equation.output.ID() == 'US':
                computed_values['US'] = do_calculation(us_equation, [computed_values['W'],
                                                                     computed_values['H'],
                                                                     computed_values['M']])
            # handle the very special case for ROUSE (equation depending on user-specified value)
            elif equation.output.ID() == 'ROUSE':
                computed_values[equation.input[0].ID()] = equation.operator(computed_values['US'])
                continue

        # handle the normal case
        output_values = do_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
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

