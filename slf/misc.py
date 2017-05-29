import numpy as np
import logging
import re
from slf.variables import get_available_variables, get_necessary_equations, do_calculation

OPERATORS = ['+', '-', '*', '/', '^', 'sqrt']
_OPERATIONS = {'+': np.add, '-': np.subtract, '*': np.multiply, '/': np.divide, '^': np.power, 'sqrt': np.sqrt}
_PRECEDENCE = {'(': 1, '-': 2, '+': 2, '*': 3, '/': 3, '^': 4, 'sqrt': 5}

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


def mean(input_stream, selected_vars, time_indices, _=None):
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
        mother = _VECTORS[var][1]
        current_values[mother] = np.ones((nb_nodes,)) * (-float('Inf'))

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

            if mother not in computed_values:
                computed_values[mother] = input_stream.read_var_in_frame(index, parent)
            if var not in computed_values:
                computed_values[var] = input_stream.read_var_in_frame(index, var)

            current_values[var] = np.where(computed_values[mother] > current_values[mother],
                                           computed_values[var], current_values[var])

    values = np.empty((len(selected_vectors), nb_nodes))
    for i, (var, _, _) in enumerate(selected_vectors):
        values[i, :] = current_values[var]
    return values


def vector_min(input_stream, selected_vectors, time_indices, additional_equations):
    nb_nodes = input_stream.header.nb_nodes
    current_values = {}
    for var, _, _ in selected_vectors:
        current_values[var] = np.ones((nb_nodes,)) * float('Inf')
        mother = _VECTORS[var][1]
        current_values[mother] = np.ones((nb_nodes,)) * float('Inf')

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
            mother = _VECTORS[var][1]

            if mother not in computed_values:
                computed_values[mother] = input_stream.read_var_in_frame(index, mother)
            if var not in computed_values:
                computed_values[var] = input_stream.read_var_in_frame(index, var)

            current_values[var] = np.where(computed_values[mother] < current_values[mother],
                                           computed_values[var], current_values[var])

    values = np.empty((len(selected_vectors), nb_nodes))
    for i, (var, _, _) in enumerate(selected_vectors):
        values[i, :] = current_values[var]
    return values


def tighten_expression(expression):
    """
    Remove the spaces and brackets to get a nice expression
    """
    return re.sub('(\s+|\[|\])', '', expression)


def to_infix(expression):
    return list(filter(None, map(lambda x: x.strip(), re.split('(\d+\.*\d+E*e*-*\d+|(?!e)-|(?!E)-'
                                                               '|[+*()^/]|\[[A-Z]+\])', expression))))


def infix_to_postfix(expression):
    """!
    Convert infix to postfix
    """
    stack = []
    post = []
    for token in expression:
        if token == '(':
            stack.append(token)
        elif token == ')':
            top_token = stack.pop()
            while top_token != '(':
                post.append(top_token)
                top_token = stack.pop()
        elif token in OPERATORS:
            while stack and _PRECEDENCE[stack[-1]] >= _PRECEDENCE[token]:
                post.append(stack.pop())
            stack.append(token)
        else:
            post.append(token)
    while stack:
        op_token = stack.pop()
        post.append(op_token)
    return post


def is_valid_postfix(expression):
    """!
    Is my postfix expression valid?
    """
    stack = []

    try:  # try to evaluate the expression
        for symbol in expression:
            if symbol in OPERATORS:
                if symbol == 'sqrt':
                    stack.pop()
                else:
                    stack.pop()
                    stack.pop()
                stack.append(0)
            else:
                stack.append(0)
        # the stack should be empty after the final pop
        stack.pop()
        if stack:
            return False
        return True
    except IndexError:
        return False


def test_condition(value, comparator, threshold):
    if comparator == '>':
        return value > threshold
    elif comparator == '<':
        return value < threshold
    elif comparator == '>=':
        return value >= threshold
    else:
        return value <= threshold


def evaluate_expression(input_stream, time_index, expression):
    nb_nodes = input_stream.header.nb_nodes
    stack = []

    for symbol in expression:
        if symbol in OPERATORS:
            if symbol == 'sqrt':
                operand = stack.pop()
                stack.append(_OPERATIONS[symbol](operand))
            else:
                first_operand = stack.pop()
                second_operand = stack.pop()
                stack.append(_OPERATIONS[symbol](first_operand, second_operand))
        else:
            if symbol[0] == '[':
                stack.append(input_stream.read_var_in_frame(time_index, symbol[1:-1]))
            else:
                stack.append(np.ones((nb_nodes,)) * float(symbol))

    return stack.pop()


def arrival_duration(input_stream, time_indices, expression, comparator, threshold):
    # first
    previous_time = input_stream.time[time_indices[0]]
    previous_value = evaluate_expression(input_stream, time_indices[0], expression)
    previous_flag = test_condition(previous_value, comparator, threshold)

    duration = np.zeros((input_stream.header.nb_nodes,))
    arrival = np.where(previous_flag, previous_time, float('Inf'))
    previous_flip = np.ones((input_stream.header.nb_nodes,)) * previous_time

    # iteration
    for index in time_indices[1:]:
        current_time = input_stream.time[index]
        current_value = evaluate_expression(input_stream, index, expression)
        with np.errstate(divide='ignore'):
            t_star = (current_value * previous_time - previous_value * current_time) / (current_value - previous_value)

        current_flag = test_condition(current_value, comparator, threshold)
        flip_forward = np.logical_and(current_flag, np.logical_not(previous_flag))
        flip_backward = np.logical_and(previous_flag, np.logical_not(current_flag))

        if index == time_indices[-1]:  # last
            duration = np.where(np.logical_and(previous_flag, current_flag),
                                duration + input_stream.time[index] - previous_flip, duration)
        else:
            duration = np.where(flip_backward, duration + t_star - previous_flip, duration)

        arrival = np.where(flip_forward, np.minimum(arrival, t_star), arrival)
        previous_flip = np.where(flip_forward, t_star, previous_flip)

        previous_flag = current_flag
        previous_value = current_value
        previous_time = current_time

    return arrival, duration

