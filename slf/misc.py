import numpy as np

VECTORS = ['U', 'V', 'QSX', 'QSY', 'QSBLX', 'QSBLY', 'QSSUSPX', 'QSSUSPY', 'I', 'J']


def scalars_vectors(selected_vars):
    scalars = []
    vectors = []
    for var, name, unit in selected_vars:
        if var in VECTORS:
            vectors.append((var, name, unit))
        else:
            scalars.append((var, name, unit))
    return scalars, vectors


def scalar_max(input_stream, selected_vars, time_indices):
    nb_var = len(selected_vars)
    nb_nodes = input_stream.header.nb_nodes
    current_values = np.ones((nb_var, nb_nodes)) * (-float('Inf'))

    for index in time_indices:
        values = np.empty((nb_var, nb_nodes))
        for i, (var, name, unit) in enumerate(selected_vars):
            values[i, :] = input_stream.read_var_in_frame(index, var)
        current_values = np.maximum(current_values, values)
    return current_values


def scalar_min(input_stream, selected_vars, time_indices):
    nb_var = len(selected_vars)
    nb_nodes = input_stream.header.nb_nodes
    current_values = np.ones((nb_var, nb_nodes)) * float('Inf')

    for index in time_indices:
        values = np.empty((nb_var, nb_nodes))
        for i, (var, name, unit) in enumerate(selected_vars):
            values[i, :] = input_stream.read_var_in_frame(index, var)
        current_values = np.minimum(current_values, values)
    return current_values


def mean(input_stream, selected_vars, time_indices):
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



