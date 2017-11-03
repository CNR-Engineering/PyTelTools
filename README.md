# PyTelTools
<img style="float: right" src="https://github.com/CNR-Engineering/PyTelTools_media/blob/master/icons/PyTelTools_with_text.png" width="256px" />

* [Documentations](#documentations)
* [Installation and requirements](#installation-and-requirements)
* [Usage](#usage)
* [Configure](#configure)


## Documentations
* [User documentation](https://github.com/CNR-Engineering/PyTelTools/wiki)
* [Developer documentation](https://cnr-engineering.github.io/PyTelTools) ([repository with static files](https://github.com/CNR-Engineering/CNR-Engineering.github.io))


## Installation and requirements
PyTelTools relies on Python3 and requires packages which are listed in [requirements.txt](https://github.com/CNR-Engineering/PyTelTools/blob/master/requirements.txt).

I can be installed as a Python module (A) or an external program (B).
The recommended installation is within Python (A) as it becomes fully integrated with Python and more easier to install, upgrade and use.

### A) Installation as Python module
If you want to use a [virtual environnement](https://virtualenv.pypa.io/en/stable/) do the following:
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
```
This step to create and use virtualenv is optional and can also be done trough `make venv`.

PyTelTools can be installed directly from its repository with **pip**:
```bash
# user install
pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=pyteltools --user
# default install (eventually in a virtualenv or needs to be root)
pip install -e git://github.com/CNR-Engineering/PyTelTools.git#egg=pyteltools
```

#### Upgrade
To upgrade PyTelTools, simply use **pip**:
```bash
$ pip install PyTelTools --upgrade
```

### B) PyTelTools as an external program

#### B.1) Get the source code
Clone source code repository in a folder `PyTelTools`.
```bash
$ git clone https://github.com/CNR-Engineering/PyTelTools.git
```

If you do not have a `git` client, simply unzip the [source code repository](https://github.com/CNR-Engineering/PyTelTools/archive/master.zip).
For the next steps, the source code is expected to be in a folder named `PyTelTools` (containing this `README.md` file).

#### B.2) Install dependencies
If you want to use a [virtual environnement](https://virtualenv.pypa.io/en/stable/) do the following:
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
```
This step to create and use virtualenv is optional and can also be done trough `make venv`.

Packages installation can be done directly with **pip**:
```bash
$ pip install -r requirements.txt
```

## Usage

Depending on the followed installation procedure, see the correspond paragraph.

### A) Python module

#### A.1) Inside a Python interpreter
If PyTelTools is installed (the module is named `pyteltools`), it can be imported with:
```bash
$ python
>>> import pyteltools
>>>
```

Then all the methods and classes are accessible (such as `pyteltools.slf.Serafin`).

It can be usefull to define your own script adapted to your needs and still relying on PyTelTools core.

#### A.2) Call scripts

```bash
# Classic or Workflow interface (GUI)
$ pyteltools_gui.py
# Command line script (CLI) can be called directly from any directory
$ slf_base.py -h
```

Beware, that the Python executable is the one you configured (a Python3 which meets the requirements presented above).
Otherwise you could try to specify complete path to the Python executable and the script.

### B) PyTelTools as an external program

### B.1) Configure PYTHONPATH
Firstly, add the `PyTelTools` folder (which contains this `README.md` file) repository into the `PYTHONPATH`
environment variable of your operating system.

For Windows, you can find some help on the [official python documentation](https://docs.python.org/3.7/using/windows.html#excursus-setting-environment-variables).

On Linux, you easily do this through a command line like (or add directly this line in your `~/.bashrc`):
```bash
$ export PYTHONPATH=$PYTHONPATH:/home/opentelemac/PyTelTools
```

### Open interface
From the `PyTelTools` folder (containing this `README.md` file), simply run:
```bash
$ python cli/pyteltools_gui.py
# See help message to open a specific interface (classic or workflow)
$ python cli/pyteltools_gui.py -h
```

### Use command line for workflow
**Load** a workflow project file in the **GUI** (in mono tab):
```bash
$ python pyteltools/workflow/workflow_gui.py -i path_to_workflow_project_file.txt
```

**Load** and **run** a workflow project from the **command line**:
```bash
$ python pyteltools/workflow/mono_gui.py -i path_to_workflow_project_file.txt
$ python pyteltools/workflow/multi_gui.py -i path_to_workflow_project_file.txt
```

The argument `-h` provides a **help** message for the corresponding script and specify its **usage**.
Output **verbosity** can be increased (debug mode) with `-v` argument.

## Configure
PyTelTools comes with a set of default parameters which determines its behavior and some assumptions and options.

To configure PyTelTools, modify directly and only the file `pyteltools/conf/settings.py`.
Every constants which are defined in `pyteltools/conf/settings_sample.py` can be overwritten through this mean.

For example to change default Serafin language (for variable detection)
and to change increase verbosity `pyteltools/conf/settings.py` would be:
```python
from .settings_sample import *

LANG = 'en'

import logging
LOGGING_LEVEL = logging.DEBUG
```
