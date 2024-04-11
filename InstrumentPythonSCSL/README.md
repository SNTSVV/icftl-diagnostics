# InstrumentPythonSCSL

This package inserts Python instrumentation code with respect to an SCSL specification.

## Toolchain overview

The SCSL toolchain can be used to verify that a program conforms to an SCSL specification 
([see below](#the-specification-language)). The verification process consists of three steps:

1. **Instrumenting the program.** During this step, the instrumentation tool `instrument-python-scsl`
   analyses the source code of the program in order to determine which parts of it are relevant to 
   a specification. Instructions are then automatically inserted into the program. This process
   is described in the activity diagram below. You will find instructions on how to instrument a
   program [here](#usage).
   ![Instrumentation process](figures/activity-diagram.png)
2. **Monitoring.** When the instrumented program is executed, the instructions added during the
   previous step record events which are necessary to determine whether the specification is
   satisfied. More information on monitoring can be found 
   [here](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL#monitoring).
3. **Trace checking.** This step consists of analysing the events recorded during monitoring and
   issuing a verdict as to whether the assertions contained in the specification are satisfied.
   Instructions on trace checking can be found 
   [here](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL#checking-traces).

SCSL supports two types of monitoring: *online monitoring* and *offline monitoring*. In the case
of online monitoring, steps 2 and 3 take place concurrently and asynchronously, i.e. events are
processed on a separate thread while the program is running[^1]. In the case of offline monitoring,
the events are written to a file named `scsl-trace.json` when the program terminates. Instructions
on how to check the trace can be found
[here](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL#checking-traces).

[^1]: Note that currently, a verdict is only issued when the program ends, although this could
change in the future. However, it is also possible for the user to start and end monitoring
multiple times during a single execution of a program, in which case a verdict will be
issued each time monitoring is ended.

Steps 2 and 3 are shown in the activity diagram below. 
![Monitoring and trace checking](figures/activity-diagram-2.png)

The SCSL toolchain consists of four packages:

- [`SCFG`](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCFG) defines so-called *symbolic control-flow
  graphs* (SCFGs), which are required for determining the points of a program which need to be 
  instrumented;
- [`SCFGPython`](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCFGPython) generates SCFGs for Python programs;
- [`SCSL`](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL) is programming-language agnostic and consists
  of three subpackages:
  - `SCSL.Analysis`, which uses SCFGs to determine the points of a program which need to be 
    instrumented;
  - `SCSL.Monitoring` is invoked by instrumented programs. It records and processes events and
    performs online monitoring;
  - `SCSL.TraceChecking` performs offline monitoring;
- [`InstrumentPythonSCSL`](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/InstrumentPythonSCSL) instruments
  Python programs with respect to SCSL.

A dependency graph of these packages is shown below.
![Dependency graph](figures/dependency-graph.png)

## Installation

### Using `pip`

The recommended way of installing this package and, in fact, the entire toolchain, is using `pip`:

```
pip install --upgrade pip setuptools
pip install git+ssh://git@cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/InstrumentPythonSCSL.git
```

The commands above will also install the other packages listed above, including [`SCSL`](https://cosmos-devops.cloudlab.zhaw.ch/cosmos-devops/cosmos-tools/rv-for-gmv/SCSL),
which provides trace checking machinery. Note that access to the repository using an SSH key is required.

### Manually

Alternatively, the packages can also be installed manually and separately. 
This process is more cumbersome, but does not require an SSH key and allows 
[editable installs](https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs).
In order to do so, first upgrade `pip` and `setuptools` as  shown above. Then 
clone all the repositories listed above and for each, run the following:

```
pip install --no-dependencies /path/to/repository
```

Finally, because `pip` was run with the `no-dependencies` flag, install the projects' 
external dependencies as follows:

```
pip install graphviz antlr4-python3-runtime==4.11.1
```

### Post-installation (in both of the above cases)
In order to draw graphs, `graphviz` needs to be installed on your computer. 
On macOS, it can be installed using Homebrew (`$ brew install graphviz`) or
using MacPorts (`$ sudo port install graphviz`). For instructions for other
platforms, see [here](https://www.graphviz.org/download/).

## Usage

The `scsl-instrument-python` command-line interface can be used to instrument a project,
as per the usage instructions below. It can also be invoked using `scsl-instrument` or
`python -m InstrumentPythonSCSL`.

```
scsl-instrument-python [-h] [--online] specification_path [project_path]

Instruments Python projects with respect to SCSL specifications.

positional arguments:
  specification_path  Path to the specification with respect to which to instrument.
  project_path        Path to the project to instrument (default: '.')

optional arguments:
  -h, --help          show this help message and exit
  --online            Instrument for online monitoring
  --debug             Write some additional files useful for debugging and measurements
```

When instrumentation is performed, the instrumented files are backed up with the suffix
`_uninstrumented_original`. **The instrumented files themselves should not be modified,
as they will be overwritten the next time that instrumentation is performed.** In order
to restore the original uninstrumented files (and delete the backups), run 
`scsl-instrument-restore`:

```
scsl-instrument-restore [-h] [project_path]

Restores instrumented files from backup.

positional arguments:
  project_path  Path to the project to instrument (default: '.')

optional arguments:
  -h, --help    show this help message and exit
```

# The Specification Language

A program is instrumented with respect to a *specification*, which is a descriptions of how you expect 
your program to behave.

Specifications are written in our specification language. As an example, suppose you want to capture 
the following:

*In the file `database.py`, whenever the function `commit` is called by the procedure `query`, it 
should take less than 1 second.*

You can write this as follows:

```
for every c satisfying calls("commit").during("database.py:query") {
  duration c < 1
}
```

Below you'll find a reference for the language that you can use to write your own specifications.

## Capturing events

When writing a specification, your first step is to choose some events that you'll make assertions 
about.

To do this, you use `for every` or `there is`. `for every` lets you say that some assertion 
should hold *for every event* that you identify, whereas `there is` lets you say that some 
assertion need only hold *for one or more events* that you identify.

### For every

To use `for every`, you use the form
```
for every <variable> satisfying <predicate> {
    <some assertions>
}
```
Here, `<variable>` is the name that you'll use to identify the events that satisfy `<predicate>` at 
runtime.

`<predicate>` can be
* `calls("<function name>").during("<function name>")`
* `changes("<variable name>").during("<function name>")`

So, putting this together, you can write something like
```
for every q satisfying changes("x").during("func") {

}
```
which will mean that you want to make an assertion on the event `q`, every time that event represents 
a change of the variable `x` by the function `func`.

### There is

To use `there is`, you use the form
```
there is <variable> satisfying <predicate> {
    <some assertions>
}
```
Where everything is the same as for the `for every` case.

Again, putting this together, you can write something like
```
there is q satisfying changes("x").during("func") {
  value variable "x" in q < 1
}
```
to say that there must be at least one event representing a change of the variable `x` (during the 
function `func`) in which the variable `x` is less than 1.

### Ordering events

Let's imagine you've already written part of your specification to capture 
the changes of the program variable `x` during the function `func`. Now,
suppose you want to capture all the calls of the function `f` 
(still during the function `func`) that take place *after* the changes of `x`
you identified earlier.

For this, we have the `after` keyword, and you can use it like this:

```
for every q satisfying changes("x").during("func") {

    there is c satisfying calls("f").during("func") after (timestamp q) {
    
        <some assertions>
    
    }

}
```

## Assertions

So, you've captured some events using `for every` or `there is` 
(or a combination of the two). Your next step is to write assertions over
those events.

Depending on the events that you've captured, there are different
assertions that you can define.

### Assertions on function calls

You can currently make an assertion over the time taken by a function call.

So, if you've captured a function call using something similar to the 
following:

```
for every c satisfying calls("f").during("p") {
}
```

Then you can use the `duration <event>` pattern to write an assertion on the time
taken by the function call represented by `c`:

```
for every c satisfying calls("f").during("p") {
    duration c < 1
}
```

### Assertions on program variable values

Given an event that represents the change of a program variable value,
you can write assertions about the new value held by that variable.

You access the value held in a variable using the pattern 
`value variable "<variable>" in <event>`.

For example, if you want to say that, everytime the variable `x` is changed
in the procedure `p`, the new value should be less than 10, you can write

```
for every q satisfying changes("x").during("p") {
  value variable "x" in q < 10
}
```

### Assertions on the time between events

Suppose you have two statements in your program source code, and you 
want to assert that the time taken to reach one from the other at runtime
is less than 2 seconds.

For this, you can use the pattern `time to <event> from <event>`.

A key thing to remember about this pattern is that the events *must*
be program variable value changes. This rationale behind this is that these
events represent instantaneous points in time, so it makes sense
to measure the time taken to reach one from another.

For eaxmple, if you want to say that, whenever the variable `x` is changed
in the procedure `p`, the function `f` should finish being called (after that
variable change) within 3 seconds, you can write

```
for every q satisfying changes("x").during("p") {
  time to (
    after(
        next after q satisfying calls("f").during("p")
    )
  ) from q < 3
}
```

there are a couple of extra bits of syntax used here, such as the `after` and
`next after <event> satisfying <predicate>` patterns. 
These are described in *Navigating events*.

## Navigating events

Assertions on events can be enriched by using patterns that *navigate* the
events generated at runtime. For example, given an event that represents
the change of a variable value, you can find other events in the future that
do something different, such as changing another program variable,
or calling a function. Likewise, you can take a function call and find other
events in the future that change variable values or call other functions.

### Finding variable value changes

Suppose you already have an event (representing either a function call
or a variable value change) in the variable `q` in your specification.

#### Next events

From this variable, you can find the *next event in the future* of `q` using
the pattern `next after <event> satisfying <predicate>`.

For example, if you want to find the next change of the variable `x` 
(in the procedure `p`), after some event `q`, you can write

```
next after q satisfying changes("x").during("p")
```
This would give you an event that you could treat as a variable value change.
For example, you can write
```
value variable "x" in (next after q satisfying changes("x").during("p"))
```

#### Before and after

If you've already identified a function call, it can be useful to get
the events immediately before and after (say, to write assertions
about the inputs and outputs of a function).

To get the event immediately before a function call, 
you can use the `before <event>`. Similarly, to get the event immediately
after a function call, you can use the `after <event>` pattern.

Once you've used one of these patterns, you can treat the event
that you get as a variable value change. So, you can access the value
of a variable by writing
```
value variable "a" in (before c)
```
This would take the function call held in `c`, get the event immediately
before it, and then access the value of the variable `a` in that event.

### Finding function calls

Suppose you already have an event (representing either a function call
or a variable value change) in the variable `q` in your specification.

#### Next events

From this variable, you can find the *next event in the future* of `q` using
the pattern `next after <event> satisfying <predicate>`.

For example, if you want to find the next call of the function `f` (in
the procedure `p`), after some event `q`, you can write

```
next after q satisfying calls("f").during("p")
```

This would give you an event that you could treat as a function call.
For example, you can write
```
duration (next after q satisfying calls("f").during("p"))
```

## Combining Assertions

Assertions on events can be combined using Boolean connectives. This
allows you to write more complex assertions, over multiple events
at the same time.

The basic Boolean connectives are provided - *and*, *or*, and *not*. These
are accessible via the `and`, `or` and `not` keywords.

For example, if you want to write that the program variable `x` is never
given a value below 10, you can write

```
for every q satisfying changes("x").during("p") {
  not( value variable "x" in q < 10 )
}
```

or, if you wanted to say that, when the value of the variable `x` is assigned,
then the value of `x` should be less than 10, and the value of `y` should be
greater than 20, you could write

```
for every q satisfying changes("x").during("p") {
  value variable "x" in q < 10
  and
  value variable "y" in q > 20
}
```
