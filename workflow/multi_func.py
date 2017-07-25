import os
import struct
import numpy as np
from datetime import datetime
from multiprocessing import Process, Queue, cpu_count
from shapely.geometry import Polygon

from workflow.datatypes import SerafinData, PolylineData, PointData, CSVData
from geom import BlueKenue, Shapefile
import slf.misc as operations
from slf import Serafin
import slf.variables as variables
from slf.volume import TruncatedTriangularPrisms, VolumeCalculator
from slf.flux import TriangularVectorField, FluxCalculator
from slf.interpolation import MeshInterpolator


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


def worker(input_queue, output_queue):
    for func, args in iter(input_queue.get, 'STOP'):
        result = func(*args)
        output_queue.put(result)


def success_message(node_name, job_id, info='', second_job_id=''):
    return '== %s - SUCCESS == %s (%s%s)%s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), node_name, job_id,
                                               ' AND %s' % second_job_id if second_job_id else '',
                                               ': %s.' % info if info else '')


def fail_message(reason, node_name, job_id, second_job_id=''):
    return '== %s - FAIL == %s (%s%s): %s.' % \
          (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), node_name, job_id,
           ' AND %s' % second_job_id if second_job_id else '',
           reason)


def read_slf(node_id, fid, filename, language, job_id):
    data = SerafinData(job_id, filename, language)
    is_2d = data.read()
    if not is_2d:
        success, message = False, fail_message('file is not 2D', 'Load Serafin', job_id)
    else:
        success, message = True, success_message('Load Serafin', job_id)
    return success, node_id, fid, data, message


def read_slf_3d(node_id, fid, filename, language, job_id):
    data = SerafinData(job_id, filename, language)
    is_2d = data.read()
    if is_2d:
        success, message = False, fail_message('file is not 3D', 'Load Serafin 3D', job_id)
    else:
        success, message = True, success_message('Load Serafin 3D', job_id)
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


def read_polylines(node_id, filename):
    try:
        with open(filename) as f:
            pass
    except PermissionError:
        message = fail_message('access denied', 'Load 2D Open Polylines', 'all')
        return False, node_id, None, message

    data = PolylineData()
    is_i2s = filename[-4:] == '.i2s'
    if is_i2s:
        with BlueKenue.Read(filename) as f:
            f.read_header()
            for poly in f.get_open_polylines():
                data.add_line(poly)
        data.set_fields(['Value'])
    else:
        try:
            for poly in Shapefile.get_open_polylines(filename):
                data.add_line(poly)
        except struct.error:
            message = fail_message('inconsistent bytes', 'Load 2D Open Polylines', 'all')
            return False, node_id, None, message

        data.set_fields(Shapefile.get_all_fields(filename))

    if data.is_empty():
        message = fail_message('the file does not contain any open polyline', 'Load 2D Open Polylines', 'all')
        return False, node_id, None, message

    return True, node_id, data, success_message('Load 2D Open Polylines', 'all')


def read_points(node_id, filename):
    try:
        with open(filename) as f:
            pass
    except PermissionError:
        message = fail_message('access denied', 'Load 2D Points', 'all')
        return False, node_id, None, message

    data = PointData()
    try:
        for point, attribute in Shapefile.get_points(filename):
            data.add_point(point)
            data.add_attribute(attribute)
    except struct.error:
        message = fail_message('inconsistent bytes', 'Load 2D Points', 'all')
        return False, node_id, None, message

    data.set_fields(Shapefile.get_all_fields(filename))

    if data.is_empty():
        message = fail_message('the file does not contain any point', 'Load 2D Points', 'all')
        return False, node_id, None, message

    return True, node_id, data, success_message('Load 2D Points', 'all')


def select_variables(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot select variable after computation',
                                                       'Select Variables', data.job_id)
    us_equation, selected_vars, selected_vars_names = options

    # check if all selected variables are computable
    known_vars = [var for var in data.header.var_IDs if var in data.selected_vars]
    new_vars = known_vars[:]
    new_vars.extend(list(map(lambda x: x.ID(), variables.get_available_variables(new_vars))))
    if us_equation is not None:
        us_vars = []
        variables.add_US(us_vars, known_vars)
        new_vars.extend([x.ID() for x in us_vars])
    if not all(var in new_vars for var in selected_vars):
        return False, node_id, fid, None, fail_message('not all selected variables are available',
                                                       'Select Variables', data.job_id)

    new_data = data.copy()
    new_data.us_equation = us_equation
    new_data.equations = variables.get_necessary_equations(data.header.var_IDs, selected_vars, us_equation)
    new_data.selected_vars = selected_vars
    new_data.selected_vars_names = {}
    for var_ID, (var_name, var_unit) in selected_vars_names.items():
        new_data.selected_vars_names[var_ID] = (var_name, var_unit)
    return True, node_id, fid, new_data, success_message('Select Variables', data.job_id)


def add_rouse(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Add Rouse',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot add Rouse after computation',
                                                       'Add Rouse', data.job_id)
    if 'US' not in data.selected_vars:
        return False, node_id, fid, None, fail_message('US not found', 'Add Rouse', data.job_id)
        
    rouse_table = options[0]
    new_rouse = [rouse_table[i][0] for i in range(len(rouse_table))]
    new_names = [rouse_table[i][1] for i in range(len(rouse_table))]
    old_names = [data.selected_vars_names[var][0].decode('utf-8').strip()
                 for var in data.selected_vars]
    for rouse in new_rouse:
        if rouse in data.selected_vars:
            return False, node_id, fid, None, fail_message('duplicated value', 'Add Rouse', data.job_id)
    for name in new_names:
        if name in old_names:
            return False, node_id, fid, None, fail_message('duplicated name', 'Add Rouse', data.job_id)

    new_data = data.copy()
    new_data.selected_vars.extend([rouse_table[i][0] for i in range(len(rouse_table))])
    for i in range(len(rouse_table)):
        new_data.selected_vars_names[rouse_table[i][0]] = (bytes(rouse_table[i][1], 'utf-8').ljust(16),
                                                           bytes(rouse_table[i][2], 'utf-8').ljust(16))
    new_data.equations = variables.get_necessary_equations(data.header.var_IDs, new_data.selected_vars,
                                                           data.us_equation)
    return True, node_id, fid, new_data, success_message('Add Rouse', data.job_id)


def select_time(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot select time after computation',
                                                       'Select Time', data.job_id)
    if len(data.selected_time_indices) != len(data.time):
        return False, node_id, fid, None, fail_message('cannot re-select time', 'Select Time', data.job_id)

    start_date, end_date, sampling_frequency = options
    available_dates = list(map(lambda x: x + data.start_time, data.time_second))
    if start_date in available_dates:
        start_index = available_dates.index(start_date)
    else:
        return False, node_id, fid, None, fail_message('selected date not available', 'Select Time', data.job_id)
    if end_date in available_dates:
        end_index = available_dates.index(end_date)
    else:
        return False, node_id, fid, None, fail_message('selected date not available', 'Select Time', data.job_id)

    new_data = data.copy()
    new_data.selected_time_indices = list(range(start_index, end_index+1, sampling_frequency))
    return True, node_id, fid, new_data, success_message('Select Time', data.job_id)


def select_single_frame(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot select time after computation', 'Select Time', data.job_id)
    if len(data.selected_time_indices) != len(data.time):
        return False, node_id, fid, None, fail_message('cannot re-select time', 'Select Time', data.job_id)

    selected_date = options[0]
    available_dates = list(map(lambda x: x + data.start_time, data.time_second))
    if selected_date in available_dates:
        selected_index = available_dates.index(selected_date)
    else:
        return False, node_id, fid, None, fail_message('selected date not available', 'Select Time', data.job_id)

    new_data = data.copy()
    new_data.selected_time_indices = [selected_index]
    return True, node_id, fid, new_data, success_message('Select Time', data.job_id)


def select_first_frame(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot select time after computation',
                                                       'Select First Frame', data.job_id)
    if len(data.selected_time_indices) != len(data.time):
        return False, node_id, fid, None, fail_message('cannot re-select time', 'Select First Frame', data.job_id)
    new_data = data.copy()
    new_data.selected_time_indices = [0]
    return True, node_id, fid, new_data, success_message('Select First Frame', data.job_id)


def select_last_frame(node_id, fid, data, options):
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('cannot select time after computation',
                                                       'Select Last Frame', data.job_id)
    if len(data.selected_time_indices) != len(data.time):
        return False, node_id, fid, None, fail_message('cannot re-select time', 'Select Last Frame', data.job_id)
    new_data = data.copy()
    new_data.selected_time_indices = [len(data.time)-1]
    return True, node_id, fid, new_data, success_message('Select Last Frame', data.job_id)


def compute_max(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Max',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Max', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MAX
    return True, node_id, fid, new_data, success_message('Max', data.job_id)


def compute_min(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Min',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Min', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MIN
    return True, node_id, fid, new_data, success_message('Compute Min', data.job_id)


def compute_mean(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Mean',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Mean', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MEAN
    return True, node_id, fid, new_data, success_message('Mean', data.job_id)


def synch_max(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'SynchMax',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'SynchMax', data.job_id)
    var = operations[0]
    available_vars = [var for var in data.selected_vars if var in data.header.var_IDs]
    if var not in available_vars:
        return False, node_id, fid, None, fail_message('variable not available', 'SynchMax', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.SYNCH_MAX
    new_data.metadata = {'var': var}
    return True, node_id, fid, new_data, success_message('SynchMax', data.job_id)


def arrival_duration(node_id, fid, data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Compute Arrival Duration',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Compute Arrival Duration', data.job_id)
    table, conditions, time_unit = options
    needed_vars = set()
    for condition in conditions:
        expression = condition.expression
        for item in expression:
            if item[0] == '[':
                needed_vars.add(item[1:-1])
    available_vars = [var for var in data.selected_vars if var in data.header.var_IDs]
    if not all([var in available_vars for var in needed_vars]):
        return False, node_id, fid, None, fail_message('variable not available', 'Compute Arrival Duration', data.job_id)
    new_data = data.copy()
    new_data.operator = operations.ARRIVAL_DURATION
    new_data.metadata = {'conditions': conditions, 'table': table, 'time unit': time_unit}
    return True, node_id, fid, new_data, success_message('Mean', data.job_id)


def convert_to_single(node_id, fid, data, options):
    if data.header.float_type != 'd':
        return False, node_id, fid, None, fail_message('the input file is not of double-precision format',
                                                       'Convert to Single Precision', data.job_id)
    if data.to_single:
        return False, node_id, fid, None, fail_message('the input data is already converted to single-precision format',
                                                       'Convert to Single Precision', data.job_id)
    new_data = data.copy()
    new_data.to_single = True
    return True, node_id, fid, new_data, success_message('Convert to Single Precision', data.job_id)


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

    if data.operator is None:
        success, message = write_simple_slf(data, filename)
    elif data.operator in (operations.MAX, operations.MIN, operations.MEAN):
        success, message = write_max_min_mean(data, filename)
    elif data.operator == operations.ARRIVAL_DURATION:
        success, message = write_arrival_duration(data, filename)
    elif data.operator == operations.SYNCH_MAX:
        success, message = write_synch_max(data, filename)
    else:
        success, message = write_project_mesh(data, filename)

    new_data = None
    if success:
        new_data = SerafinData(data.job_id, filename, data.language)
        new_data.read()
    return success, node_id, fid, new_data, message


def write_simple_slf(input_data, filename):
    output_header = input_data.default_output_header()
    with Serafin.Read(input_data.filename, input_data.language) as resin:
        resin.header = input_data.header
        resin.time = input_data.time
        with Serafin.Write(filename, input_data.language, True) as resout:
            resout.write_header(output_header)
            for i, time_index in enumerate(input_data.selected_time_indices):
                values = variables.do_calculations_in_frame(input_data.equations, input_data.us_equation,
                                                            resin, time_index, input_data.selected_vars,
                                                            output_header.np_float_type)
                resout.write_entire_frame(output_header, input_data.time[time_index], values)
    return True, success_message('Write Serafin', input_data.job_id)


def write_max_min_mean(input_data, filename):
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
        if has_scalar:
            scalar_calculator.run()
        if has_vector:
            vector_calculator.run()

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


def write_synch_max(input_data, filename):
    selected_vars = [var for var in input_data.selected_vars if var in input_data.header.var_IDs]
    output_header = input_data.header.copy()
    output_header.nb_var = len(selected_vars)
    output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
    for var_ID in selected_vars:
        var_name, var_unit = input_data.selected_vars_names[var_ID]
        output_header.var_IDs.append(var_ID)
        output_header.var_names.append(var_name)
        output_header.var_units.append(var_unit)
    if input_data.to_single:
        output_header.to_single_precision()

    with Serafin.Read(input_data.filename, input_data.language) as input_stream:
        input_stream.header = input_data.header
        input_stream.time = input_data.time

        calculator = operations.SynchMaxCalculator(input_stream, selected_vars, input_data.selected_time_indicies,
                                                   input_data.metadata['var'])
        calculator.run()
        values = calculator.finishing_up()

        with Serafin.Write(filename, input_data.language, True) as output_stream:
            output_stream.write_header(output_header)
            output_stream.write_entire_frame(output_header, input_data.time[0], values)

    return True, success_message('Write Serafin', input_data.job_id)


def write_arrival_duration(input_data, filename):
    conditions, table, time_unit = input_data.metadata['conditions'], \
                                   input_data.metadata['table'], input_data.metadata['time unit']

    output_header = input_data.header.copy()
    output_header.nb_var = 2 * len(conditions)
    output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
    for row in range(len(table)):
        a_name = table[row][1]
        d_name = table[row][2]
        for name in [a_name, d_name]:
            output_header.var_IDs.append('')
            output_header.var_names.append(bytes(name, 'utf-8').ljust(16))
            output_header.var_units.append(bytes(time_unit.upper(), 'utf-8').ljust(16))
    if input_data.to_single:
        output_header.to_single_precision()

    with Serafin.Read(input_data.filename, input_data.language) as input_stream:
        input_stream.header = input_data.header
        input_stream.time = input_data.time
        calculators = []

        for i, condition in enumerate(conditions):
            calculators.append(operations.ArrivalDurationCalculator(input_stream, input_data.selected_time_indices,
                                                                    condition))
        for calculator in calculators:
            calculator.run()

        values = np.empty((2*len(conditions), input_data.header.nb_nodes))
        for i, calculator in enumerate(calculators):
            values[2*i, :] = calculator.arrival
            values[2*i+1, :] = calculator.duration

        if time_unit == 'minute':
            values /= 60
        elif time_unit == 'hour':
            values /= 3600
        elif time_unit == 'day':
            values /= 86400
        elif time_unit == 'percentage':
            values *= 100 / (input_data.time[input_data.selected_time_indices[-1]]
                             - input_data.time[input_data.selected_time_indices[0]])

        with Serafin.Write(filename, input_data.language, True) as resout:
            resout.write_header(output_header)
            resout.write_entire_frame(output_header, input_data.time[0], values)

    return True, success_message('Write Serafin', input_data.job_id)


def write_project_mesh(first_input, filename):
    operation_type = first_input.operator
    second_input = first_input.metadata['operand']

    if second_input.filename == filename:
        return False, fail_message('cannot overwrite to the input file', 'Write Serafin',
                                   first_input.job_id, second_input.job_id)

    # common vars
    first_vars = [var for var in first_input.header.var_IDs if var in first_input.selected_vars]
    second_vars = [var for var in second_input.header.var_IDs if var in second_input.selected_vars]
    common_vars = []
    for var in first_vars:
        if var in second_vars:
            common_vars.append(var)
    if not common_vars:
        return False, fail_message('the two input files do not share common variables', 'Write Serafin',
                                   first_input.job_id, second_input.job_id)

    # common frames
    first_frames = [first_input.start_time + first_input.time_second[i]
                    for i in first_input.selected_time_indices]
    second_frames = [second_input.start_time + second_input.time_second[i]
                     for i in second_input.selected_time_indices]
    common_frames = []
    for first_index, first_frame in zip(first_input.selected_time_indices, first_frames):
        for second_index, second_frame in zip(second_input.selected_time_indices, second_frames):
            if first_frame == second_frame:
                common_frames.append((first_index, second_index))
    if not common_frames:
        return False, fail_message('the two input files do not share common frames', 'Write Serafin',
                                   first_input.job_id, second_input.job_id)

    # construct output header
    output_header = first_input.header.copy()
    output_header.nb_var = len(common_vars)
    output_header.var_IDs, output_header.var_names, output_header.var_units = [], [], []
    for var in common_vars:
        name, unit = first_input.selected_vars_names[var]
        output_header.var_IDs.append(var)
        output_header.var_names.append(name)
        output_header.var_units.append(unit)
    if first_input.to_single:
        output_header.to_single_precision()

    # map points of A onto mesh B
    mesh = MeshInterpolator(second_input.header, False)

    if second_input.has_index:
        mesh.index = second_input.index
        mesh.triangles = second_input.triangles
    else:
        construct_mesh(mesh)
        second_input.has_index = True
        second_input.index = mesh.index
        second_input.triangles = mesh.triangles

    is_inside, point_interpolators = mesh.get_point_interpolators(list(zip(first_input.header.x,
                                                                           first_input.header.y)))
    # run the calculator
    with Serafin.Read(first_input.filename, first_input.language) as first_in:
        first_in.header = first_input.header
        first_in.time = first_input.time

        with Serafin.Read(second_input.filename, second_input.language) as second_in:
            second_in.header = second_input.header
            second_in.time = second_input.time

            calculator = operations.ProjectMeshCalculator(first_in, second_in, common_vars, is_inside,
                                                          point_interpolators, common_frames, operation_type)

            with Serafin.Write(filename, first_input.language, True) as out_stream:
                out_stream.write_header(output_header)

                calculator.run(out_stream, output_header)

    message = success_message('Write Serafin', first_input.job_id,
                              'The mesh A has {} / {} nodes inside the mesh B'.format(sum(is_inside),
                                                                                      first_input.header.nb_nodes),
                              second_input.job_id)
    return True, message


def construct_mesh(mesh):
    for i, j, k in mesh.ikle:
        t = Polygon([mesh.points[i], mesh.points[j], mesh.points[k]])
        mesh.triangles[i, j, k] = t
        mesh.index.insert(i, t.bounds, obj=(i, j, k))


def compute_volume(node_id, fid, data, aux_data, options, csv_separator):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Compute Volume',
                                                       data.job_id)
    first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite = options

    # process volume options
    if first_var not in data.selected_vars or first_var not in data.header.var_IDs:
        return False, node_id, fid, None, fail_message('variable not available', 'Compute Volume', data.job_id)
    if second_var is not None and second_var != '0':
        if second_var not in data.selected_vars or second_var not in data.header.var_IDs:
            return False, node_id, fid, None, fail_message('variable not available', 'Compute Volume', data.job_id)

    polygons = aux_data.lines
    polygon_names = ['Polygon %d' % (i+1) for i in range(len(polygons))]
    if sup_volume:
        volume_type = VolumeCalculator.POSITIVE
    else:
        volume_type = VolumeCalculator.NET

    # process output options
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
            return True, node_id, fid, csv_data, success_message('Compute Volume', data.job_id, 'reload existing file')

    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Compute Volume', data.job_id)

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

        result = calculator.run()
        for row in result:
            csv_data.add_row(row)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, success_message('Compute Volume', data.job_id)


def compute_flux(node_id, fid, data, aux_data, options, csv_separator):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Compute Flux',
                                                       data.job_id)
    flux_options, suffix, in_source_folder, dir_path, double_name, overwrite = options

    # process flux options
    var_IDs = list(flux_options.split(':')[1].split('(')[1][:-1].split(', '))
    if not all(u in data.selected_vars and u in data.header.var_IDs for u in var_IDs):
        return False, node_id, fid, None, fail_message('variable not available', 'Compute Flux', data.job_id)

    sections = aux_data.lines
    section_names = ['Section %d' % (i+1) for i in range(len(sections))]
    nb_vars = len(var_IDs)
    if nb_vars == 1:
        flux_type = FluxCalculator.LINE_INTEGRAL
    elif nb_vars == 2:
        if var_IDs[0] == 'M':
            flux_type = FluxCalculator.DOUBLE_LINE_INTEGRAL
        else:
            flux_type = FluxCalculator.LINE_FLUX
    elif nb_vars == 3:
        flux_type = FluxCalculator.AREA_FLUX
    else:
        flux_type = FluxCalculator.MASS_FLUX

    # process output options
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
            return True, node_id, fid, csv_data, success_message('Compute Flux', data.job_id, 'reload existing file')
    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Compute Flux', data.job_id)

    # prepare the mesh
    mesh = TriangularVectorField(data.header, False)

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

        calculator = FluxCalculator(flux_type, var_IDs,
                                    resin, section_names, sections, 1)
        calculator.time_indices = data.selected_time_indices
        calculator.mesh = mesh
        calculator.construct_intersections()

        csv_data = CSVData(data.filename, ['time'] + section_names)
        result = calculator.run()
        for row in result:
            csv_data.add_row(row)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, success_message('Compute Flux', data.job_id)


def interpolate_points(node_id, fid, data, aux_data, options, csv_separator):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Interpolate on Points',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Interpolate on Points', data.job_id)
    selected_vars = [var for var in data.header.var_IDs if var in data.selected_vars]
    if not selected_vars:
        return False, node_id, fid, None, fail_message('no available variable', 'Interpolate on Points', data.job_id)

    # process options
    suffix, in_source_folder, dir_path, double_name, overwrite = options

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
            return True, node_id, fid, csv_data, success_message('Interpolate on Points', data.job_id,
                                                                 'reload existing file')
    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Interpolate on Points', data.job_id)

    # prepare the mesh
    mesh = MeshInterpolator(data.header, False)

    if data.has_index:
        mesh.index = data.index
        mesh.triangles = data.triangles
    else:
        construct_mesh(mesh)
        data.has_index = True
        data.index = mesh.index
        data.triangles = mesh.triangles

    # process the points
    points = aux_data.points
    is_inside, point_interpolators = mesh.get_point_interpolators(points)
    point_interpolators = [p for i, p in enumerate(point_interpolators) if is_inside[i]]
    nb_inside = sum(map(int, is_inside))
    if nb_inside == 0:
        return False, node_id, fid, None, fail_message('no point inside the mesh', 'Interpolate on Points', data.job_id)

    # do calculation
    header = ['time']
    for x, y in points:
        for var in selected_vars:
            header.append('%s (%.4f, %.4f)' % (var, x, y))
    csv_data = CSVData(data.filename, header)

    nb_selected_vars = len(selected_vars)

    with Serafin.Read(data.filename, data.language) as input_stream:
        input_stream.header = data.header
        input_stream.time = data.time

        for index, index_time in enumerate(data.selected_time_indices):
            row = [str(data.time[index_time])]

            var_values = []
            for var in selected_vars:
                var_values.append(input_stream.read_var_in_frame(index, var))

            for (i, j, k), interpolator in point_interpolators:
                for index_var in range(nb_selected_vars):
                    row.append('%.6f' % interpolator.dot(var_values[index_var][[i, j, k]]))
            csv_data.add_row(row)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, \
                 success_message('Interpolate on Points', data.job_id, 
                                 '%s point%s inside the mesh' % (nb_inside, 's are' if nb_inside > 1 else ' is'))


def interpolate_lines(node_id, fid, data, aux_data, options, csv_separator):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Interpolate along Lines',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Interpolate along Lines', data.job_id)
    selected_vars = [var for var in data.header.var_IDs if var in data.selected_vars]
    if not selected_vars:
        return False, node_id, fid, None, fail_message('no available variable', 'Interpolate along Lines', data.job_id)

    # process options
    suffix, in_source_folder, dir_path, double_name, overwrite = options

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
            return True, node_id, fid, csv_data, success_message('Interpolate along Lines', data.job_id,
                                                                 'reload existing file')
    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Interpolate along Lines', data.job_id)

    # prepare the mesh
    mesh = MeshInterpolator(data.header, False)

    if data.has_index:
        mesh.index = data.index
        mesh.triangles = data.triangles
    else:
        construct_mesh(mesh)
        data.has_index = True
        data.index = mesh.index
        data.triangles = mesh.triangles

    # process the line
    lines = aux_data.lines
    nb_nonempty = 0
    indices_nonempty = []
    line_interpolators = []

    for i, line in enumerate(lines):
        line_interpolator, distance, _, _ = mesh.get_line_interpolators(line)
        if line_interpolator:
            nb_nonempty += 1
            indices_nonempty.append(i)

        line_interpolators.append((line_interpolator, distance))

    if nb_nonempty == 0:
        return False, node_id, fid, None, fail_message('no polyline intersects the mesh continuously', 
                                                       'Interpolate along Lines', data.job_id)

    header = ['line', 'time', 'x', 'y', 'distance'] + selected_vars
    csv_data = CSVData(data.filename, header)

    with Serafin.Read(data.filename, data.language) as input_stream:
        input_stream.header = data.header
        input_stream.time = data.time

        for u, id_line in enumerate(indices_nonempty):
            line_interpolator, distances = line_interpolators[id_line]

            for v, time_index in enumerate(data.selected_time_indices):
                time_value = data.time[time_index]
                var_values = []
                for var in selected_vars:
                    var_values.append(input_stream.read_var_in_frame(time_index, var))

                for (x, y, (i, j, k), interpolator), distance in zip(line_interpolator, distances):
                    row = [str(id_line+1), str(time_value), '%.6f' % x, '%.6f' % y, '%.6f' % distance]
                    for i_var, var in enumerate(selected_vars):
                        values = var_values[i_var]
                        row.append('%.6f' % interpolator.dot(values[[i, j, k]]))
                    csv_data.add_row(row)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, \
                 success_message('Interpolate along Lines', data.job_id, 
                                 '%s line%s the mesh continuously' % (nb_nonempty, 's intersect' if nb_nonempty > 1 else ' intersects'))


def project_lines(node_id, fid, data, aux_data, options, csv_separator):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Project Lines',
                                                       data.job_id)
    if len(data.selected_time_indices) != 1:
        return False, node_id, fid, None, fail_message('the file has more than one time frame',
                                                       'Project Lines', data.job_id)
    time_index = data.selected_time_indices[0]
    selected_vars = [var for var in data.header.var_IDs if var in data.selected_vars]
    if not selected_vars:
        return False, node_id, fid, None, fail_message('no available variable', 'Project Lines', data.job_id)

    # process options
    suffix, in_source_folder, dir_path, double_name, overwrite, reference_index = options
    lines = aux_data.lines
    if reference_index >= len(lines):
        return False, node_id, fid, None, fail_message('reference line not found (wrong polyline file?)',
                                                       'Project Lines', data.job_id)

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
            return True, node_id, fid, csv_data, success_message('Project Lines', data.job_id, 'reload existing file')
    try:
        with open(filename, 'w') as f:
            pass
    except PermissionError:
        return False, node_id, fid, None, fail_message('access denied', 'Project Lines', data.job_id)

    # prepare the mesh
    mesh = MeshInterpolator(data.header, False)

    if data.has_index:
        mesh.index = data.index
        mesh.triangles = data.triangles
    else:
        construct_mesh(mesh)
        data.has_index = True
        data.index = mesh.index
        data.triangles = mesh.triangles

    # process the line
    nb_nonempty = 0
    indices_nonempty = []
    line_interpolators = []

    for i, line in enumerate(lines):
        line_interpolator, distance, _, _ = mesh.get_line_interpolators(line)
        if line_interpolator:
            nb_nonempty += 1
            indices_nonempty.append(i)
        line_interpolators.append((line_interpolator, distance))

    if nb_nonempty == 0:
        return False, node_id, fid, None, fail_message('no polyline intersects the mesh continuously',
                                                       'Project Lines', data.job_id)
    elif reference_index not in indices_nonempty:
        return False, node_id, fid, None, fail_message('the reference line does not intersect the mesh continuously ',
                                                       'Project Lines', data.job_id)

    # do calculation
    reference = lines[reference_index]
    max_distance = reference.length()

    header = ['line', 'x', 'y', 'distance'] + selected_vars
    csv_data = CSVData(data.filename, header)

    with Serafin.Read(data.filename, data.language) as input_stream:
        input_stream.header = data.header
        input_stream.time = data.time

        var_values = []
        for var in selected_vars:
            var_values.append(input_stream.read_var_in_frame(time_index, var))

        for u, id_line in enumerate(indices_nonempty):
            line_interpolator, _ = line_interpolators[id_line]
            distances = []
            for x, y, _, __ in line_interpolator:
                distances.append(reference.project(x, y))

            for (x, y, (i, j, k), interpolator), distance in zip(line_interpolator, distances):
                if distance <= 0 or distance >= max_distance:
                    continue
                row = [str(id_line+1), '%.6f' % x, '%.6f' % y, '%.6f' % distance]
                for i_var, var in enumerate(selected_vars):
                    values = var_values[i_var]
                    row.append('%.6f' % interpolator.dot(values[[i, j, k]]))

                csv_data.add_row(row)

    csv_data.write(filename, csv_separator)
    return True, node_id, fid, csv_data, \
           success_message('Project Lines', data.job_id, '{} line{} the mesh continuously'.format(nb_nonempty,
                                                         's intersect' if nb_nonempty > 1 else ' intersects'))


def project_mesh(node_id, fid, data, second_data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Project B on A',
                                                       data.job_id)
    if not second_data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Project B on A',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Project B on A',
                                                       data.job_id, second_job_id=second_data.job_id)
    new_data = data.copy()
    new_data.operator = operations.PROJECT
    new_data.metadata = {'operand': second_data.copy()}
    return True, node_id, fid, new_data, success_message('Project B on A', data.job_id,
                                                         second_job_id=second_data.job_id)


def minus(node_id, fid, data, second_data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'A Minus B',
                                                       data.job_id)
    if not second_data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'A Minus B',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'A Minus B',
                                                       data.job_id, second_job_id=second_data.job_id)
    new_data = data.copy()
    new_data.operator = operations.DIFF
    new_data.metadata = {'operand': second_data.copy()}
    return True, node_id, fid, new_data, success_message('A Minus B', data.job_id, second_job_id=second_data.job_id)


def reverse_minus(node_id, fid, data, second_data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'B Minus A',
                                                       data.job_id)
    if not second_data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'B Minus A',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'B Minus A',
                                                       data.job_id, second_job_id=second_data.job_id)
    new_data = data.copy()
    new_data.operator = operations.REV_DIFF
    new_data.metadata = {'operand': second_data.copy()}
    return True, node_id, fid, new_data, success_message('B Minus A', data.job_id, second_job_id=second_data.job_id)


def max_between(node_id, fid, data, second_data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Max(A,B)',
                                                       data.job_id)
    if not second_data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Max(A,B)',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Max(A,B)',
                                                       data.job_id, second_job_id=second_data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MAX_BETWEEN
    new_data.metadata = {'operand': second_data.copy()}
    return True, node_id, fid, new_data, success_message('Max(A,B)', data.job_id, second_job_id=second_data.job_id)


def min_between(node_id, fid, data, second_data, options):
    if not data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Min(A,B)',
                                                       data.job_id)
    if not second_data.header.is_2d:
        return False, node_id, fid, None, fail_message('the input file is not 2d', 'Min(A,B)',
                                                       data.job_id)
    if data.operator is not None:
        return False, node_id, fid, None, fail_message('duplicated operator', 'Min(A,B)',
                                                       data.job_id, second_job_id=second_data.job_id)
    new_data = data.copy()
    new_data.operator = operations.MIN_BETWEEN
    new_data.metadata = {'operand': second_data.copy()}
    return True, node_id, fid, new_data, success_message('Min(A,B)', data.job_id, second_job_id=second_data.job_id)


FUNCTIONS = {'Select Variables': select_variables, 'Add Rouse': add_rouse, 'Select Time': select_time,
             'Select Single Frame': select_single_frame,
             'Select First Frame': select_first_frame, 'Select Last Frame': select_last_frame,
             'Max': compute_max, 'Min': compute_min, 'Mean': compute_mean,
             'Convert to Single Precision': convert_to_single, 'Compute Arrival Duration': arrival_duration,
             'Load 2D Polygons': read_polygons, 'Load 2D Open Polylines': read_polylines, 'Load 2D Points': read_points,
             'Write Serafin': write_slf, 'Compute Volume': compute_volume, 'Compute Flux': compute_flux,
             'Interpolate on Points': interpolate_points, 'Interpolate along Lines': interpolate_lines,
             'Project Lines': project_lines, 'Project B on A': project_mesh, 'A Minus B': minus,
             'B Minus A': reverse_minus, 'Max(A,B)': max_between,
             'Min(A,B)': min_between, 'Load Serafin 3D': read_slf_3d}


