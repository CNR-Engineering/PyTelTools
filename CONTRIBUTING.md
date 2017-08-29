# Contributing

> First off, thank you for considering contributing to the opensource project PyTelTools.
> It's people like you that make such great tools for Telemac post-processing tasks.

Requiring needs include: development, documentation, tests, ...


## Report a bug

Please [write an issue](https://github.com/CNR-Engineering/PyTelTools/issues/new) with: the error message (with traceback) and a minimal non-working example to reproduce it.


## Documentate a tool

Ask for write access (e.g. per email at: l _(dot)_ duron _(at)_ cnr _(dot)_ tm _(dot)_ fr).

Screenshots should be upload on https://github.com/CNR-Engineering/PyTelTools_media.

### Some notions
* DAG: directed acyclic graph
* DFS: depth first search


## Want to develop something?

### Implement your fix or feature

Please do a pull request if you're ready to make your changes!

Feel free to ask for help; everyone is a beginner at first.

### Add a new unitary tool

TODO

### Add a new tool in workflow

1. Add it to Mono tab
    * `nodes_*`: add a new class which derives from Node (e.g. `TwoInOneOutNode`) in the corresponding file (depending on its category)
    * `mono_gui`: add a new entry in dict `NODES`
2. Add it to Multi tab
    * `multi_nodes`: add a new class which derives from Nodederived (e.g. `MultiDoubleInputNode`) and define `load` method
    * `multi_gui`: add
    * `multi_func`: add a function

#### Datatypes for ports

Possible datatypes as input/output for workflow tools are currently:
* Serafin
  * `slf`
  * `slf reference`
  * `slf 3d`
  * `slf geom`
  * `slf out`
* CSV
  * `point csv`
  * `volume csv`
  * `flux csv`
* Geopositional data
  * `point 2d`
  * `polyline 2d`
  * `polygon 2d`
