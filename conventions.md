Conventions
===========

## Coding conventions
* encoding: utf-8
* linux line breaking
* indent: 4 spaces
* comment language: English
* shebang: `#!/usr/bin/python3`

## Module imports
Avoid any import with * except for PyQt5:
```python
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
```

### Group and order imports
Two groups for line imports are separated by an empty line:
1. internal Python imports
2. imports from PyTelTools

Imports are sorted by alphabetic order.

Example:
```python
import sys
from time import time

from conf.settings import CSV_SEPARATOR, DIGITS, LANG, SCENE_SIZE
from workflow.Node import Box, Link, Port
from workflow.util import logger
```

### Common abbreviations
Some common import renamings:
```python
import numpy as np
import slf.misc as operations
```

## Naming conventions
* variables, functions, methods: lowercase_with_underscores
* class: CapWords

### Common custom methods for PyQt5
* `_initWidgets()`: fix element sizes, tooltips, ...
* `_setLayout()`: add widgets, items and finally calls `setLayouts()`
* `_bindEvents()`: bind events with methods

## Logging
Use with following logging levels (with corresponding numeric value) :
* CRITICAL (40)
* WARNING (30)
* INFO (20)
* DEBUG (10)

## Code documentation
Developper documentation is generated with doyxgen and provided on https://cnr-engineering.github.io/PyTelTools.

Doxygen will extract preformatted comments following [some conventions](https://www.stack.nl/~dimitri/doxygen/manual/docblocks.html#pythonblocks).
