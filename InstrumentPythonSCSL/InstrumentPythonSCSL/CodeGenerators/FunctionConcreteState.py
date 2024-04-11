"""
Module to hold a class that generates instrumentation code for a specific function.
"""

from . import FunctionGeneratorBase, InstrumentationLine

class Generator(FunctionGeneratorBase):
    def generate_code_line_list(self) -> list[InstrumentationLine]:
        time = self.generate_time_measurement_code()
        line_number = self.generate_line_number_code()
        module_name = self.generate_module_name_code()
        spec_id = self.generate_spec_id_code()
        function_name = self.generate_function_name()
        # construct measurement code
        measurement_code = f"tf_{self._element_index} = scsl_monitoring_time.time()"
        # construct the instrument code
        instrument_code = f"""{self._indentation}{measurement_code}; {self._instrument_function}({{"type": "function", {spec_id}, "value": tf_{self._element_index}, "atom_index": {self._atom_index}, {time}, {line_number}, {module_name}, {function_name}}})"""
        code_line_list = [InstrumentationLine(self._module_name, self._line_index , instrument_code, "function")]
        return code_line_list
