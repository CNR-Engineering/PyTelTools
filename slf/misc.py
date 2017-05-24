import numpy as np
import logging
from slf.variables import get_available_variables, get_necessary_equations, do_calculation


_VECTORS = {'U': ('V', 'M'), 'V': ('U', 'M'), 'QSX': ('QSY', 'QS'), 'QSY': ('QSX', 'QS'),
            'QSBLX': ('QSBLY', 'QSBL'), 'QSBLY': ('QSBLX', 'QSBL'),
            'QSSUSPX': ('QSSUSPY', 'QSSUSP'), 'QSSUSPY': ('QSSUSPX', 'QSSUSP'),
            'I': ('J', 'Q'), 'J': ('I', 'Q')}
module_logger = logging.getLogger(__name__)


def scalars_vectors(known_vars, selected_vars):
    scalars = []
    vectors = []
    additional_equations = {}
    for var, name, unit in selected_vars:
        if var in _VECTORS:
            brother, mother = _VECTORS[var]
            if mother in known_vars:
                vectors.append((var, name, unit))
            elif brother in known_vars:
                vectors.append((var, name, unit))
                additional_equations[mother] = get_necessary_equations(known_vars, [mother], None)
            else:
                # handle the special case for I and J
                if var == 'I' or var == 'J':
                    computable_variables = get_available_variables(known_vars)
                    if 'Q' in map(lambda x: x.ID(), computable_variables):
                        vectors.append((var, name, unit))
                        additional_equations['Q'] = get_necessary_equations(known_vars, ['Q'], None)
                        continue
                # if the magnitude is not computable, use scalar operation instead
                module_logger.warn('The variable %s will be considered to be scalar instead of vector.' % var)
                scalars.append((var, name, unit))
        else:
            scalars.append((var, name, unit))
    return scalars, vectors, list(sum(additional_equations.values(), []))


def scalar_max(input_stream, selected_scalars, time_indices):
    nb_var = len(selected_scalars)
    nb_nodes = input_stream.header.nb_nodes
    current_values = np.ones((nb_var, nb_nodes)) * (-float('Inf'))

    for index in time_indices:
        values = np.empty((nb_var, nb_nodes))
        for i, (var, name, unit) in enumerate(selected_scalars):
            values[i, :] = input_stream.read_var_in_frame(index, var)
        current_values = np.maximum(current_values, values)
    return current_values


def scalar_min(input_stream, selected_scalars, time_indices):
    nb_var = len(selected_scalars)
    nb_nodes = input_stream.header.nb_nodes
    current_values = np.ones((nb_var, nb_nodes)) * float('Inf')

    for index in time_indices:
        values = np.empty((nb_var, nb_nodes))
        for i, (var, name, unit) in enumerate(selected_scalars):
            values[i, :] = input_stream.read_var_in_frame(index, var)
        current_values = np.minimum(current_values, values)
    return current_values


def mean(input_stream, selected_vars, time_indices, dummy=None):
    nb_var = len(selected_vars)
    nb_nodes = input_stream.header.nb_nodes
    current_values = np.zeros((nb_var, nb_nodes))

    for index in time_indices:
        values = np.empty((nb_var, nb_nodes))
        for i, (var, name, unit) in enumerate(selected_vars):
            values[i, :] = input_stream.read_var_in_frame(index, var)
        current_values += values
    current_values /= len(time_indices)
    return current_values


def vector_max(input_stream, selected_vectors, time_indices, additional_equations):
    nb_nodes = input_stream.header.nb_nodes
    current_values = {}
    for var, _, _ in selected_vectors:
        current_values[var] = np.ones((nb_nodes,)) * (-float('Inf'))
        parent = _VECTORS[var][1]
        current_values[parent] = np.ones((nb_nodes,)) * (-float('Inf'))

    for index in time_indices:
        computed_values = {}
        for equation in additional_equations:
            input_var_IDs = list(map(lambda x: x.ID(), equation.input))

            # read (if needed) input variables values
            for input_var_ID in input_var_IDs:
                if input_var_ID not in computed_values:
                    computed_values[input_var_ID] = input_stream.read_var_in_frame(index, input_var_ID)
            # compute additional variables
            output_values = do_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
            computed_values[equation.output.ID()] = output_values

        for var, _, _ in selected_vectors:
            parent = _VECTORS[var][1]

            if parent not in computed_values:
                computed_values[parent] = input_stream.read_var_in_frame(index, parent)
            if var not in computed_values:
                computed_values[var] = input_stream.read_var_in_frame(index, var)

            new_max = computed_values[parent] >= current_values[parent]
            current_values[var][new_max] = computed_values[var]

    values = np.empty((len(selected_vectors), nb_nodes))
    for i, (var, _, _) in enumerate(selected_vectors):
        values[i, :] = current_values[var]
    return values


def vector_min(input_stream, selected_vectors, time_indices, additional_equations):
    nb_nodes = input_stream.header.nb_nodes
    current_values = {}
    for var, _, _ in selected_vectors:
        current_values[var] = np.ones((nb_nodes,)) * float('Inf')
        parent = _VECTORS[var][1]
        current_values[parent] = np.ones((nb_nodes,)) * float('Inf')

    for index in time_indices:
        computed_values = {}
        for equation in additional_equations:
            input_var_IDs = list(map(lambda x: x.ID(), equation.input))

            # read (if needed) input variables values
            for input_var_ID in input_var_IDs:
                if input_var_ID not in computed_values:
                    computed_values[input_var_ID] = input_stream.read_var_in_frame(index, input_var_ID)
            # compute additional variables
            output_values = do_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
            computed_values[equation.output.ID()] = output_values

        for var, _, _ in selected_vectors:
            parent = _VECTORS[var][1]

            if parent not in computed_values:
                computed_values[parent] = input_stream.read_var_in_frame(index, parent)
            if var not in computed_values:
                computed_values[var] = input_stream.read_var_in_frame(index, var)

            new_min = computed_values[parent] <= current_values[parent]
            current_values[var][new_min] = computed_values[var]

    values = np.empty((len(selected_vectors), nb_nodes))
    for i, (var, _, _) in enumerate(selected_vectors):
        values[i, :] = current_values[var]
    return values



