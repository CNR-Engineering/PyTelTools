# TelTools
Telemac toolbox

* [User documentation](https://github.com/CNR-Engineering/TelTools/wiki)
* [Developper documentation](https://cnr-engineering.github.io/TelTools) ([repository with static files](https://github.com/CNR-Engineering/CNR-Engineering.github.io))

## Installation and requirements
It relies on Python3 and requires packages which are listed in [requirements.txt](https://github.com/CNR-Engineering/TelTools/blob/master/requirements.txt).

Packages installation can be done with pip:
```bash
$ pip install -r requirements.txt
```

### Virtualenv
The use of isolated Python environments is possible through virtualenv:
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt --upgrade
```

## Usage

### Open interface
```bash
$ python main_interface.py
$ python outil_carto.py
```

### Use command line for workflow
**Load** a workflow project file in the **GUI** (in mono tab):
```bash
$ python workflow/interface.py -i path_to_workflow_project_file.txt
```

**Load** and **run** a workflow project from the **command line**:
```bash
$ python workflow/mono_gui.py -i path_to_workflow_project_file.txt
$ python workflow/multi_gui.py -i path_to_workflow_project_file.txt
```

The argument `-h` provides a **help** message for the corresponding script and specify its **usage**.
Output **verbosity** can be increased (debug mode) with `-v` argument.

## Configure
Modify `conf/settings.py` to change default parameters.
