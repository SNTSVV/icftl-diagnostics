import sys
sys.path.append("...")

from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *

specification = \
    forall(id=0,
           binding={},
           predicate=inTimeInterval([0, 1])
    ).check(lambda binding: (
        disjunction(
            binding,
            signal("s").at(binding[0]).equals(60),
            binding[0].next(calls("decrease_signal").during("generator.controller")).duration() < 1
        )
    ))