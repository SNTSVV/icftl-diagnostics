import sys
sys.path.append("...")

from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *

specification = \
    forall(id=0,
           binding={},
           predicate=calls("decrease_signal").during("generator.controller")
    ).check(lambda binding: (
        exists(id=1,
               binding=binding,
               predicate=inTimeInterval([time(binding[0]), time(binding[0]) + 5])
               ).check(lambda binding: (
                    signal("s").at(binding[1]).equals(0)
               )
               )
        )
    )