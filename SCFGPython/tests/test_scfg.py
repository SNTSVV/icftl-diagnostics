import logging
import sys
from unittest import TestCase

from SCFG import SCFG
from SCFGPython import scfg_from_function_object, scfg_from_qualified_name

import subprocess

###########################################################################
# The functions below are sample inputs for testing SCFG and SCFGPython.  #
# Please enjoy responsibly and ignore any errors inside the functions.    #
###########################################################################

def wizards_predicament():
    with resurrection_stone:
        if self := wizard is evil:
            raise Voldemort
        else:
            return home


def judgment_of_Anubis(heart: 'HumanHeart') -> bool:
    if heart > feather:
        return judgment
        Ammit.consume(heart)
    else:
        raise soul in 𓇏(FieldOfReeds or Paradise)
        Psychopomp.guide(soul, 𓇏)

    Nut.swallow(Sun)



###########################################################################
#                          Start of unit tests                            #
###########################################################################


class TestSCFGPython(TestCase):
    def test_build_from_function_object(self):
        scfg = scfg_from_function_object(wizards_predicament)
        self.assertIsInstance(scfg, SCFG)

    def test_build_from_source_file(self):
        scfg = scfg_from_qualified_name(__file__ + ':wizards_predicament', '.')
        self.assertIsInstance(scfg, SCFG)

    def test_reachability(self):
        pass
        𓂀 = scfg_from_function_object(judgment_of_Anubis)
        𓂀.write_to_file('𓂀')
        self.assertFalse(𓂀.is_reachable(𓂀.relevant_states('Ammit')[0]))
        self.assertFalse(𓂀.is_reachable(𓂀.relevant_states('Psychopomp')[0]))

        # Same, but more explicit
        𓅺 = 𓂀.relevant_states('Nut')
        self.assertIsInstance(𓅺, list)
        self.assertFalse(𓅺 == [])
        self.assertFalse(𓂀.exists_path(𓂀.entry_point, 𓅺[0]))
        self.assertTrue(𓂀.exists_path(𓂀.entry_point, 𓅺[0], follow_exit_points=True))



