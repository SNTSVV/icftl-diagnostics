"""
Module for getting data from the database, and then formatting it read to be printed to stdout.
"""
import importlib
from datetime import datetime
import json

from .Database.database import Connection
from ..Specifications.simplified_lang_translator import (TranslatorFromText,
                                                         _eval_specification_from_python_code)


class FormatSpecDuration:

    def __init__(self, dsl_type, dsl_text, measurements):
        # import the relevant dsl type class from the parser
        module = importlib.import_module("SCSL.Specifications.simplified_lang_translator")
        dsl_type_class = getattr(module, dsl_type)
        # store the arguments
        self._dsl_parser = dsl_type_class(dsl_text)
        self._measurements = measurements

    def format_output(self, indent_level):
        # initialise default indent
        default_indent = "  "*indent_level
        # initialise output string
        output_string = "\n"
        # iterate through measurements
        for measurement in self._measurements:
            # get expression from dsl text
            expression_from_spec = self._dsl_parser.get_expression(0, 0)
            # add to output string
            output_string += f"{default_indent}{expression_from_spec} -> " \
                             f"{measurement['measurement']} " \
                             f"({measurement['module_name']} @ line {measurement['line_number']})\n"
        return output_string

class FormatSpecTimeBetween:

    def __init__(self, dsl_type, dsl_text, measurements):
        # import the relevant dsl type class from the parser
        module = importlib.import_module("SCSL.Specifications.simplified_lang_translator")
        dsl_type_class = getattr(module, dsl_type)
        # store the arguments
        self._dsl_parser = dsl_type_class(dsl_text)
        self._measurements = measurements

    def format_output(self, indent_level):
        # initialise default indent
        default_indent = "  "*indent_level
        # initialise output string
        output_string = ""
        # measurements come in pairs, so iterate until the penultimate with a step of 2
        for i in range(0, len(self._measurements)-1, 2):
            # get the "left" and "right" measurements
            lhs_measurement = self._measurements[i]
            rhs_measurement = self._measurements[i+1]
            # get time difference
            start_timestamp = float(lhs_measurement["measurement"])
            end_timestamp = float(rhs_measurement["measurement"])
            difference = end_timestamp - start_timestamp
            # get dsl string for lhs and rhs
            lhs_expression_from_spec = self._dsl_parser.get_expression(0, 0)
            rhs_expression_from_spec = self._dsl_parser.get_expression(0, 1)
            output_string += f"\n{default_indent}time between -> {difference}\n"
            # add information from "left" measurement
            output_string += f"{default_indent}  {lhs_expression_from_spec} -> " \
                             f"{lhs_measurement['measurement']} " \
                             f"({lhs_measurement['module_name']} @ line {lhs_measurement['line_number']})\n"
            # add information from "right" measurement
            output_string += f"{default_indent}  {rhs_expression_from_spec} -> " \
                             f"{rhs_measurement['measurement']} " \
                             f"({rhs_measurement['module_name']} @ line {rhs_measurement['line_number']})\n"

        return output_string

class FormatSpecWhenever:

    def __init__(self, dsl_type, dsl_text, measurements):
        # import the relevant dsl type class from the parser
        module = importlib.import_module("SCSL.Specifications.simplified_lang_translator")
        dsl_type_class = getattr(module, dsl_type)
        # store the arguments
        self._dsl_parser = dsl_type_class(dsl_text)
        self._measurements = measurements

    def format_output(self, indent_level):
        # initialise default indent
        default_indent = "  "*indent_level
        # initialise output string
        output_string = "\n"
        # iterate over measurements
        for measurement in self._measurements:
            atomic_constraint_index = measurement["atomic_constraint_index"]
            expression_index = measurement["expression_index"]
            expression_text = self._dsl_parser.get_expression(atomic_constraint_index, expression_index)
            # add to output string
            output_string += f"{default_indent}{expression_text} -> " \
                             f"{measurement['measurement']} " \
                             f"({measurement['module_name']} @ line {measurement['line_number']})\n"
        return output_string

formatter_classes = {
    "FormatSpecDuration": FormatSpecDuration,
    "FormatSpecTimeBetween": FormatSpecTimeBetween,
    "FormatSpecWhenever": FormatSpecWhenever
}

class Formatter:

    def __init__(self, db):
        # store db filename
        self._db = db
        # establish database connection
        self._connection = Connection({"type": "sqlite", "filename": self._db})

    def all_test_suites(self):
        """
        Get all distinct test suite names.
        """
        # get all test suites
        all_test_suites = self._connection.get_all_test_suites()
        return "\n".join(all_test_suites)

    def all_tests(self):
        """
        Get all distinct test names.
        """
        # get all tests
        all_tests = self._connection.get_all_tests()
        return "\n".join(all_tests)

    def all_specs(self):
        """
        Get all specs.
        """
        # get all specs
        all_specs = self._connection.get_all_specs()
        return "\n".join(
            map(lambda spec : f"ID {spec[0]} -> {spec[1]}", all_specs)
        )

    def all_tests_that_violated_spec(self, spec_id):
        """
        Get all tests whose execution involved the specification with spec_id being violated.
        """
        # get all relevant tests
        dsl_type, dsl_text, dictionary = self._connection.get_tests_that_violated_spec(spec_id)
        # initialise output string
        output_string = f"{dsl_text}\n"
        # construct string to output
        if len(dictionary) == 0:
            output_string = "No tests resulted in the given specification being violated."
        else:
            for test_execution_id in dictionary:
                test_execution_data = dictionary[test_execution_id]
                test_name = test_execution_data["test_name"]
                start_time = datetime.fromtimestamp(test_execution_data["start_time"]).strftime('%Y-%m-%d %H:%M:%S')
                output_string += f"\nTest {test_name} (started at {start_time}):\n"
                measurements = test_execution_data["measurements"]
                # get the relevant formatter class
                formatter_class_name = f"Format{dsl_type}"
                formatter_class = formatter_classes[formatter_class_name]
                # instantiate formatter class
                formatter = formatter_class(dsl_type, dsl_text, measurements)
                # construct output string
                output_string += formatter.format_output(indent_level=1)
        return output_string

    def all_specs_violated_during_test(self, test_name):
        """
        Get all specs that were violated during execution of the given test.
        """
        # get all relevant specs
        full_test_name, results_dictionary = self._connection.get_specs_violated_during_test(test_name)
        # initialise output string
        output_string = f"Test {full_test_name}\n"
        # iterate through test executions
        for test_execution_id in results_dictionary:
            test_execution = results_dictionary[test_execution_id]
            test_execution_start_time = \
                datetime.fromtimestamp(test_execution["start_time"]).strftime('%Y-%m-%d %H:%M:%S')
            output_string += f"\n  Execution starting at time {test_execution_start_time}\n"
            monitoring_results = test_execution["monitoring_results"]
            if len(monitoring_results) == 0:
                output_string += f"\n    No specifications were violated.\n"
            else:
                for monitoring_result_id in monitoring_results:
                    monitoring_result = monitoring_results[monitoring_result_id]
                    spec_dsl_text = monitoring_result["spec_dsl_text"]
                    spec_dsl_type = monitoring_result["spec_dsl_type"]
                    measurements = monitoring_result["measurements"]
                    output_string += f"\n    Specification {spec_dsl_text}\n"
                    # get the relevant formatter class
                    formatter_class_name = f"Format{spec_dsl_type}"
                    formatter_class = formatter_classes[formatter_class_name]
                    # instantiate formatter class
                    formatter = formatter_class(spec_dsl_type, spec_dsl_text, measurements)
                    # construct output string
                    output_string += formatter.format_output(indent_level=3)

        return output_string
