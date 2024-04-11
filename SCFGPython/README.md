# SCFGPython

Builds SCFGs for Python source code

## Installation

To install this package, run:

```
pip install --upgrade pip setuptools
pip install git+ssh://git@cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCFGPython.git
```

In order to draw graphs, `graphviz` needs to be installed on your computer. 
On macOS, it can be installed using Homebrew (`$ brew install graphviz`) or
using MacPorts (`$ sudo port install graphviz`). For instructions for other
platforms, see [here](https://www.graphviz.org/download/).

## Usage

In order to generate a graph, use the command-line interface as follows:

```
generate-scfg [-h] MODULE_PATH:[CLASS.]*FUNCTION

Draws the symbolic-control flow graph (SCFG) of a given Python function

positional arguments:
  MODULE_PATH:[CLASS.]*FUNCTION
                        Qualified name of a Python function (e.g. "src/some_module.py:SomeClass.some_method")

optional arguments:
  -h, --help            show this help message and exit

The files <function_name>.dot and <functon_name>.dot.pdf will be created.
```
