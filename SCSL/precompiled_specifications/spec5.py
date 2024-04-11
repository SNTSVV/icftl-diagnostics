import sys
sys.path.append("...")

from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *

specification = \
    forall(id=0,
           binding={},
           predicate=calls("decrease_signal").during("generator.controller")
    ).check(lambda binding: (

            signal("s").at(time(binding[0]) + 0.1) < 100

    ))