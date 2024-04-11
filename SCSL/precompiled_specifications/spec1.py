import sys
sys.path.append("...")

from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *

specification = forall(id=0, binding={}, predicate=inTimeInterval([0, 200]))\
    .check(lambda binding: signal("s").at(binding[0]) < 100)