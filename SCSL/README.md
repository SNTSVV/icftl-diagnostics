# SCSL

Performs monitoring, trace checking, and Python code analysis for SCSL

## Installation

To install this package, run:

```
pip install --upgrade pip setuptools
pip install git+ssh://git@cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL.git
```

In order to draw graphs, `graphviz` needs to be installed on your computer. 
On macOS, it can be installed using Homebrew (`$ brew install graphviz`) or
using MacPorts (`$ sudo port install graphviz`). For instructions for other
platforms, see [here](https://www.graphviz.org/download/).

## Instrumentation

In order to generate a trace, a program first needs to be instrumented. For example, if that
program is written in Python, [InstrumentPythonSCSL](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/InstrumentPythonSCSL)
can be used to instrument it. Before instrumentation, one can specify whether the program
should be instrumented for online or offline verification. After instrumentation, the program
needs to be run to generate a trace.

## Monitoring
Monitoring normally occurs automatically when an instrumented program is executed, with one
exception: when the value of a signal changes, this needs to be recorded manually, as in the
example below:
```python
from SCSL.Monitoring import process_signal_event
# Call this whenever the value of signal x changes
process_signal_event('x', x)
```
While monitoring is normally started and ended automatically by an instrumented program, you
can also start it and end it multiple times during the execution of a program by running
`SCSL.Monitoring.start_monitoring` or `SCSL.Monitoring.end_monitoring`, respectively. Note
that, once monitoring is started and until it is ended, any further calls of `start_monitoring`
are ignored. `start_monitoring` requires passing a specification (in its compiled form as a 
Python object), which can be imported from the module `compiled_spec.py` This module is created
in the project path during instrumentation. See the example below:
```python
from SCSL.Monitoring import start_monitoring
from compiled_spec import specification
start_monitoring(specification, online=True)
```

## Checking traces
After a program has been instrumented and run and a trace has been generated, the 
`scsl-check-trace` command-line interface can be used to check the trace, as per the 
usage instructions below. The CLI can also be invoked using `python -m SCSL.TraceChecker`.

```
scsl-check-trace [-h] [--write-tree] [--down] trace_file [project_path]

Checks traces with respect to SCSL specifications.

positional arguments:
  trace_file    JSON trace file output by the instrumented program
  project_path  Path to the instrumented project (default: '.')

optional arguments:
  -h, --help    show this help message and exit
  --write-tree  Write the final monitoring tree to .gv and .pdf files.
  --down        Evaluate the tree from the root down rather than from the leaves up.
```