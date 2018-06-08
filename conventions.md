Conventions
===========

## Coding conventions
* encoding: utf-8
* linux line breaking
* indent: 4 spaces
* comment language: English
* shebang: `#!/usr/bin/env python`

## pylint
![pylint Score](https://mperlet.github.io/pybadge/badges/8.50.svg)

Simply run pylint with: 
```
pylint pyteltools
```
The configuration file `.pylintrc` will be used.

## Module imports
Avoid any wildcard imports.

### Group and order imports
Three groups for line imports are separated by an empty line:
1. internal Python imports
2. imports from PyTelTools
3. relative imports (within a PyTelTools module)

Imports are sorted by alphabetic order.

Example:
```python
import sys
from time import time

from pyteltools.conf import settings
from pyteltools.slf import Serafin

from .Node import Box, Link, Port
from .util import logger
```

### Common abbreviations
Some common import renamings:
```python
import numpy as np
import pyteltools.slf.misc as operations
```

## Naming conventions
* variables, functions, methods: lowercase_with_underscores
* class: CapWords

PyQt element prefixes :
* `qcb` = QCheckBox
* `qds` = QDoubleSpinBox
* `qle` = QLineEdit
* `qpb` = QPushButton

### Common custom methods for PyQt5
* `_initWidgets()`: fix element sizes, tooltips, ...
* `_setLayout()`: add widgets, items and finally calls `setLayouts()`
* `_bindEvents()`: bind events with methods

## Logging
Use with following logging levels (with corresponding numeric value) :
* `CRITICAL` (40)
* `WARNING` (30)
* `INFO` (20)
* `DEBUG` (10)

## CLI exiting code
* 0 = successful termination
* 1 = different kind of errors/inconsistencies: in input/output, error during computation, ...
* 2 = error or inconsistencies with command-line arguments
* 3 = file error (parser, writer)

## Code documentation
Developer documentation is generated with doyxgen and provided on https://cnr-engineering.github.io/PyTelTools.

Doxygen will extract preformatted comments following [some conventions](https://www.stack.nl/~dimitri/doxygen/manual/docblocks.html#pythonblocks).
