import numpy as np

from slf.misc import tighten_expression, OPERATORS, OPERATIONS


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
                    stack.append(OPERATIONS[symbol](operand))
                else:
                    first_operand = stack.pop()
                    second_operand = stack.pop()
                    stack.append(OPERATIONS[symbol](first_operand, second_operand))
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
