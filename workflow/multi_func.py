from slf import Serafin
from multiprocessing import Process, Queue, current_process


class Workers:
    def __init__(self):
        self.nb_processes = 4
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


def read_slf(filename, job_id):
    print('reading', filename, 'with', current_process().name)
    with Serafin.Read(filename, 'fr') as f:
        f.read_header()
        if f.header.is_2d:
            return False, job_id
        return True, job_id