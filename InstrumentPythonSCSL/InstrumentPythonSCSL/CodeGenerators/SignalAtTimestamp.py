"""
Module to hold a class that generates instrumentation code for a specific type of measurement.
"""

from . import GeneratorBase, InstrumentationLine

class Generator(GeneratorBase):
    def generate_code_line_list(self) -> list[InstrumentationLine]:
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = self.generate_time_measurement_code()
        line_number = self.generate_line_number_code()
        module_name = self.generate_module_name_code()
        spec_id = self.generate_spec_id_code()
        # construct measurement code
        measurement_code = f"ts_{self._subatom_index} = {total_seconds_expression}"
        # construct the instrument code
        instrument_code = f"""{self._indentation}{measurement_code}; {self._instrument_function}({{"type": "measurement", {spec_id}, "atom_index": {self._atom_index}, "subatom_index": {self._subatom_index}, "value": ts_{self._subatom_index}, {time}, {line_number}, {module_name}}})"""
        code_line_list = [InstrumentationLine(self._module_name, self._line_index + 1, instrument_code, "measurement")]
        return code_line_list
