# PyTelTools
<img style="float: right" src="https://github.com/CNR-Engineering/PyTelTools_media/blob/master/icons/PyTelTools_with_text.png" width="256px" />

## Documentations
* [User documentation](https://github.com/CNR-Engineering/PyTelTools/wiki)
* [Developer documentation](https://cnr-engineering.github.io/PyTelTools) ([repository with static files](https://github.com/CNR-Engineering/CNR-Engineering.github.io))

## Installation and requirements
PyTelTools relies on Python3 and requires packages which are listed in [requirements.txt](https://github.com/CNR-Engineering/PyTelTools/blob/master/requirements.txt).

I can be installed as an external program (A) or as a Python module (B).

### A) Download source files

#### A.1) Get source code
Clone source code in a folder `PyTelTools`.
```bash
$ git clone https://github.com/CNR-Engineering/PyTelTools.git
```

If you do not have a `git` client, simply unzip the [source code repository](https://github.com/CNR-Engineering/PyTelTools/archive/master.zip). For the next steps, the source code is expected to be in a folder named `PyTelTools`.

#### A.2) Install dependencies
Move to PyTelTools folder (containing this README.md file):
```bash
$ cd PyTelTools
```

If you want to use a [virtual environnement](https://virtualenv.pypa.io/en/stable/) do the following
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
```
This step to create and use virtualenv is optional and can also be done trough `make venv`.

Packages installation can be done directly with **pip**:
```bash
$ pip install -r requirements.txt
```

### B) Installation within Python
If you want to use a [virtual environnement](https://virtualenv.pypa.io/en/stable/) do the following
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
```
This step to create and use virtualenv is optional and can also be done trough `make venv`.

Packages installation can be done directly with **pip**:
```bash
# user install (eventually in a virtualenv)
pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=PyTelTools --user
# default install (needs to be root)
pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=PyTelTools
```

#### Check installation
Try to import PyTelTools module :
```python
import PyTelTools
```

Then you can use all the methods and classes (such as `PyTelTools.slf.Serafin`).

## Usage as an external program

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
