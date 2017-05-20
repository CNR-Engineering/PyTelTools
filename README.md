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
The use of isolated Python environments are possible through virtualenv:
```bash
$ virtualenv venv --python=python3
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt --upgrade
```

## Usage
```bash
$ python main_interface.py
```
