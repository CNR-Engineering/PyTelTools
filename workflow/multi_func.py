import os
import numpy as np
from datetime import datetime
from multiprocessing import Process, Queue, cpu_count
from workflow.datatypes import SerafinData
import slf.misc as operations
from slf import Serafin


class Workers:
    def __init__(self):
        self.nb_processes = cpu_count()
        self.stopped = False
        self.task_queue = Queue()
        self.done_queue = Queue()

        self.processes = []
        for i in range(self.nb_processes):
            self.processes.append(Process(target=worker, args=(self.task_queue, self.done_queue)))

    def start(self, initial_tasks):
        for task in initial_tasks:
            self.task_queue.put(task)
        for p in self.processes:
            p.start()

    def stop(self):
        for i in range(self.nb_processes):
            self.task_queue.put('STOP')
        self.stopped = True


def worker(input, output):
    for func, args in iter(input.get, 'STOP'):
        result = func(*args)
        output.put(result)


def success_message(node_name, job_id):
    return '== %s - SUCCESS == %s (%s).' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), node_name, job_id)


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
            return True, node_id, fid, data, success_message('Write Serafin', data.job_id)

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




FUNCTIONS = {'Max': compute_max, 'Min': compute_min, 'Write Serafin': write_slf}


