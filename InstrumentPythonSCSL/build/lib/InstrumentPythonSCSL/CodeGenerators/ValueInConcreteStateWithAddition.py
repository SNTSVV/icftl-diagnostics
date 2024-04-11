"""
Module to hold a class that generates instrumentation code for a specific type of measurement.
"""

from . import InstrumentationLine
from .ValueInConcreteState import Generator as g

class Generator(g):

    def generate_code_line_list(self) -> list[InstrumentationLine]:
        time = self.generate_time_measurement_code()
        line_number = self.generate_line_number_code()
        module_name = self.generate_module_name_code()
        spec_id = self.generate_spec_id_code()
        code = f"""{self._indentation}{self._instrument_function}({{"type": "measurement", {spec_id}, "atom_index": {self._atom_index}, "subatom_index": {self._subatom_index}, "value": {self._subatom.get_value_expression().get_program_variable()}, {time}, {line_number}, {module_name}}})"""
        code_line_list = [InstrumentationLine(self._module_name, self._line_index + 1, code, "measurement")]
        return code_line_list
