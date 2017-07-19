Conventions
===========

## Coding conventions
* encoding: utf-8
* linux line breaking
* indent: 4 spaces
* comment language: English

## Module imports
No import with * except for PyQt5 :
```python
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
```

### Common abbreviations
```python
import numpy as np
import pandas as pd
import shapely.affinity as aff
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
Developper documentation is generated with doyxgen and provided on https://cnr-engineering.github.io/TelTools.

Doxygen will extract preformatted comments following [some conventions](https://www.stack.nl/~dimitri/doxygen/manual/docblocks.html#pythonblocks).
