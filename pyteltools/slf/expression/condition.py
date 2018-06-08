import numpy as np


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
