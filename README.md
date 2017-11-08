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
PyTelTools relies on **Python3** and requires packages which are listed in [requirements.txt](https://github.com/CNR-Engineering/PyTelTools/blob/master/requirements.txt).

> :warning: If you have multiple versions of Python installed, beware of using the right **python** or **pip** executable (or consider using a  [virtual environnement](https://virtualenv.pypa.io/en/stable/) if you are on Linux), which has to be a Python 3 version.

> :information_source: For **Windows** users who face problems with the installation of these packages (especially PyQt5, scipy or numpy), consider using a Python version with a full set of **pre-installed scientific packages**, such as [WinPython](http://winpython.github.io) or [Conda](https://conda.io). All the major packages will be already installed, therefore it should facilitate the installation.
> 
> It is even possible to download a WinPython portable installation for Python 3.6 (64 bits) with all the dependencies required by PyTelTools (and many more packages) already installed [here (~500 MB)](https://drive.google.com/file/d/1IihdjBCefjq8EoTOnY9WBjDwLK5-vLvc/view?usp=sharing).

PyTelTools can be installed as a Python module (A) or an external program (B).
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

> :information_source: If you do not have a `git` client (which might be the case if you are using Windows), you can try to install it with:
> ```python
> pip install https://github.com/CNR-Engineering/PyTelTools/zipball/master
> ```

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

> :information_source: If you do not have a `git` client, simply unzip the [source code repository](https://github.com/CNR-Engineering/PyTelTools/archive/master.zip).

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
PyTelTools comes with a set of **default parameters** which determine its behavior and some assumptions and options.

The recommended way to modify PyTelTools configuration is to write a **user configuration file** in **JSON** file format
and refer to it in an environment variable named `PYTELTOOLS_SETTINGS`.
The environment variable `PYTELTOOLS_SETTINGS` has to contain the **absolute path** to this file.
For example, it could something like:
`/home/user/pyteltools/cfg.json` or `C:\Users\MyAccount\Documents\config_pyteltools.json`.

The parameters defined in the user configuration file will be used instead of the default parameter.

For example to change default Serafin language (for variable detection) 
and to change increase verbosity (to debug mode), the JSON file should be:
```json
{
    "LANG": "en",
    "LOGGING_LEVEL": 10
}
```

Here is a second example of a JSON configuration file with a more complex configuration:
```json
{
    "DIGITS": 8,
    "NCSIZE": 6,
    "SCENE_SIZE": [2000, 1200],
    "SERAFIN_EXT": [".slf", ".srf", ".res"],
    "WRITE_XYZ_HEADER": false,
    "X_AXIS_LABEL": "X coordinate (m)",
    "Y_AXIS_LABEL": "Y coordinate (m)"
}
```

PyTelTools configuration relies on the Python package [simple-settings](https://pypi.python.org/pypi/simple-settings)
and all the parameters are defined and described in [pyteltools/conf/default_settings.py](https://github.com/CNR-Engineering/PyTelTools/blob/master/pyteltools/conf/default_settings.py).
