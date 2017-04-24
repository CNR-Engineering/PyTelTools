import numpy as np


BASIC_VARIABLES = {}

ordered_IDs = ['H', 'U', 'V', 'M', 'S', 'B', 'I', 'J', 'Q']


class BasicVariable():
    def __init__(self, ID, name_fr, name_en, unit):
        self.ID = ID
        self.name_fr = name_fr
        self.name_en = name_en
        self.unit = unit

    def __repr__(self):
        return ', '.join([self.ID, self.name_fr.decode('utf-8'),
                          self.name_en.decode('utf-8'), self.unit.decode('utf-8')])

    def name(self, language):
        if language == 'fr':
            return self.name_fr
        return self.name_en

    def ID(self):
        return self.ID

    def unit(self):
        return self.unit


def build_variables():
    spec = """U,VITESSE U,VELOCITY U,M/S
V,VITESSE V,VELOCITY V,M/S
H,HAUTEUR D'EAU,WATER DEPTH,M
S,SURFACE LIBRE,FREE SURFACE,M
B,FOND ,BOTTOM,M
Q,DEBIT SCALAIRE,SCALAR FLOWRATE,M2/S
I,DEBIT SUIVANT X,FLOWRATE ALONG X,M2/S
J,DEBIT SUIVANT Y,FLOWRATE ALONG Y,M2/S
M,VITESSE SCALAIRE,SCALAR VELOCITY,M/S"""

    for i, row in enumerate(spec.split('\n')):
        ID, name_fr, name_en, unit = row.split(',')
        BASIC_VARIABLES[i] = BasicVariable(ID, bytes(name_fr, 'utf-8').ljust(16), bytes(name_en, 'utf-8').ljust(16),
                                           bytes(unit, 'utf-8').ljust(16))

build_variables()
H, U, V, M, S, B, I, J, Q = [BASIC_VARIABLES[i] for i in range(len(ordered_IDs))]


code = {var: i for i, var in enumerate(ordered_IDs)}
inverse_code = {i: var for i, var in enumerate(ordered_IDs)}


MINUS, TIMES, NORM2 = 0, 1, 2
OPERATIONS = {MINUS: lambda a, b: a-b,
              TIMES: lambda a, b: a*b,
              NORM2: lambda a, b: np.sqrt(np.square(a) + np.square(b))}


EQUATIONS = [((S, B), H, (MINUS,)), ((H, B), S, (MINUS,)),
             ((U, V), M, (NORM2,)), ((H, U), I, (TIMES,)),
             ((H, V), J, (TIMES,)), ((I, J), Q, (NORM2,))]



def is_basic_variable(var_ID):
    return var_ID in ordered_IDs


def is_solvable(variables, known_variables):
    return all(map(lambda x: x in known_variables, variables))


def all_computables(vars):
    computables = set(code[var] for var in vars)
    computations = []
    while True:
        found_new_computable = False
        for equation in EQUATIONS:
            variables, unknown, _ = equation
            if unknown in computables:
                continue
            solvable = is_solvable(variables, computables)
            if solvable:
                found_new_computable = True
                computables.add(unknown)
                computations.append(equation)
        if not found_new_computable:
            break
    return computables, computations


def get_new_var_IDs(input_vars):
    computables, computations = all_computables(filter(is_basic_variable, input_vars))

    # for vars, unknown, operators in computations:
    #     print('can compute', inverse_code[unknown], 'with', list(map(inverse_code.get, vars)), operators[0])

    return list(map(inverse_code.get, map(lambda x: x[1], computations)))

