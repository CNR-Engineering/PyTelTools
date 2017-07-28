"""!
Simple computation/evaluation of variable values in .slf
"""

import numpy as np
import logging
import re
import shapefile
from shapely.geometry import Point
from slf import Serafin
from slf.variables import get_available_variables, get_necessary_equations, do_calculation

module_logger = logging.getLogger(__name__)

# constants
OPERATORS = ['+', '-', '*', '/', '^', 'sqrt', 'sin', 'cos', 'atan']
MAX, MIN, MEAN, ARRIVAL_DURATION, \
          PROJECT, DIFF, REV_DIFF, MAX_BETWEEN, MIN_BETWEEN, SYNCH_MAX = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9

_OPERATIONS = {'+': np.add, '-': np.subtract, '*': np.multiply, '/': np.divide, '^': np.power,
               'sqrt': np.sqrt, 'sin': np.sin, 'cos': np.cos, 'atan': np.arctan}
_PRECEDENCE = {'(': 1, '-': 2, '+': 2, '*': 3, '/': 3, '^': 4, 'sqrt': 5, 'sin': 5, 'cos': 5, 'atan': 5}

_VECTORS = {'U': ('V', 'M'), 'V': ('U', 'M'), 'QSX': ('QSY', 'QS'), 'QSY': ('QSX', 'QS'),
            'QSBLX': ('QSBLY', 'QSBL'), 'QSBLY': ('QSBLX', 'QSBL'),
            'QSSUSPX': ('QSSUSPY', 'QSSUSP'), 'QSSUSPY': ('QSSUSPX', 'QSSUSP'),
            'I': ('J', 'Q'), 'J': ('I', 'Q')}
_VECTORS_BROTHERS = {('U', 'V'): 'M', ('I', 'J'): 'Q', ('X', 'Y'): '.', ('QSX', 'QSY'): 'QS',
                     ('QSBLX', 'QSBLY'): 'QSBL', ('QSSUSPX', 'QSSUSPY'): 'QSSUSP'}


def scalars_vectors(known_vars, selected_vars, us_equation=None):
    """!
    @brief Separate the scalars from vectors, allowing different max/min computations
    @param <list> known_vars: the list of variable IDs with known values
    @param <str> selected_vars: the selected variables IDs
    @return <tuple>: the list of scalars, the list of vectors, the list of additional equations for magnitudes
    """
    scalars = []
    vectors = []
    computable_variables = list(map(lambda x: x.ID(), get_available_variables(known_vars)))
    additional_equations = get_necessary_equations(known_vars, list(map(lambda x: x[0], selected_vars)), us_equation)
    for var, name, unit in selected_vars:
        if var in _VECTORS:
            brother, mother = _VECTORS[var]
            if mother in known_vars:  # if the magnitude is known
                vectors.append((var, name, unit))
            elif brother in known_vars:  # if the magnitude is unknown but the orthogonal field is known
                vectors.append((var, name, unit))
                additional_equations.extend(get_necessary_equations(known_vars, [mother], us_equation))
            else:
                if mother in computable_variables:
                    vectors.append((var, name, unit))
                    additional_equations.extend(get_necessary_equations(known_vars, [mother], us_equation))
                    continue
                # if the magnitude is not computable, use scalar operation instead
                module_logger.warn('The variable %s will be considered to be scalar instead of vector.' % var)
                scalars.append((var, name, unit))
        else:
            scalars.append((var, name, unit))
    additional_equations = list(set(additional_equations))
    additional_equations.sort(key=lambda x: x.output.order)
    return scalars, vectors, additional_equations


def available_vectors(known_vars):
    vectors = []
    for var in known_vars:
        if var in _VECTOR_COUPLES:
            brother = _VECTOR_COUPLES[var]
            if brother in known_vars:
                vectors.append((var, brother))
    return vectors


def tighten_expression(expression):
    """!
    Remove the spaces and brackets to get a nice and short expression for display
    """
    return re.sub('(\s+|\[|\])', '', expression)


def to_infix(expression):
    """!
    Convert an expression string to an infix expression (list of varIDs, constants, parenthesis and operators)
    """
    return list(filter(None, map(lambda x: x.strip(), re.split('(\d+\.*\d+E*e*-*\d+(?=[^\]]*(?:\[|$))'
                                                               '|(?!e)-(?=[^\]]*(?:\[|$))|(?!E)-(?=[^\]]*(?:\[|$))'
                                                               '|\[^[a-zA-Z0-9_.-]*\]|[+*()^/](?=[^\]]*(?:\[|$)))',
                                                               expression))))


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


def is_valid_expression(expression, var_IDs):
    for item in expression:
        if item[0] == '[':  # variable ID
            if item[1:-1] not in var_IDs:
                return False
        elif item in OPERATORS:
            continue
        else:  # is number
            try:
                _ = float(item)
            except ValueError:
                return False
    return True


def is_valid_postfix(expression):
    """!
    Is my postfix expression valid?
    """
    stack = []

    try:  # try to evaluate the expression
        for symbol in expression:
            if symbol in OPERATORS:
                if symbol in ('sqrt', 'sin', 'cos', 'atan'):
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


def evaluate_expression(input_stream, time_index, expression):
    """!
    @brief Evaluate a postfix expression on the input stream for a single frame
    @param <slf.Serafin.Read> input_stream: the input .slf
    @param <int> time_index: the index of the frame
    @param <list> expression: the expression to evaluate in postfix format
    @return <numpy.1D-array>: the value of the expression
    """
    stack = []

    for symbol in expression:
        if symbol in OPERATORS:
            if symbol in ('sqrt', 'sin', 'cos', 'atan'):
                operand = stack.pop()
                stack.append(_OPERATIONS[symbol](operand))
            else:
                first_operand = stack.pop()
                second_operand = stack.pop()
                stack.append(_OPERATIONS[symbol](first_operand, second_operand))
        else:
            if symbol[0] == '[':  # variable ID
                stack.append(input_stream.read_var_in_frame(time_index, symbol[1:-1]))
            else:  # constant
                stack.append(float(symbol))

    return stack.pop()


def detect_vector_couples(variables, available_variables):
    coupled, non_coupled, mothers, angles = [], [], [], []
    for var in variables:
        if var in coupled:
            continue
        if var in _VECTORS:
            brother, mother = _VECTORS[var]
            if brother in variables:
                coupled.append(var)
                coupled.append(brother)

                if (var, brother) not in _VECTORS_BROTHERS:
                    angles.append((brother, var))
                else:
                    angles.append((var, brother))

                if mother in available_variables:
                    coupled.append(mother)
                else:
                    mothers.append((mother, var, brother))
            else:
                non_coupled.append(var)
        else:
            non_coupled.append(var)
    return coupled, non_coupled, mothers, angles


def slf_to_shp(slf_name, slf_header, shp_name, variables, time_index):
    coupled, non_coupled, mothers, angles = detect_vector_couples(variables, slf_header.var_IDs)

    values = {}
    with Serafin.Read(slf_name, slf_header.language) as slf:
        slf.header = slf_header
        for var in variables:
            values[var] = slf.read_var_in_frame(time_index, var)

    # compute mother not in file
    for mother, brother, sister in mothers:
        values[mother] = np.sqrt(np.square(values[brother]) + np.square(values[sister]))

    # compute angles
    for brother, sister in angles:
        values['Angle(%s,%s)' % (brother, sister)] = np.degrees(np.arctan2(values[sister], values[brother]))

    # write shp
    key_order = coupled + non_coupled + [mother for mother, _, _ in mothers] \
                        + ['Angle(%s,%s)' % (brother, sister) for brother, sister in angles]

    w = shapefile.Writer(shapefile.POINT)
    for name in key_order:
        w.field(name, 'N', decimal=4)

    for i, (x, y) in enumerate(zip(slf_header.x, slf_header.y)):
        w.point(x, y, shapeType=shapefile.POINT)

        val = []
        for var in key_order:
            val.append(values[var][i])
        w.record(*val)
    w.save(shp_name)


def scalar_to_xml(slf_name, slf_header, xml_name, scalar, time_index):
    """!
    @brief Write LandXML file from a scalar variable of a .slf file (and its first frame)
    @param <str> slf_name: path to the input .slf file
    @param <slf.Serafin.SerafinHeader> slf_header: input Serafin header
    @param <str> xml_name: output LandXML filename
    @param <str> scalar: variable to write
    """
    with Serafin.Read(slf_name, slf_header.language) as slf:
        slf.header = slf_header

        # fetch scalar variable values
        scalar_values = slf.read_var_in_frame(time_index, scalar)

    # write shp
    with open(xml_name, 'w') as xml:
        xml.write('<?xml version="1.0" ?>\n')
        xml.write('<LandXML version="1.2" xmlns="http://www.landxml.org/schema/LandXML-1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.landxml.org/schema/LandXML-1.2 http://www.landxml.org/schema/LandXML-1.2/LandXML-1.2.xsd">\n')
        xml.write('  <Surfaces>\n')
        xml.write('    <Surface name="My TIN">\n')
        xml.write('      <Definition surfType="TIN">\n')
        xml.write('        <Pnts>')
        for i, (x, y, z) in enumerate(zip(slf_header.x, slf_header.y, scalar_values)):
            xml.write('        <P id="%d">%.4f %.4f %.4f</P>\n' % (i+1, y, x, z))
        xml.write('        </Pnts>\n')
        xml.write('        <Faces>')
        for i, (a, b, c) in enumerate(slf_header.ikle_2d):
            xml.write('        <F id="%d">%d %d %d</F>\n' % (i+1, a, b, c))
        xml.write('        </Faces>\n')
        xml.write('      </Definition>\n')
        xml.write('    </Surface>\n')
        xml.write('  </Surfaces>\n')
        xml.write('</LandXML>\n')


class ScalarMaxMinMeanCalculator:
    """!
    Compute max/min/mean of scalar variables from a .slf input stream
    """
    def __init__(self, max_min_type, input_stream, selected_scalars, time_indices, additional_equations=None):
        self.maxmin = max_min_type
        self.input_stream = input_stream
        self.selected_scalars = selected_scalars
        self.time_indices = time_indices

        self.nb_var = len(selected_scalars)
        self.nb_nodes = input_stream.header.nb_nodes
        self.additional_equations = additional_equations

        if self.maxmin == MAX:
            self.current_values = np.ones((self.nb_var, self.nb_nodes)) * (-float('Inf'))
        elif self.maxmin == MIN:
            self.current_values = np.ones((self.nb_var, self.nb_nodes)) * float('Inf')
        else:
            self.current_values = np.zeros((self.nb_var, self.nb_nodes))

    def additional_computation_in_frame(self, time_index):
        computed_values = {}
        for equation in self.additional_equations:
            input_var_IDs = list(map(lambda x: x.ID(), equation.input))

            # read (if needed) input variables values
            for input_var_ID in input_var_IDs:
                if input_var_ID not in computed_values:
                    computed_values[input_var_ID] = self.input_stream.read_var_in_frame(time_index, input_var_ID)
            # compute additional variables
            output_values = do_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
            computed_values[equation.output.ID()] = output_values
        return computed_values

    def max_min_mean_in_frame(self, time_index):
        if self.additional_equations is not None:
            computed_values = self.additional_computation_in_frame(time_index)
        else:
            computed_values = {}

        values = np.empty((self.nb_var, self.nb_nodes))
        for i, (var, name, unit) in enumerate(self.selected_scalars):
            if var not in computed_values:
                computed_values[var] = self.input_stream.read_var_in_frame(time_index, var)
            values[i, :] = computed_values[var]

        with np.errstate(invalid='ignore'):
            if self.maxmin == MAX:
                self.current_values = np.maximum(self.current_values, values)
            elif self.maxmin == MIN:
                self.current_values = np.minimum(self.current_values, values)
            else:
                self.current_values += values

    def finishing_up(self):
        if self.maxmin == MEAN:
            self.current_values /= len(self.time_indices)
        return self.current_values

    def run(self):
        for time_index in self.time_indices:
            self.max_min_mean_in_frame(time_index)


class VectorMaxMinMeanCalculator:
    """!
    Compute max/min/mean of vector variables from a .slf input stream
    """
    def __init__(self, max_min_type, input_stream, selected_vectors, time_indices, additional_equations):
        self.maxmin = max_min_type
        self.input_stream = input_stream
        self.selected_vectors = selected_vectors
        self.time_indices = time_indices
        self.additional_equations = additional_equations

        self.nb_nodes = input_stream.header.nb_nodes

        self.current_values = {}
        for var, _, _ in selected_vectors:
            mother = _VECTORS[var][1]
            if self.maxmin == MAX:
                self.current_values[var] = np.ones((self.nb_nodes,)) * (-float('Inf'))
                self.current_values[mother] = np.ones((self.nb_nodes,)) * (-float('Inf'))
            elif self.maxmin == MIN:
                self.current_values[var] = np.ones((self.nb_nodes,)) * float('Inf')
                self.current_values[mother] = np.ones((self.nb_nodes,)) * float('Inf')
            else:
                self.current_values[var] = np.zeros((self.nb_nodes,))

    def additional_computation_in_frame(self, time_index):
        computed_values = {}
        for equation in self.additional_equations:
            input_var_IDs = list(map(lambda x: x.ID(), equation.input))

            # read (if needed) input variables values
            for input_var_ID in input_var_IDs:
                if input_var_ID not in computed_values:
                    computed_values[input_var_ID] = self.input_stream.read_var_in_frame(time_index, input_var_ID)
            # compute additional variables
            output_values = do_calculation(equation, [computed_values[var_ID] for var_ID in input_var_IDs])
            computed_values[equation.output.ID()] = output_values
        return computed_values

    def max_min_mean_in_frame(self, time_index):
        computed_values = self.additional_computation_in_frame(time_index)

        if self.maxmin == MEAN:
            for var, _, _ in self.selected_vectors:
                self.current_values[var] += computed_values[var]
            return

        for var, _, _ in self.selected_vectors:
            mother = _VECTORS[var][1]

            if mother not in computed_values:
                computed_values[mother] = self.input_stream.read_var_in_frame(time_index, mother)
            if var not in computed_values:
                computed_values[var] = self.input_stream.read_var_in_frame(time_index, var)

            if self.maxmin == MAX:
                self.current_values[var] = np.where(computed_values[mother] > self.current_values[mother],
                                                    computed_values[var], self.current_values[var])
            else:
                self.current_values[var] = np.where(computed_values[mother] < self.current_values[mother],
                                                    computed_values[var], self.current_values[var])

    def finishing_up(self):
        values = np.empty((len(self.selected_vectors), self.nb_nodes))
        for i, (var, _, _) in enumerate(self.selected_vectors):
            values[i, :] = self.current_values[var]

        if self.maxmin == MEAN:
            values /= len(self.time_indices)
        return values

    def run(self):
        for time_index in self.time_indices:
            self.max_min_mean_in_frame(time_index)


class ArrivalDurationCalculator:
    """!
    Compute arrival/duration of conditions from a .slf input stream
    """
    def __init__(self, input_stream, time_indices, condition):
        self.input_stream = input_stream
        self.time_indices = time_indices
        self.expression = condition.expression
        self.test_condition = condition.test_condition

        # first
        self.previous_time = self.input_stream.time[self.time_indices[0]]
        self.previous_value = evaluate_expression(self.input_stream, self.time_indices[0], self.expression)
        self.previous_flag = self.test_condition(self.previous_value)

        self.duration = np.zeros((self.input_stream.header.nb_nodes,))
        self.arrival = np.where(self.previous_flag, self.previous_time, float('Inf'))
        self.previous_flip = np.ones((input_stream.header.nb_nodes,)) * self.previous_time

    def arrival_duration_in_frame(self, index):
        current_time = self.input_stream.time[index]
        current_value = evaluate_expression(self.input_stream, index, self.expression)
        with np.errstate(divide='ignore', invalid='ignore'):
            t_star = (current_value * self.previous_time - self.previous_value * current_time) \
                     / (current_value - self.previous_value)
            new_arrival = np.minimum(self.arrival, t_star)

        current_flag = self.test_condition(current_value)
        flip_forward = np.logical_and(current_flag, np.logical_not(self.previous_flag))
        flip_backward = np.logical_and(self.previous_flag, np.logical_not(current_flag))

        if index == self.time_indices[-1]:  # last
            self.duration = np.where(np.logical_and(self.previous_flag, current_flag),
                                     self. duration + self.input_stream.time[index] - self.previous_flip,
                                     np.where(self.previous_flag, self.duration + t_star - self.previous_flip,
                                              self.duration))
        else:
            self.duration = np.where(flip_backward, self.duration + t_star - self.previous_flip, self.duration)

        self.arrival = np.where(flip_forward, new_arrival, self.arrival)

        self.previous_flip = np.where(flip_forward, t_star, self.previous_flip)
        self.previous_flag = current_flag
        self.previous_value = current_value
        self.previous_time = current_time

    def run(self):
        for index in self.time_indices[1:]:
            self.arrival_duration_in_frame(index)


class Condition:
    """!
    Condition to compare a variable with a threshold for arrival/duration
    """
    def __init__(self, expression, literal_expression, comparator, threshold):
        self.expression = expression
        self.literal_expression = literal_expression
        self.comparator = comparator
        self.threshold = threshold
        
        if self.comparator == '>':
            self.test_condition = lambda value: value > self.threshold
        elif self.comparator == '<':
            self.test_condition = lambda value: value < self.threshold
        elif self.comparator == '>=':
            self.test_condition = lambda value: value >= self.threshold
        else:
            self.test_condition = lambda value: value <= self.threshold
            
    def __repr__(self):
        return ' '.join(self.expression) + ' %s %s' % (self.comparator, str(self.threshold))

    def __str__(self):
        return '%s %s %.4f' % (''.join(self.literal_expression), self.comparator, self.threshold)


class ProjectMeshCalculator:
    """!
    Projection and operations between two different meshes
    """
    def __init__(self, first_in, second_in, selected_vars, is_inside, point_interpolators,
                 time_indices, operation_type, use_reference=False):
        self.first_in = first_in
        self.second_in = second_in
        self.is_inside = is_inside
        self.point_interpolators = point_interpolators
        self.time_indices = time_indices
        self.operation_type = operation_type
        self.selected_vars = selected_vars

        self.use_reference = use_reference
        if self.use_reference:
            self.first_values = self.read_values_in_frame(0, False)
        else:
            self.first_values = []

        self.nb_var = len(self.selected_vars)
        self.nb_nodes = self.first_in.header.nb_nodes

    def read_values_in_frame(self, time_index, read_second):
        values = []
        for i, var_ID in enumerate(self.selected_vars):
            if read_second:
                values.append(self.second_in.read_var_in_frame(time_index, var_ID))
            else:
                values.append(self.first_in.read_var_in_frame(time_index, var_ID))
        return values

    def interpolate(self, values):
        interpolated_values = []
        for index_node in range(self.nb_nodes):
            if not self.is_inside[index_node]:
                interpolated_values.append(np.nan)
            else:
                (i, j, k), interpolator = self.point_interpolators[index_node]
                interpolated_values.append(interpolator.dot(values[[i, j, k]]))
        return interpolated_values

    def operation_in_frame(self, first_time_index, second_time_index):
        if self.operation_type == PROJECT:  # projection
            second_values = self.read_values_in_frame(second_time_index, True)
            return np.array([self.interpolate(second_values[i]) for i in range(self.nb_var)])

        if self.use_reference:
            first_values = self.first_values
        else:
            first_values = np.array(self.read_values_in_frame(first_time_index, False))
        second_values = self.read_values_in_frame(second_time_index, True)

        if self.operation_type == DIFF:
            return np.array([first_values[i] - np.array(self.interpolate(second_values[i]))
                             for i in range(self.nb_var)])
        elif self.operation_type == REV_DIFF:
            return np.array([np.array(self.interpolate(second_values[i])) - first_values[i]
                             for i in range(self.nb_var)])
        elif self.operation_type == MAX_BETWEEN:
            return np.array([np.maximum(self.interpolate(second_values[i]), first_values[i])
                             for i in range(self.nb_var)])
        else:
            return np.array([np.minimum(self.interpolate(second_values[i]), first_values[i])
                             for i in range(self.nb_var)])

    def run(self, out_stream, out_header):
        for i, (first_time_index, second_time_index) in enumerate(self.time_indices):
            values = self.operation_in_frame(first_time_index, second_time_index)
            if self.use_reference:
                out_stream.write_entire_frame(out_header,
                                              self.second_in.time[second_time_index], values)
            else:
                out_stream.write_entire_frame(out_header,
                                              self.first_in.time[first_time_index], values)


class SynchMaxCalculator:
    """!
    Compute multiple synchronized maxima with respect to a reference variable
    """
    def __init__(self, input_stream, selected_vars, time_indices, ref_var):
        self.input_stream = input_stream
        self.selected_vars = selected_vars
        self.time_indices = time_indices
        self.ref_var = ref_var

        self.read_ref = False
        if ref_var not in selected_vars:
            self.read_ref = True
        self.nb_nodes = input_stream.header.nb_nodes
        self.current_values = {'time': np.ones((self.nb_nodes,)) * self.input_stream.time[time_indices[0]]}

        for var, _, _ in selected_vars:
            self.current_values[var] = self.input_stream.read_var_in_frame(time_indices[0], var)
        if self.read_ref:
            self.current_values[ref_var] = self.input_stream.read_var_in_frame(time_indices[0], ref_var)

    def synch_max_in_frame(self, time_index):
        values = {}
        for var, _, _ in self.selected_vars:
            values[var] = self.input_stream.read_var_in_frame(time_index, var)
        if self.read_ref:
            values[self.ref_var] = self.input_stream.read_var_in_frame(time_index, self.ref_var)

        flags = values[self.ref_var] > self.current_values[self.ref_var]
        for var, _, _ in self.selected_vars:
            self.current_values[var] = np.where(flags, values[var], self.current_values[var])
        self.current_values[self.ref_var] = np.where(flags, values[self.ref_var], self.current_values[self.ref_var])

        time_value = self.input_stream.time[time_index]
        self.current_values['time'] = np.where(flags, time_value, self.current_values['time'])

    def finishing_up(self):
        values = np.empty((len(self.selected_vars)+1, self.nb_nodes))
        values[0, :] = self.current_values['time']
        for i, (var, _, _) in enumerate(self.selected_vars):
            values[i+1, :] = self.current_values[var]
        return values

    def run(self):
        for time_index in self.time_indices[1:]:
            self.synch_max_in_frame(time_index)


class ComplexExpression:
    """!
    expression object in an expression pool
    """
    def __init__(self, index):
        self.index = index
        self.polygonal = False  # polygonal expression can only be evaluated inside a masked expression
        self.masked = False  # masked expression cannot be composed to create new expression
        self.mask_id = 0

    def __repr__(self):
        return ''

    def __str__(self):
        return 'E%d: %s' % (self.index, repr(self))

    def code(self):
        return 'E%d' % self.index

    def evaluate(self, values, mask=None):
        return []


class SimpleExpression(ComplexExpression):
    """!
    expression object in an expression pool
    """
    def __init__(self, index, postfix, literal_expression):
        super().__init__(index)
        self.expression = postfix
        self.tight_expression = tighten_expression(literal_expression)

    def __repr__(self):
        return self.tight_expression

    def evaluate(self, values, mask=None):
        stack = []
        for symbol in self.expression:
            if symbol in OPERATORS:
                if symbol in ('sqrt', 'sin', 'cos', 'atan'):
                    operand = stack.pop()
                    stack.append(_OPERATIONS[symbol](operand))
                else:
                    first_operand = stack.pop()
                    second_operand = stack.pop()
                    stack.append(_OPERATIONS[symbol](first_operand, second_operand))
            else:
                if symbol[0] == '[':
                    stack.append(values[symbol[1:-1]])
                else:
                    stack.append(float(symbol))
        return stack.pop()


class ConditionalExpression(ComplexExpression):
    def __init__(self, index, condition, true_expression, false_expression):
        super().__init__(index)
        self.condition = condition
        self.true_expression = true_expression
        self.false_expression = false_expression

    def __repr__(self):
        return 'IF (%s) THEN (%s) ELSE (%s)' % (self.condition.text, repr(self.true_expression),
                                                repr(self.false_expression))

    def evaluate(self, values, mask=None):
        condition = values[self.condition.code()]
        return np.where(condition, values[self.true_expression.code()], values[self.false_expression.code()])


class MaxMinExpression(ComplexExpression):
    def __init__(self, index, first_expression, second_expression, is_max):
        super().__init__(index)
        self.first_expression = first_expression
        self.second_expression = second_expression
        self.is_max = is_max

    def __repr__(self):
        return '%s(%s, %s)' % ('MAX' if self.is_max else 'MIN',
                               repr(self.first_expression), repr(self.second_expression))

    def evaluate(self, values, mask=None):
        if self.is_max:
            return np.maximum(values[self.first_expression.code()], values[self.second_expression.code()])
        else:
            return np.minimum(values[self.first_expression.code()], values[self.second_expression.code()])


class PolygonalMask:
    def __init__(self, index, mask, values):
        self.index = index
        self.mask = mask
        self.values = values
        self.children = []
        self.nb_children = 0

    def code(self):
        return 'POLY%d' % self.index

    def add_child(self, child):
        self.nb_children += 1
        self.children.append(child.code())


class MaskedExpression(ComplexExpression):
    def __init__(self, index, inside_expression, outside_expression):
        super().__init__(index)
        self.inside_expression = inside_expression
        self.outside_expression = outside_expression
        self.masked = True
        self.polygonal = True
        self.mask_id = self.inside_expression.mask_id

    def __repr__(self):
        return 'IF (POLY%s) THEN (%s) ELSE (%s)' % (self.mask_id,
                                                    repr(self.inside_expression),
                                                    repr(self.outside_expression))

    def evaluate(self, values, mask=None):
        return np.where(mask, values[self.inside_expression.code()], values[self.outside_expression.code()])


class ComplexCondition:
    def __init__(self, index):
        self.index = index
        self.text = ''
        self.polygonal = False
        self.masked = False  # placeholder
        self.mask_id = 0

    def __str__(self):
        return 'C%d: %s' % (self.index, self.text)

    def code(self):
        return 'C%d' % self.index


class SimpleCondition(ComplexCondition):
    def __init__(self, index, expression, comparator, threshold):
        super().__init__(index)
        self.expression = expression
        self.text = '%s %s %s' % (repr(self.expression), comparator, str(threshold))
        self.polygonal = expression.polygonal
        self.mask_id = expression.mask_id

        if comparator == '>':
            self._evaluate = lambda value: value > threshold
        elif comparator == '<':
            self._evaluate = lambda value: value < threshold
        elif comparator == '>=':
            self._evaluate = lambda value: value >= threshold
        else:
            self._evaluate = lambda value: value <= threshold

    def evaluate(self, current_values):
        return self._evaluate(current_values[self.expression.code()])


class AndOrCondition(ComplexCondition):
    def __init__(self, index, first_condition, second_condition, is_and):
        super().__init__(index)
        self.first_condition = first_condition
        self.second_condition = second_condition
        self.text = '(%s) %s (%s)' % (self.first_condition.text, 'AND' if is_and else 'OR',
                                      self.second_condition.text)
        self.func = np.logical_and if is_and else np.logical_or

    def evaluate(self, current_values):
        return self.func(current_values[self.first_condition.code()], current_values[self.second_condition.code()])


class ComplexExpressionPool:
    def __init__(self, variables, names, x, y):
        self.nb_expressions = 0
        self.expressions = {}
        self.nb_conditions = 0
        self.conditions = {}
        self.nb_masks = 0
        self.masks = {}

        self.x = x
        self.y = y
        self.vars = ['COORDX', 'COORDY'] + variables
        self.var_names = ['X coordinate', 'Y coordinate'] + names
        self.id_pool = self.vars[:]
        self.dependency_graph = {var: set() for var in self.vars}  # a DAG

    def points(self):
        for i, (x, y) in enumerate(zip(self.x, self.y)):
            yield i, Point(x, y)

    def add_simple_expression(self, literal_expression):
        infix = to_infix(literal_expression)
        postfix = infix_to_postfix(infix)
        if not self.is_valid(postfix):
            return -1

        self.nb_expressions += 1
        new_expression = SimpleExpression(self.nb_expressions, postfix, literal_expression)
        self.expressions[self.nb_expressions] = new_expression
        new_id = new_expression.code()
        self.id_pool.append(new_id)

        self.dependency_graph[new_id] = set()
        for item in postfix:
            if item[0] == '[':
                var_id = item[1:-1]
                if var_id[:4] == 'POLY':
                    if not new_expression.polygonal:
                        new_expression.polygonal = True
                        new_expression.mask_id = int(var_id[4:])
                    elif int(var_id[4:]) != new_expression.mask_id:
                        del self.dependency_graph[new_id]
                        del self.expressions[self.nb_expressions]
                        self.id_pool.pop()
                        self.nb_expressions -= 1
                        return -2
                elif var_id not in self.vars:  # expression
                    expr = self.expressions[int(var_id[1:])]
                    if expr.polygonal:
                        mask_id = expr.mask_id
                        if not new_expression.polygonal:
                            new_expression.polygonal = True
                            new_expression.mask_id = mask_id
                        elif mask_id != new_expression.mask_id:
                            del self.dependency_graph[new_id]
                            del self.expressions[self.nb_expressions]
                            self.id_pool.pop()
                            self.nb_expressions -= 1
                            return -2
                self.dependency_graph[new_id].add(var_id)
        if new_expression.polygonal:
            self.masks[new_expression.mask_id].add_child(new_expression)
            return 1
        return 0

    def add_conditional_expression(self, condition, true_expression, false_expression):
        polygonal, mask_id = False, 0
        if condition.polygonal:
            polygonal = True
            mask_id = condition.mask_id
        if true_expression.polygonal:
            if polygonal:
                if mask_id != true_expression.mask_id:
                    return -2
            else:
                polygonal = True
                mask_id = true_expression.mask_id
        if false_expression.polygonal:
            if polygonal:
                if mask_id != false_expression.mask_id:
                    return -2
            else:
                polygonal = True
                mask_id = false_expression.mask_id

        self.nb_expressions += 1
        new_expression = ConditionalExpression(self.nb_expressions, condition, true_expression, false_expression)
        self.expressions[self.nb_expressions] = new_expression
        new_id = new_expression.code()
        self.id_pool.append(new_id)
        self.dependency_graph[new_id] = {condition.code(), true_expression.code(), false_expression.code()}
        if polygonal:
            new_expression.mask_id = mask_id
            new_expression.polygonal = True
            self.masks[mask_id].add_child(new_expression)
            return 1
        return 0

    def add_max_min_expression(self, first_expression, second_expression, is_max):
        first_mask, second_mask, polygonal = 0, 0, False
        if first_expression.polygonal:
            first_mask = first_expression.mask_id
        if second_expression.polygonal:
            second_mask = second_expression.mask_id
        if first_mask > 0 and second_mask > 0:
            if first_mask != second_mask:
                return -2
        if first_mask > 0 or second_mask > 0:
            polygonal = True

        self.nb_expressions += 1
        new_expression = MaxMinExpression(self.nb_expressions, first_expression, second_expression, is_max)
        self.expressions[self.nb_expressions] = new_expression
        new_id = new_expression.code()
        self.id_pool.append(new_id)
        self.dependency_graph[new_id] = {first_expression.code(), second_expression.code()}
        new_expression.polygonal = polygonal
        if polygonal:
            new_expression.mask_id = max(first_mask, second_mask)
            self.masks[new_expression.mask_id].add_child(new_expression)
            return 1
        return 0

    def add_masked_expression(self, inside_expression, outside_expression):
        # masked expressions are not added as children of the mask
        self.nb_expressions += 1
        new_expression = MaskedExpression(self.nb_expressions, inside_expression, outside_expression)
        self.expressions[self.nb_expressions] = new_expression
        new_id = new_expression.code()
        self.id_pool.append(new_id)
        self.dependency_graph[new_id] = {inside_expression.code(), outside_expression.code()}

    def add_condition(self, expression, comparator, threshold):
        self.nb_conditions += 1
        new_condition = SimpleCondition(self.nb_conditions, expression, comparator, threshold)
        self.conditions[self.nb_conditions] = new_condition
        new_id = new_condition.code()
        self.dependency_graph[new_id] = {expression.code()}

    def add_and_or_condition(self, first_condition, second_condition, is_and):
        first_mask, second_mask, polygonal = 0, 0, False
        if first_condition.polygonal:
            first_mask = first_condition.mask_id
        if second_condition.polygonal:
            second_mask = second_condition.mask_id
        if first_mask > 0 and second_mask > 0:
            if first_mask != second_mask:
                return -2
        if first_mask > 0 or second_mask > 0:
            polygonal = True

        self.nb_conditions += 1
        new_condition = AndOrCondition(self.nb_conditions, first_condition, second_condition, is_and)
        self.conditions[self.nb_conditions] = new_condition
        new_id = new_condition.code()
        self.id_pool.append(new_id)
        self.dependency_graph[new_id] = {first_condition.code(), second_condition.code()}
        new_condition.polygonal = polygonal
        if polygonal:
            new_condition.mask_id = max(first_mask, second_mask)
            return 1
        return 0

    def add_polygonal_mask(self, polygons, attribute_index):
        self.nb_masks += 1
        new_id = 'POLY%d' % self.nb_masks
        self.id_pool.append(new_id)
        self.dependency_graph[new_id] = set()
        mask = np.zeros_like(self.x)
        for index, poly in enumerate(polygons):
            for i, point in self.points():
                if poly.contains(point):
                    mask[i] = index+1
        masked_values = np.zeros_like(self.x)
        for index, poly in enumerate(polygons):
            masked_values[mask == index+1] = poly.attributes()[attribute_index]
        self.masks[self.nb_masks] = PolygonalMask(self.nb_masks, mask > 0, masked_values)

    def get_expression(self, str_expression):
        index = int(str_expression.split(':')[0][1:])
        return self.expressions[index]

    def get_condition(self, str_condition):
        index = int(str_condition.split(':')[0][1:])
        return self.conditions[index]

    def get_mask(self, str_mask):
        index = int(str_mask[4:])
        return self.masks[index]

    def ready_for_conditional_expression(self):
        # one can add conditional expression if
        # case 1: there are only polygonal conditions (then at least one polygonal expression)
        #         at least polygonal expression for the same mask OR at least one non-polygonal expression
        # case 2: there are only non-polygonal conditions
        #         at least two non-polygonal expressions
        # case 3: mixed case (then there are at least one polygonal expression and one non-polygonal expression)
        #         always ready
        if self.nb_conditions == 0:
            return False
        nb_polygonal, nb_non_polygonal = 0, 0
        for condition in self.conditions.values():
            if condition.polygonal:
                nb_polygonal += 1
            else:
                nb_non_polygonal += 1
        if nb_non_polygonal > 0 and nb_polygonal > 0:
            return True
        elif nb_polygonal > 0:
            expr_non_polygonal = 0
            for expr in self.expressions.values():
                if not expr.polygonal:
                    expr_non_polygonal += 1
                    if expr_non_polygonal > 0:
                        return True
            for mask in self.masks.values():
                if mask.nb_children > 1:
                    return True
            return False
        else:
            expr_non_polygonal = 0
            for expr in self.expressions.values():
                if not expr.polygonal:
                    expr_non_polygonal += 1
                    if expr_non_polygonal > 1:
                        return True
            return False

    def ready_for_max_min_expression(self):
        # one can add max min expression is there are
        # (at least one polygonal and at least one non-polygonal expression) OR
        # (at least two polygonal expressions with the same mask)
        nb_non_polygonal = 0
        for expr in self.expressions.values():
            if not expr.polygonal:
                nb_non_polygonal += 1
                if nb_non_polygonal > 1:
                    return True
        if nb_non_polygonal == 0:
            for mask in self.masks.values():
                if mask.nb_children > 1:
                    return True
            return False
        else:
            for mask in self.masks.values():
                if mask.nb_children > 0:
                    return True
            return False

    def ready_for_masked_expression(self):
        # one can add a masked expression if there are at least one polygonal expression
        # and at least one non-polygonal expression
        has_non_polygonal = False
        for expr in self.expressions.values():
            if not expr.polygonal:
                has_non_polygonal = True
                break
        if not has_non_polygonal:
            return False
        has_polygonal = False
        for mask in self.masks.values():
            if mask.nb_children > 0:
                has_polygonal = True
                break
        return has_polygonal

    def is_valid(self, postfix):
        return is_valid_expression(postfix, self.id_pool) and is_valid_postfix(postfix)

    def get_dependence(self, expression_code):
        # BFS in a DAG
        dependence = [expression_code]
        queue = [expression_code]
        while queue:
            current_node = queue.pop(0)
            parents = self.dependency_graph[current_node]
            for p in parents:
                if parents not in dependence:
                    dependence.append(p)
                    queue.append(p)
        dependence.reverse()
        return dependence

    def evaluable_expressions(self):
        for i in range(1, self.nb_expressions+1):
            expr = self.expressions[i]
            if expr.masked or not expr.polygonal:
                yield expr.code(), repr(expr)

    def evaluate_expressions(self, augmented_path, input_stream, selected_expressions):
        nb_row = len(selected_expressions)
        nb_col = input_stream.header.nb_nodes

        for time_index, time_value in enumerate(input_stream.time):
            values = self._evaluate_expressions(input_stream, time_index, augmented_path)

            # build nd-array in the selected order
            value_array = np.empty((nb_row, nb_col))
            for i, expr in enumerate(selected_expressions):
                value_array[i, :] = values[expr]
            yield time_value, value_array

    def decode(self, input_stream, time_index, node_code):
        if node_code == 'COORDX':
            return self.x, None
        elif node_code == 'COORDY':
            return self.y, None
        elif node_code in self.vars:
            return input_stream.read_var_in_frame(time_index, node_code), None
        elif node_code[:4] == 'POLY':
            index = int(node_code[4:])
            return self.masks[index].values, None
        elif node_code[0] == 'C':
            index = int(node_code[1:])
            return None, self.conditions[index]
        else:
            index = int(node_code[1:])
            return None, self.expressions[index]

    def _evaluate_expressions(self, input_stream, time_index, path):
        # evaluate each node on the augmented path
        values = {node: None for node in path}
        for node in path:
            node_values, node_object = self.decode(input_stream, time_index, node)
            if node_values is None:
                if node_object.masked:
                    node_values = node_object.evaluate(values, self.masks[node_object.mask_id].mask)
                else:
                    node_values = node_object.evaluate(values)
                if type(node_values) == float:  # single constant expression
                    node_values = np.ones_like(self.x) * node_values
            values[node] = node_values
        return values


class ComplexExpressionMultiPool:
    def __init__(self):
        self.input_data = []
        self.nb_pools = 0
        self.pools = []
        self.representative = None

    def clear(self):
        self.input_data = []
        self.nb_pools = 0
        self.pools = []
        self.representative = None

    def get_data(self, input_data):
        self.input_data = input_data
        self.nb_pools = len(input_data)

        common_vars = set(input_data[0].header.var_IDs)
        for data in input_data[1:]:
            common_vars.intersection_update(data.header.var_IDs)
        variables = [var for var in input_data[0].header.var_IDs if var in common_vars]
        names = [name.decode('utf-8').strip() for (var, name)
                 in zip(input_data[0].header.var_IDs, input_data[0].header.var_names) if var in common_vars]

        for data in input_data:
            pool = ComplexExpressionPool(variables, names, data.header.x, data.header.y)
            self.pools.append(pool)
        self.representative = self.pools[0]

    def add_polygonal_mask(self, polygons, attribute_index):
        for pool in self.pools:
            pool.add_polygonal_mask(polygons, attribute_index)

    def add_simple_expression(self, literal_expression):
        success_code = self.representative.add_simple_expression(literal_expression)
        if success_code not in (0, 1):
            return success_code
        for pool in self.pools[1:]:
            pool.add_simple_expression(literal_expression)
        return success_code

    def add_conditional_expression(self, condition, true_expression, false_expression):
        success_code = self.representative.add_conditional_expression(condition, true_expression, false_expression)
        if success_code not in (0, 1):
            return success_code
        for pool in self.pools[1:]:
            pool.add_conditional_expression(condition, true_expression, false_expression)
        return success_code

    def add_max_min_expression(self, first_expression, second_expression, is_max):
        success_code = self.representative.add_max_min_expression(first_expression, second_expression, is_max)
        if success_code not in (1, 2):
            return success_code
        for pool in self.pools[1:]:
            pool.add_max_min_expression(first_expression, second_expression, is_max)
        return success_code

    def add_masked_expression(self, inside_expression, outside_expression):
        for pool in self.pools:
            pool.add_masked_expression(inside_expression, outside_expression)

    def add_condition(self, expression, comparator, threshold):
        for pool in self.pools:
            pool.add_condition(expression, comparator, threshold)

    def add_and_or_condition(self, first_condition, second_condition, is_and):
        success_code = self.representative.add_and_or_condition(first_condition, second_condition, is_and)
        if success_code not in (0, 1):
            return success_code
        for pool in self.pools[1:]:
            pool.add_and_or_condition(first_condition, second_condition, is_and)
        return success_code

    def vars(self):
        return self.representative.vars

    def var_names(self):
        return self.representative.var_names

    def nb_expressions(self):
        return self.representative.nb_expressions

    def expressions(self):
        return self.representative.expressions

    def nb_masks(self):
        return self.representative.nb_masks

    def masks(self):
        return self.representative.masks

    def nb_conditions(self):
        return self.representative.nb_conditions

    def conditions(self):
        return self.representative.conditions

    def get_expression(self, text):
        return self.representative.get_expression(text)

    def get_condition(self, text):
        return self.representative.get_condition(text)

    def get_mask(self, text):
        return self.representative.get_mask(text)

    def ready_for_conditional_expression(self):
        return self.representative.ready_for_conditional_expression()

    def ready_for_max_min_expression(self):
        return self.representative.ready_for_max_min_expression()

    def ready_for_masked_expression(self):
        return self.representative.ready_for_masked_expression()

    def evaluable_expressions(self):
        for code, text in self.representative.evaluable_expressions():
            yield code, text

    def output_headers(self, selected_names):
        for data in self.input_data:
            output_header = data.header.copy()
            output_header.nb_var = len(selected_names)
            output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
            for name in selected_names:
                output_header.var_IDs.append('DUMMY')
                output_header.var_names.append(bytes(name, 'utf-8').ljust(16))
                output_header.var_units.append(bytes('', 'utf-8').ljust(16))
            yield output_header

    def build_augmented_path(self, selected_expressions):
        augmented_path = self.representative.get_dependence(selected_expressions[0])
        for expr in selected_expressions[1:]:
            path = self.representative.get_dependence(expr)
            for node in path:
                if node not in augmented_path:
                    augmented_path.append(node)
        return augmented_path

    def evaluate_iterator(self, selected_names):
        for data, output_header, pool in zip(self.input_data, self.output_headers(selected_names), self.pools):
            yield data.filename, data.header, output_header, pool



