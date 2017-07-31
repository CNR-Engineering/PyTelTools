"""!
Similarity transformations between multiple coordinate systems
"""

import numpy as np
import scipy.optimize


class Transformation:
    """!
    @brief Transformation between two coordinate systems
    A transformation is a composition of rotation, scaling and translation on 3d vectors.
    """
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
        """!
        @brief The inverse transformation
        The inverse transformation is a transformation with inverse rotation, inverse scaling
        and a translation vector that is equal to the result of inverse rotation and inverse scaling
        of the inverse translation vector
        """
        inverse_rotation = self.rotation.inverse()
        inverse_scaling = self.scaling.inverse()
        inverse_translation = self.translation.inverse()
        inverse_dx, inverse_dy, inverse_dz = inverse_scaling.vector * \
                                             inverse_rotation.rotation_matrix.dot(inverse_translation.vector)
        return Transformation(inverse_rotation.angle,
                              inverse_scaling.horizontal_factor, inverse_scaling.vertical_factor,
                              inverse_dx, inverse_dy, inverse_dz)


class Rotation:
    """!
    @brief Rotation around z axis
    """
    def __init__(self, angle):
        self.angle = angle
        cos = np.cos(self.angle)
        sin = np.sin(self.angle)
        self.rotation_matrix = np.array([[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]])

    def inverse(self):
        return Rotation(-self.angle)


class Scaling:
    """!
    @brief Heterogeneous scaling along xy axis and along z axis
    The scaling factors along x and along y are restricted to be equal
    """
    def __init__(self, horizontal_factor, vertical_factor):
        self.horizontal_factor = horizontal_factor
        self.vertical_factor = vertical_factor
        self.vector = np.array([horizontal_factor, horizontal_factor, vertical_factor])

    def inverse(self):
        return Scaling(1/self.horizontal_factor, 1/self.vertical_factor)


class Translation:
    """!
    @brief Translation of 3d vectors
    """
    def __init__(self, dx, dy, dz):
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.vector = np.array([dx, dy, dz])

    def inverse(self):
        return Translation(-self.dx, -self.dy, -self.dz)


# the identity transformation
IDENTITY = Transformation(0, 1, 1, 0, 0, 0)


class TransformationMap:
    """!
    @brief Transformations between multiple coordinate systems
    A transformation has a list of coordinate systems with labels
    and a spanning tree of transformations (between two systems)
    """
    def __init__(self, labels, transformations):
        self.labels = labels
        self.transformations = transformations
        self.nodes = list(range(len(labels)))

        self.adj = {}
        for i in self.nodes:
            self.adj[i] = set()
        for u, v in self.transformations.keys():
            self.adj[u].add(v)

    def _path(self, from_node, to_node):
        """!
        @brief ad hoc function for finding the path from from_node to to_node in the spanning tree
        """
        visited = {}
        for node in self.nodes:
            visited[node] = False

        stack = [from_node]
        parent = {}
        while stack:
            current_node = stack.pop()
            visited[current_node] = True
            for neighbor in self.adj[current_node]:
                if not visited[neighbor]:
                    stack.append(neighbor)
                    parent[neighbor] = current_node

        path = []
        current_node = to_node
        while current_node != from_node:
            previous_node = parent[current_node]
            path.append((previous_node, current_node))
            current_node = previous_node
        path.reverse()
        return path

    def get_transformation(self, from_index, to_index):
        """!
        @brief Get the series of transformations needed to transform coordinates in the first system to the second
        @param <int> from_index: the index of the first coordinate system
        @param <int> to_index: the index of the second coordinate system
        @return <list of Transformation>: the list of transformations from the first system to the second
        """
        if from_index == to_index:
            return [IDENTITY]
        path = self._path(from_index, to_index)
        return [self.transformations[i, j] for i, j in path]


def transformation_optimization(from_points, to_points, ignore_z):
    """!
    @brief Wrapper for optimization methods for transformations from one coordinate system to another
    @param <list> from_points: coordinates of points in the first coordinate system
    @param <list> to_points: the coordinates of the same points in the second coordinate system
    @param <bool> ignore_z: if True, optimize for 4 parameters instead of 6 (identity along z-axis)
    @return <tuple>: the final transformation, final cost function value, boolean indicating success and a message
    """
    if ignore_z:
        return four_parameters_optimization(from_points, to_points)
    return six_parameters_optimization(from_points, to_points)


def four_parameters_optimization(from_points, to_points):
    """!
    @brief Optimize four parameters of the transformation from one coordinate system to another (identity along z-axis)
    @param <list> from_points: coordinates of points in the first coordinate system
    @param <list> to_points: the coordinates of the same points in the second coordinate system
    @return <tuple>: the final transformation, final cost function value, boolean indicating success and a message
    """
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
    """!
    @brief Optimize all six parameters of the transformation from one coordinate system to another
    @param <list> from_points: coordinates of points in the first coordinate system
    @param <list> to_points: the coordinates of the same points in the second coordinate system
    @return <tuple>: the final transformation, final cost function value, boolean indicating success and a message
    """
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


def is_connected(nodes, edge_list):
    """!
    @brief ad hoc function for checking if an undirected graph is connected
    @param <list> nodes: the list of nodes in the graph
    @param <iterable> edge_list: edges in the graph
    @return <bool>: True if the graph is connected
    """
    adj = {}
    for i in nodes:
        adj[i] = set()
    for u, v in edge_list:
        adj[u].add(v)

    visited = {}
    for node in nodes:
        visited[node] = False

    stack = [nodes[0]]
    while stack:
        current_node = stack.pop()
        if not visited[current_node]:
            visited[current_node] = True
            for neighbor in adj[current_node]:
                stack.append(neighbor)
    return all(visited.values())


def load_transformation_map(filename):
    """!
    @brief Load and build the transformation map from configuration file
    @param <str> filename: path to the input file
    @return <tuple>: boolean indicating if the file is valid, and the TransformationMap object
    """
    try:
        with open(filename, 'r') as f:
            labels = f.readline().rstrip().split('|')
            f.readline()  # line for graphical objects
            transformations = {}
            for line in f.readlines():
                i, j, params = line.rstrip().split('|')
                i, j = int(i), int(j)
                angle, scalexy, scalez, dx, dy, dz = map(float, params.split())
                transformations[i, j] = Transformation(angle, scalexy, scalez, dx, dy, dz)
                transformations[j, i] = transformations[i, j].inverse()
        if len(labels) < 2:
                raise ValueError
        if not is_connected(list(range(len(labels))), transformations.keys()):
            raise ValueError
    except (ValueError, IndexError):
        return False, None
    return True, TransformationMap(labels, transformations)
