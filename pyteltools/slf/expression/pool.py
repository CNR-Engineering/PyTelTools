import numpy as np
from shapely.geometry import Point

from pyteltools.slf.misc import infix_to_postfix, is_valid_expression, is_valid_postfix, to_infix
from pyteltools.slf.Serafin import SLF_EIT

from .expression import ConditionalExpression, MaskedExpression, MaxMinExpression, PolygonalMask, SimpleExpression
from .condition import AndOrCondition, SimpleCondition


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
        names = [name.decode(SLF_EIT).strip() for (var, name)
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
            output_header.empty_variables()
            for name in selected_names:
                output_header.add_variables_str('DUMMY', name, '')
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


