"""!
Simple computation/evaluation of variable values in Serafin
"""

import numpy as np
import re
import shapefile

from . import Serafin
from .util import logger
from .variables import do_calculation, get_available_variables, get_necessary_equations


# constants
OPERATORS = ['+', '-', '*', '/', '^', 'sqrt', 'sin', 'cos', 'atan']
MAX, MIN, MEAN, ARRIVAL_DURATION, PROJECT, DIFF, REV_DIFF, \
    MAX_BETWEEN, MIN_BETWEEN, SYNCH_MAX, LAYER_SELECTION = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

OPERATIONS = {'+': np.add, '-': np.subtract, '*': np.multiply, '/': np.divide, '^': np.power,
               'sqrt': np.sqrt, 'sin': np.sin, 'cos': np.cos, 'atan': np.arctan}
_PRECEDENCE = {'(': 1, '-': 2, '+': 2, '*': 3, '/': 3, '^': 4, 'sqrt': 5, 'sin': 5, 'cos': 5, 'atan': 5}

_VECTORS = {'U': ('V', 'M'), 'V': ('U', 'M'), 'QSX': ('QSY', 'QS'), 'QSY': ('QSX', 'QS'),
            'QSBLX': ('QSBLY', 'QSBL'), 'QSBLY': ('QSBLX', 'QSBL'),
            'QSSUSPX': ('QSSUSPY', 'QSSUSP'), 'QSSUSPY': ('QSSUSPX', 'QSSUSP'),
            'I': ('J', 'Q'), 'J': ('I', 'Q')}
_VECTORS_BROTHERS = {('U', 'V'): 'M', ('I', 'J'): 'Q', ('X', 'Y'): '.', ('QSX', 'QSY'): 'QS',
                     ('QSBLX', 'QSBLY'): 'QSBL', ('QSSUSPX', 'QSSUSPY'): 'QSSUSP'}

_VECTORS_2D = {('U', 'V'): {'fr': 'VITESSE', 'en': 'VELOCITY'},
               ('I', 'J'): {'fr': 'DEBIT', 'en': 'FLOWRATE'}, ('X', 'Y'): {'fr': 'VENT', 'en': 'WIND'},
               ('QSX', 'QSY'): {'fr': 'DEBIT_SOLIDE', 'en': 'SOLID_DISCHARGE'},
               ('QSBLX', 'QSBLY'): {'fr': 'QS_CHARRIAGE', 'en': 'QS_BEDLOAD'},
               ('QSSUPSX', 'QSSUSPY'): {'fr': 'QS_SUSPENSION', 'en': 'QS_SUSPENSION'}}
_VECTORS_3D = {('U', 'V', 'W'): {'fr': 'VITESSE', 'en': 'VELOCITY'},
               ('NUX', 'NUY', 'NUZ'): {'fr': 'NU_POUR_VITESSE', 'en': 'NU_FOR_VELOCITY'},
               ('UCONV', 'VCONV', 'WCONV'): {'fr': 'CONVECTION', 'en': 'ADVECTION'}}


def scalars_vectors(known_vars, selected_vars, us_equation=None):
    """!
    @brief Separate the scalars from vectors, allowing different max/min computations
    @param known_vars <list>: the list of variable IDs with known values
    @param selected_vars <str>: the selected variables IDs
    @return <tuple>: the list of scalars, the list of vectors, the list of additional equations for magnitudes
    """
    scalars = []
    vectors = []
    computable_variables = list(map(lambda x: x.ID(), get_available_variables(known_vars, is_2d=True)))
    additional_equations = get_necessary_equations(known_vars, list(map(lambda x: x[0], selected_vars)),
                                                   is_2d=True, us_equation=us_equation)
    for var, name, unit in selected_vars:
        if var in _VECTORS:
            brother, mother = _VECTORS[var]
            if mother in known_vars:  # if the magnitude is known
                vectors.append((var, name, unit))
            elif brother in known_vars:  # if the magnitude is unknown but the orthogonal field is known
                vectors.append((var, name, unit))
                additional_equations.extend(get_necessary_equations(known_vars, [mother],
                                                                    is_2d=True, us_equation=us_equation))
            else:
                if mother in computable_variables:
                    vectors.append((var, name, unit))
                    additional_equations.extend(get_necessary_equations(known_vars, [mother],
                                                                        is_2d=True, us_equation=us_equation))
                    continue
                # if the magnitude is not computable, use scalar operation instead
                logger.warning('The variable %s will be considered to be scalar instead of vector.' % var)
                scalars.append((var, name, unit))
        else:
            scalars.append((var, name, unit))
    additional_equations = list(set(additional_equations))
    additional_equations.sort(key=lambda x: x.output.order)
    return scalars, vectors, additional_equations


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
    @param input_stream <slf.Serafin.Read>: the input Serafin
    @param time_index <int>: the index of the frame
    @param expression <list>: the expression to evaluate in postfix format
    @return <numpy.1D-array>: the value of the expression
    """
    stack = []

    for symbol in expression:
        if symbol in OPERATORS:
            if symbol in ('sqrt', 'sin', 'cos', 'atan'):
                operand = stack.pop()
                stack.append(OPERATIONS[symbol](operand))
            else:
                first_operand = stack.pop()
                second_operand = stack.pop()
                stack.append(OPERATIONS[symbol](first_operand, second_operand))
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


def detect_vector_vtk(is_2d, variables, variable_names, language):
    scalars, vectors, names = [], [], {}
    if is_2d:
        for couple, name_dic in _VECTORS_2D.items():
            if all(u in variables for u in couple):
                vectors.append(couple)
                names[couple] = name_dic[language]
    else:
        for triple, name_dic in _VECTORS_3D.items():
            if all(u in variables for u in triple):
                vectors.append(triple)
                names[triple] = name_dic[language]
    var_vectors = sum(vectors, ())
    for var in variables:
        if var not in var_vectors:
            scalars.append(var)
            names[var] = variable_name_to_vtk(variable_names[var][0].decode(Serafin.SLF_EIT).strip())
    return scalars, vectors, names


def variable_name_to_vtk(name):
    # replace whitespaces by underscores
    return ''.join([s for s in name if s != ' '])


def slf_to_shp(slf_name, slf_header, shp_name, variables, time_index):
    # separate vectors from scalars
    coupled, non_coupled, mothers, angles = detect_vector_couples(variables, slf_header.var_IDs)

    # fetch all variables values
    values = {}
    with Serafin.Read(slf_name, slf_header.language) as input_stream:
        input_stream.header = slf_header
        for var in variables:
            values[var] = input_stream.read_var_in_frame(time_index, var)

    # compute mothers not in the file
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


def slf_to_xml(slf_name, slf_header, xml_name, scalar, time_index):
    """!
    @brief Write LandXML file from a scalar variable of a Serafin file
    @param slf_name <str>: path to the input Serafin file
    @param slf_header <slf.Serafin.SerafinHeader>: input Serafin header
    @param xml_name <str>: output LandXML filename
    @param scalar <str>: variable to write
    @param time_index <int>: the index of the frame (0-based)
    """
    # fetch scalar variable values
    with Serafin.Read(slf_name, slf_header.language) as input_stream:
        input_stream.header = slf_header
        scalar_values = input_stream.read_var_in_frame(time_index, scalar)

    # write LandXML
    with open(xml_name, 'w') as xml:
        xml.write('<?xml version="1.0" ?>\n')
        xml.write('<!-- Title: %s -->\n' % slf_header.title.decode(Serafin.SLF_EIT).strip())
        xml.write('<!-- This file contains x and y reversed in purpose (because arcpy is buggy) -->\n')
        xml.write('<LandXML version="1.2" xmlns="http://www.landxml.org/schema/LandXML-1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.landxml.org/schema/LandXML-1.2 http://www.landxml.org/schema/LandXML-1.2/LandXML-1.2.xsd">\n')
        xml.write('  <Surfaces>\n')
        xml.write('    <Surface name="%s at frame %i/%i">\n' % (scalar, time_index+1, slf_header.nb_frames))
        xml.write('      <Definition surfType="TIN">\n')
        xml.write('        <Pnts>\n')
        for i, (x, y, z) in enumerate(zip(slf_header.x, slf_header.y, scalar_values)):
            xml.write('          <P id="%d">%.4f %.4f %.4f</P>\n' % (i+1, y, x, z))
        xml.write('        </Pnts>\n')
        xml.write('        <Faces>\n')
        for i, (a, b, c) in enumerate(slf_header.ikle_2d):
            xml.write('          <F id="%d">%d %d %d</F>\n' % (i+1, a, b, c))
        xml.write('        </Faces>\n')
        xml.write('      </Definition>\n')
        xml.write('    </Surface>\n')
        xml.write('  </Surfaces>\n')
        xml.write('</LandXML>\n')


def slf_to_vtk(is_2d, slf_name, slf_header, vtk_name, scalars, vectors, variable_names, time_index):
    """!
    @brief Write vtk file from a scalar variable of a Serafin file
    @param is_2d <bool>: True if the input file is 2D
    @param slf_name <str>: path to the input Serafin file
    @param slf_header <slf.Serafin.SerafinHeader>: input Serafin header
    @param vtk_name <str>: output vtk filename
    @param scalars <str>: scalar variables
    @param vectors <tuple of str>: vector variables
    @param time_index <int>: the index of the frame (0-based)
    """
    if is_2d:
        slf_to_vtk_2d(slf_name, slf_header, vtk_name, scalars, vectors, variable_names, time_index)
    else:
        slf_to_vtk_3d(slf_name, slf_header, vtk_name, scalars, vectors, variable_names, time_index)


def slf_to_vtk_2d(slf_name, slf_header, vtk_name, scalars, vectors, variable_names, time_index):
    with Serafin.Read(slf_name, slf_header.language) as input_stream:
        input_stream.header = slf_header

        with open(vtk_name, 'w') as output_stream:
            # write header
            header = '# vtk DataFile Version 2.0\nMesh export\nASCII\nDATASET UNSTRUCTURED_GRID\n\n'
            output_stream.write(header)

            # write vertices
            output_stream.write('POINTS %d float\n' % slf_header.nb_nodes)
            for ix, iy in zip(slf_header.x, slf_header.y):
                output_stream.write('%.6f %.6f 0.\n' % (ix, iy))
            output_stream.write('\n')

            # write cells
            output_stream.write('CELLS %d %d\n' % (slf_header.nb_elements, slf_header.nb_elements * 4))

            ikle = slf_header.ikle_2d - 1
            for k1, k2, k3 in ikle:
                output_stream.write('3 %d %d %d\n' % (k1, k2, k3))
            output_stream.write('\n')

            output_stream.write('CELL_TYPES %d\n' % slf_header.nb_elements)
            for _ in range(slf_header.nb_elements):
                output_stream.write('5\n')
            output_stream.write('\n')

            # write scalar and vector data
            output_stream.write('POINT_DATA %d\n' % slf_header.nb_nodes)

            for scalar in scalars:
                values = input_stream.read_var_in_frame(time_index, scalar)
                name = variable_names[scalar]

                output_stream.write('SCALARS %s float\nLOOKUP_TABLE default\n' % name)
                for v in values:
                    output_stream.write('%.6f\n' % v)
                output_stream.write('\n')

            for triple in vectors:
                u_values = input_stream.read_var_in_frame(time_index, triple[0])
                v_values = input_stream.read_var_in_frame(time_index, triple[1])
                name = variable_names[triple]

                output_stream.write('VECTORS %s float\n' % name)
                for u, v in zip(u_values, v_values):
                    output_stream.write('%.6f %.6f 0.\n' % (u, v))
                output_stream.write('\n')


def slf_to_vtk_3d(slf_name, slf_header, vtk_name, scalars, vectors, variable_names, time_index):
    with Serafin.Read(slf_name, slf_header.language) as input_stream:
        input_stream.header = slf_header

        with open(vtk_name, 'w') as output_stream:
            # write header
            header = '# vtk DataFile Version 2.0\nMesh export\nASCII\nDATASET UNSTRUCTURED_GRID\n\n'
            output_stream.write(header)

            # read z values
            z = input_stream.read_var_in_frame(time_index, 'Z')

            # write vertices
            output_stream.write('POINTS %d float\n' % slf_header.nb_nodes)
            for ix, iy, iz in zip(slf_header.x, slf_header.y, z):
                output_stream.write('%.6f %.6f %.6f\n' % (ix, iy, iz))
            output_stream.write('\n')

            # write cells
            output_stream.write('CELLS %d %d\n' % (slf_header.nb_elements, slf_header.nb_elements * 7))

            ikle = slf_header.ikle.reshape(slf_header.nb_elements, 6) - 1
            for k1, k2, k3, k4, k5, k6 in ikle:
                output_stream.write('6 %d %d %d %d %d %d\n' % (k1, k2, k3, k4, k5, k6))
            output_stream.write('\n')

            output_stream.write('CELL_TYPES %d\n' % slf_header.nb_elements)
            for _ in range(slf_header.nb_elements):
                output_stream.write('13\n')
            output_stream.write('\n')

            # write scalar and vector data
            output_stream.write('POINT_DATA %d\n' % slf_header.nb_nodes)

            for scalar in scalars:
                values = input_stream.read_var_in_frame(time_index, scalar)
                name = variable_names[scalar]

                output_stream.write('SCALARS %s float\nLOOKUP_TABLE default\n' % name)
                for v in values:
                    output_stream.write('%.6f\n' % v)
                output_stream.write('\n')

            for triple in vectors:
                u_values = input_stream.read_var_in_frame(time_index, triple[0])
                v_values = input_stream.read_var_in_frame(time_index, triple[1])
                w_values = input_stream.read_var_in_frame(time_index, triple[2])
                name = variable_names[triple]

                output_stream.write('VECTORS %s float\n' % name)
                for u, v, w in zip(u_values, v_values, w_values):
                    output_stream.write('%.6f %.6f %.6f\n' % (u, v, w))
                output_stream.write('\n')


class ScalarMaxMinMeanCalculator:
    """!
    Compute max/min/mean of 2D scalar variables from a Serafin input stream
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
    Compute max/min/mean of vector variables from a Serafin input stream
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
    Compute arrival/duration of conditions from a Serafin input stream
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
