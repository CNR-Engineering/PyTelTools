# PyTelTools
Python Telemac Tools

* [User documentation](https://github.com/CNR-Engineering/PyTelTools/wiki)
* [Developer documentation](https://cnr-engineering.github.io/PyTelTools) ([repository with static files](https://github.com/CNR-Engineering/CNR-Engineering.github.io))

## Installation and requirements
PyTelTools relies on Python3 and requires packages which are listed in [requirements.txt](https://github.com/CNR-Engineering/PyTelTools/blob/master/requirements.txt).

### Installation via pip
Packages installation can be done with **pip**:
```bash
# user install
$ pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=PyTelTools --user
# default install (needs to be root)
# pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=PyTelTools
```

### Installation in a virtual environnement
The use of isolated Python environments is possible through **virtualenv**:
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
(venv) $ pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=PyTelTools
```

## Usage

### Open interface
```bash
$ python PyTelTools/main_interface.py
$ python PyTelTools/outil_carto.py
```

### Use command line for workflow
**Load** a workflow project file in the **GUI** (in mono tab):
```bash
$ python PyTelTools/workflow/interface.py -i path_to_workflow_project_file.txt
```

**Load** and **run** a workflow project from the **command line**:
```bash
$ python PyTelTools/workflow/mono_gui.py -i path_to_workflow_project_file.txt
$ python PyTelTools/workflow/multi_gui.py -i path_to_workflow_project_file.txt
```

The argument `-h` provides a **help** message for the corresponding script and specify its **usage**.
Output **verbosity** can be increased (debug mode) with `-v` argument.

## Configure
Modify `PyTelTools/conf/settings.py` to change default parameters.

For example to change default Serafin language (for variable detection)
and to change increase verbosity write this in `PyTelTools/conf/settings.py`:
```python
from conf.settings_sample import *

LANG = 'en'

import logging
LOGGING_LEVEL = logging.DEBUG
```
