import os
import struct
import numpy as np
from datetime import datetime
from multiprocessing import Process, Queue, cpu_count
from shapely.geometry import Polygon

from workflow.datatypes import SerafinData, PolylineData, CSVData
from geom import BlueKenue, Shapefile
import slf.misc as operations
from slf import Serafin
from slf.volume import TruncatedTriangularPrisms, VolumeCalculator


class Workers:
    def __init__(self):
        self.nb_processes = cpu_count()
        self.started = False
        self.stopped = False
        self.task_queue = Queue()
        self.done_queue = Queue()

        self.processes = []
        for i in range(self.nb_processes):
            self.processes.append(Process(target=worker, args=(self.task_queue, self.done_queue)))

    def add_tasks(self, tasks):
        for task in tasks:
            self.task_queue.put(task)

    def start(self):
        for p in self.processes:
            p.start()
        self.started = True

    def stop(self):
        for i in range(self.nb_processes):
            self.task_queue.put('STOP')
        self.stopped = True


def worker(input, output):
    for func, args in iter(input.get, 'STOP'):
        result = func(*args)
        output.put(result)


def success_message(node_name, job_id, info=''):
    return '== %s - SUCCESS == %s (%s)%s.' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), node_name, job_id,
                                              ': %s.' % info if info else '')


def fail_message(reason, node_name, job_id):
    return '== %s - FAIL == %s (%s): %s.' % \
          (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), node_name, job_id, reason)


def read_slf(node_id, fid, filename, language, job_id):
    data = SerafinData(job_id, filename, language)
    success = data.read()
    if not success:
        message = fail_message('file is not 2D', 'Load Serafin', job_id)
    else:
        message = success_message('Load Serafin', job_id)
    return success, node_id, fid, data, message


def read_polygons(node_id, filename):
    try:
        with open(filename) as f:
            pass
    except PermissionError:
        message = fail_message('access denied', 'Load 2D Polygons', 'all')
        return False, node_id, None, message

    data = PolylineData()
    is_i2s = filename[-4:] == '.i2s'
    if is_i2s:
        with BlueKenue.Read(filename) as f:
            f.read_header()
            for poly in f.get_polygons():
                data.add_line(poly)
        data.set_fields(['Value'])
    else:
        try:
            for polygon in Shapefile.get_polygons(filename):
                data.add_line(polygon)
        except struct.error:
            message = fail_message('inconsistent bytes', 'Load 2D Polygons', 'all')
            return False, node_id, None, message

        data.set_fields(Shapefile.get_all_fields(filename))

    if data.is_empty():
        message = fail_message('the file does not contain any polygon', 'Load 2D Polygons', 'all')
        return False, node_id, None, message

    return True, node_id, data, success_message('Load 2D Polygons', 'all')


def compute_max(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Compute Max', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MAX
    return True, node_id, fid, new_data, success_message('Compute Max', data.job_id)


def compute_min(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Compute Min', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MIN
    return True, node_id, fid, new_data, success_message('Compute Min', data.job_id)


def write_slf(node_id, fid, data, options):
    suffix, in_source_folder, dir_path, double_name, overwrite = options

    input_name = os.path.split(data.filename)[1][:-4]
    if double_name:
        output_name = input_name + '_' + data.job_id + suffix + '.slf'
    else:
        output_name = input_name + suffix + '.slf'
    if in_source_folder:
        filename = os.path.join(os.path.split(data.filename)[0], output_name)
    else:
        if not os.path.exists(dir_path):
            return False, node_id, fid, None, fail_message('output folder not found', 'Write Serafin', data.job_id)
        filename = os.path.join(dir_path, output_name)
    if not overwrite:
        if os.path.exists(filename):
            new_data = SerafinData(data.job_id, filename, data.language)
            new_data.read()
            return True, node_id, fid, data, success_message('Write Serafin', data.job_id, 'reload existing file')

    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Write Serafin', data.job_id)

    if data.operator in (operations.MAX, operations.MIN, operations.MEAN):
        success, message = run_max_min_mean(data, filename)
    else:
        success, message = True, success_message('Write Serafin', data.job_id)

    return success, node_id, fid, data, message


def run_max_min_mean(input_data, filename):
    selected = [(var, input_data.selected_vars_names[var][0],
                      input_data.selected_vars_names[var][1]) for var in input_data.selected_vars]
    scalars, vectors, additional_equations = operations.scalars_vectors(input_data.header.var_IDs,
                                                                        selected,
                                                                        input_data.us_equation)
    output_header = input_data.header.copy()
    output_header.nb_var = len(scalars) + len(vectors)
    output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
    for var_ID, var_name, var_unit in scalars + vectors:
        output_header.var_IDs.append(var_ID)
        output_header.var_names.append(var_name)
        output_header.var_units.append(var_unit)
    if input_data.to_single:
        output_header.to_single_precision()

    with Serafin.Read(input_data.filename, input_data.language) as input_stream:
        input_stream.header = input_data.header
        input_stream.time = input_data.time
        has_scalar, has_vector = False, False
        scalar_calculator, vector_calculator = None, None
        if scalars:
            has_scalar = True
            scalar_calculator = operations.ScalarMaxMinMeanCalculator(input_data.operator, input_stream,
                                                                      scalars, input_data.selected_time_indices,
                                                                      additional_equations)
        if vectors:
            has_vector = True
            vector_calculator = operations.VectorMaxMinMeanCalculator(input_data.operator, input_stream,
                                                                      vectors, input_data.selected_time_indices,
                                                                      additional_equations)
        for i, time_index in enumerate(input_data.selected_time_indices):

            if has_scalar:
                scalar_calculator.max_min_mean_in_frame(time_index)
            if has_vector:
                vector_calculator.max_min_mean_in_frame(time_index)

        if has_scalar and not has_vector:
            values = scalar_calculator.finishing_up()
        elif not has_scalar and has_vector:
            values = vector_calculator.finishing_up()
        else:
            values = np.vstack((scalar_calculator.finishing_up(), vector_calculator.finishing_up()))

        with Serafin.Write(filename, input_data.language, True) as resout:
            resout.write_header(output_header)
            resout.write_entire_frame(output_header, input_data.time[0], values)

    return True, success_message('Write Serafin', input_data.job_id)


def construct_mesh(mesh):
    for i, j, k in mesh.ikle:
        t = Polygon([mesh.points[i], mesh.points[j], mesh.points[k]])
        mesh.triangles[i, j, k] = t
        mesh.index.insert(i, t.bounds, obj=(i, j, k))


def compute_volume(node_id, fid, data, aux_data, options, csv_separator):
    # process options
    first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite = options

    input_name = os.path.split(data.filename)[1][:-4]
    if double_name:
        output_name = input_name + '_' + data.job_id + suffix + '.csv'
    else:
        output_name = input_name + suffix + '.csv'
    if in_source_folder:
        filename = os.path.join(os.path.split(data.filename)[0], output_name)
    else:
        filename = os.path.join(dir_path, output_name)
    if not overwrite:
        if os.path.exists(filename):
            csv_data = CSVData(data.filename, None, filename)
            csv_data.metadata = {'var': first_var, 'second var': second_var,
                                 'start time': data.start_time, 'language': data.language}
            return True, node_id, fid, csv_data, success_message('Compute Volume', data.job_id, 'reload existing file')

    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Compute Volume', data.job_id)

    polygons = aux_data.lines
    polygon_names = ['Polygon %d' % (i+1) for i in range(len(polygons))]
    if sup_volume:
        volume_type = VolumeCalculator.POSITIVE
    else:
        volume_type = VolumeCalculator.NET

    # prepare the mesh
    mesh = TruncatedTriangularPrisms(data.header, False)

    if data.has_index:
        mesh.index = data.index
        mesh.triangles = data.triangles
    else:
        construct_mesh(mesh)
        data.has_index = True
        data.index = mesh.index
        data.triangles = mesh.triangles

    # run the calculator
    with Serafin.Read(data.filename, data.language) as resin:
        resin.header = data.header
        resin.time = data.time

        calculator = VolumeCalculator(volume_type, first_var, second_var, resin,
                                      polygon_names, polygons, 1)
        calculator.time_indices = data.selected_time_indices
        calculator.mesh = mesh
        calculator.construct_weights()

        csv_data = CSVData(data.filename, calculator.get_csv_header())
        csv_data.metadata = {'var': first_var, 'second var': second_var,
                             'start time': data.start_time, 'language': data.language}

        for i, time_index in enumerate(calculator.time_indices):
            i_result = [str(calculator.input_stream.time[time_index])]
            values = calculator.read_values_in_frame(time_index)

            for j in range(len(calculator.polygons)):
                weight = calculator.weights[j]
                volume = calculator.volume_in_frame_in_polygon(weight, values, calculator.polygons[j])
                if calculator.volume_type == VolumeCalculator.POSITIVE:
                    for v in volume:
                        i_result.append('%.6f' % v)
                else:
                    i_result.append('%.6f' % volume)
            csv_data.add_row(i_result)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, success_message('Compute Volume', data.job_id)


FUNCTIONS = {'Max': compute_max, 'Min': compute_min, 'Write Serafin': write_slf,
             'Load 2D Polygons': read_polygons, 'Compute Volume': compute_volume}


