"""
Package init module for CodeGenerators.
"""

from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class InstrumentationLine:
    module_name: str
    line_number: int
    code: str
    priority_key: Literal["trigger", "end-timestamp", "measurement", "quantifier-measurement", "before-measurement",
                      "start-timestamp"]
    lines_to_delete: Optional[range] = None

class GeneratorBase:

    def __init__(self, indentation, spec_id, module_name, module_ast, line_index, line_contents, instrument_function,
                 atom_index, subatom_index, subatom):
        self._indentation = indentation
        self._spec_id = spec_id
        self._module_name = module_name
        self._module_ast = module_ast
        self._line_index = line_index
        self._line_contents = line_contents
        self._instrument_function = instrument_function
        self._atom_index = atom_index
        self._subatom_index = subatom_index
        self._subatom = subatom

    def generate_time_measurement_code(self):
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = f"\"time\": {total_seconds_expression} - SCSL.Monitoring.monitoring._start_time"
        return time

    def generate_line_number_code(self):
        line_number = self._line_index + 1
        code = f"\"line_number\": {line_number}"
        return code

    def generate_module_name_code(self):
        code = f"\"module_name\": \"{self._module_name}\""
        return code

    def generate_spec_id_code(self):
        code = f"\"spec_id\": {self._spec_id}"
        return code

class FunctionGeneratorBase:

    def __init__(self, indentation, spec_id, module_name, module_ast, line_index, line_contents, instrument_function,
                 element_index, function_name, atom_index):
        self._indentation = indentation
        self._spec_id = spec_id
        self._module_name = module_name
        self._module_ast = module_ast
        self._line_contents = line_contents
        self._instrument_function = instrument_function
        self._element_index = element_index
        self._line_index = line_index
        self._function_name = function_name
        self._atom_index = atom_index

    def generate_time_measurement_code(self):
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = f"\"time\": {total_seconds_expression} - SCSL.Monitoring.monitoring._start_time"
        return time

    def generate_line_number_code(self):
        line_number = self._line_index
        code = f"\"line_number\": {line_number}"
        return code

    def generate_module_name_code(self):
        code = f"\"module_name\": \"{self._module_name}\""
        return code

    def generate_spec_id_code(self):
        code = f"\"spec_id\": {self._spec_id}"
        return code

    def generate_function_name(self):
        code = f"\"function_name\": \"{self._function_name}\""
        return code

class FaultFunctionGeneratorBase:

    def __init__(self, indentation, spec_id, module_name, module_ast,import_module, line_index, line_contents, instrument_function
                ):
        self._indentation = indentation
        self._spec_id = spec_id
        self._module_name = module_name
        self._module_ast = module_ast
        self._import_module = import_module
        self._line_contents = line_contents
        self._instrument_function = instrument_function
        self._line_index = line_index

    def generate_time_measurement_code(self):
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = f"\"time\": {total_seconds_expression} - SCSL.Monitoring.monitoring._start_time"
        return time

    def generate_line_number_code(self):
        line_number = self._line_index + 1
        code = f"\"line_number\": {line_number}"
        return code

    def generate_module_name_code(self):
        code = f"\"module_name\": \"{self._module_name}\""
        return code

    def generate_import_module_code(self):
        code = f"{self._import_module}"
        return code

    def generate_spec_id_code(self):
        code = f"\"spec_id\": {self._spec_id}"
        return code