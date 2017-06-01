import numpy as np
import scipy.optimize


class Transformation:
    def __init__(self, angle, horizontal_factor, vertical_factor, dx, dy, dz):
        self.rotation = Rotation(angle)
        self.scaling = Scaling(horizontal_factor, vertical_factor)
        self.translation = Translation(dx, dy, dz)

    def __repr__(self):
        return ' '.join(map(str, [self.rotation.angle, self.scaling.horizontal_factor, self.scaling.vertical_factor,
                                  self.translation.dx, self.translation.dy, self.translation.dz]))

    def __call__(self, coordinates):
        return self.translation.vector + self.scaling.vector * self.rotation.rotation_matrix.dot(coordinates)

    def __str__(self):
        return '\n'.join(['Rotation:\t%.4f (rad)' % self.rotation.angle,
                          'Scaling:\tXY %.4f \tZ %.4f ' %
                          (self.scaling.horizontal_factor, self.scaling.vertical_factor),
                          'Translation:\tX %.4f \t Y %.4f \t Z %.4f' %
                          (self.translation.dx, self.translation.dy, self.translation.dz)])

    def inverse(self):
        inverse_rotation = self.rotation.inverse()
        inverse_scaling = self.scaling.inverse()
        inverse_translation = self.translation.inverse()
        inverse_dx, inverse_dy, inverse_dz = inverse_scaling.vector * \
                                             inverse_rotation.rotation_matrix.dot(inverse_translation.vector)
        return Transformation(inverse_rotation.angle,
                              inverse_scaling.horizontal_factor, inverse_scaling.vertical_factor,
                              inverse_dx, inverse_dy, inverse_dz)


class Rotation:
    def __init__(self, angle):
        self.angle = angle
        cos = np.cos(self.angle)
        sin = np.sin(self.angle)
        self.rotation_matrix = np.array([[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]])

    def inverse(self):
        return Rotation(-self.angle)


class Scaling:
    def __init__(self, horizontal_factor, vertical_factor):
        self.horizontal_factor = horizontal_factor
        self.vertical_factor = vertical_factor
        self.vector = np.array([horizontal_factor, horizontal_factor, vertical_factor])

    def inverse(self):
        return Scaling(1/self.horizontal_factor, 1/self.vertical_factor)


class Translation:
    def __init__(self, dx, dy, dz):
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.vector = np.array([dx, dy, dz])

    def inverse(self):
        return Translation(-self.dx, -self.dy, -self.dz)


def transformation_optimization(from_points, to_points, ignore_z):
    if ignore_z:
        return four_parameters_optimization(from_points, to_points)
    return six_parameters_optimization(from_points, to_points)


def four_parameters_optimization(from_points, to_points):
    def sum_square_error(x):
        angle, horizontal_factor, dx, dy = x
        transform = Transformation(angle, horizontal_factor, 1, dx, dy, 0)
        return sum([sum(np.square(transform(p1)-p2)) for p1, p2 in zip(from_points, to_points)])

    def jacobian(x):
        angle, horizontal_factor, dx, dy = x
        transform = Transformation(angle, horizontal_factor, 1, dx, dy, 0)
        errors = [transform(p1)-p2 for p1, p2 in zip(from_points, to_points)]
        cos = np.cos(angle)
        sin = np.sin(angle)

        jac = np.zeros_like(x)
        jac[0] = 2 * horizontal_factor * sum(v[0] * (-p[0]*sin - p[1]*cos) + v[1] * (p[0]*cos - p[1]*sin)
                                             for p, v in zip(from_points, errors))
        jac[1] = 2 * sum(v[0] * (p[0]*cos - p[1]*sin) + v[1] * (p[0]*sin + p[1]*cos)
                         for p, v in zip(from_points, errors))
        jac[2] = 2 * sum(v[0] for v in errors)
        jac[3] = 2 * sum(v[1] for v in errors)
        return jac

    x0 = np.array([0, 1, 0, 0])
    res = scipy.optimize.minimize(sum_square_error, x0, method='BFGS',
                                  jac=jacobian, options={'gtol': 1e-3})
    angle, horizontal_factor, dx, dy = res.x
    if horizontal_factor < 0:
        horizontal_factor *= -1
        angle += np.pi
    transform = Transformation(angle, horizontal_factor, 1, dx, dy, 0)
    final_value = sum([sum(np.square(transform(p1)-p2)) for p1, p2 in zip(from_points, to_points)])
    return transform, final_value, res.success, res.message


def six_parameters_optimization(from_points, to_points):
    def sum_square_error(x):
        angle, horizontal_factor, vertical_factor, dx, dy, dz = x
        transform = Transformation(angle, horizontal_factor, vertical_factor, dx, dy, dz)
        return sum([sum(np.square(transform(p1)-p2)) for p1, p2 in zip(from_points, to_points)])

    def jacobian(x):
        angle, horizontal_factor, vertical_factor, dx, dy, dz = x
        transform = Transformation(angle, horizontal_factor, vertical_factor, dx, dy, dz)
        errors = [transform(p1)-p2 for p1, p2 in zip(from_points, to_points)]
        cos = np.cos(angle)
        sin = np.sin(angle)

        jac = np.zeros_like(x)
        jac[0] = 2 * horizontal_factor * sum(v[0] * (-p[0]*sin - p[1]*cos) + v[1] * (p[0]*cos - p[1]*sin)
                                             for p, v in zip(from_points, errors))
        jac[1] = 2 * sum(v[0] * (p[0]*cos - p[1]*sin) + v[1] * (p[0]*sin + p[1]*cos)
                         for p, v in zip(from_points, errors))
        jac[2] = 2 * sum(v[2] * p[2] for p, v in zip(from_points, errors))
        jac[3] = 2 * sum(v[0] for v in errors)
        jac[4] = 2 * sum(v[1] for v in errors)
        jac[5] = 2 * sum(v[2] for v in errors)
        return jac

    x0 = np.array([0, 1, 1, 0, 0, 0])
    res = scipy.optimize.minimize(sum_square_error, x0, method='BFGS',
                                  jac=jacobian, options={'gtol': 1e-3})
    angle, horizontal_factor, vertical_factor, dx, dy, dz = res.x
    if horizontal_factor < 0:
        horizontal_factor *= -1
        angle += np.pi
    transform = Transformation(angle, horizontal_factor, vertical_factor, dx, dy, dz)
    final_value = sum([sum(np.square(transform(p1)-p2)) for p1, p2 in zip(from_points, to_points)])
    return transform, final_value, res.success, res.message




