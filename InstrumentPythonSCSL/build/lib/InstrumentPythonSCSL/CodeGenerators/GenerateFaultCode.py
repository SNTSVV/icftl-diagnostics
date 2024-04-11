"""
Module to hold a class that generates code for a function fault injection.
"""

from . import FaultFunctionGeneratorBase, InstrumentationLine

class Generator(FaultFunctionGeneratorBase):
    def generate_code_line_list(self) -> list[InstrumentationLine]:
        func="InstrumentPythonSCSL.sleep_function.delay()"
        instrument_code = f"""{self._indentation}{func}"""
        code_line_list = [InstrumentationLine(self._module_name, self._line_index , instrument_code, "measurement")]
        return code_line_list

    def generate_function_import(self) -> list[InstrumentationLine]:
        import_module = self.generate_import_module_code()
        project_module = 'InstrumentPythonSCSL'
        func=f"import {project_module}.{import_module}"
        instrument_code = f"""{self._indentation}{func}"""
        code_line_list = [InstrumentationLine(self._module_name, 0 , instrument_code, "measurement")]
        return code_line_list

