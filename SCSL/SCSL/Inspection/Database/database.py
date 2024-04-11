"""
Module holding logic for writing test/monitoring results to a database.

All of this is done through an adapter that implements a specific interface, but contains
logic specific to individual database types (SQLite, Postgres, etc.)
"""
from .Adaptors import SQLite

class Connection:
    """
    Class containing logic for writing specific test/monitoring results to a database.
    """

    def __init__(self, connection_data):
        """
        Given `connection_data`, establish a database connection.
        """
        # store connection data
        self._connection_data = connection_data
        # initialise connection, depending on the type of the database
        if connection_data["type"] == "sqlite":
            self._connection = SQLite(connection_data["filename"])

    def check_for_tables(self):
        """
        Check for the existence of all necessary tables in the database.
        """
        # initialise list of tables to check for
        tables = [
            "test_suite_execution",
            "test_execution",
            "monitoring_result",
            "specification",
            "atomic_constraint_check",
            "measurement"
        ]
        # iterate through tables and check
        for table in tables:
            result = self._connection.query("select * from sqlite_master where type = 'table' and name = ?", table)
            if len(result) == 0:
                return False
        return True

    def get_all_tests(self):
        """
        Get a list of all tests in the database.
        """
        results = self._connection.query("select distinct test_name from test_execution")
        tests = list(map(lambda row : row[0], results))
        return tests

    def get_all_test_suites(self):
        """
        Get a list of all test suites in the database.
        """
        results = self._connection.query("select distinct test_suite_name from test_suite_execution")
        test_suites = list(map(lambda row : row[0], results))
        return test_suites

    def get_all_specs(self):
        """
        Get a list of all specs in the database.
        """
        results = self._connection.query("select id, dsl_text from specification")
        return results

    def get_tests_that_violated_spec(self, spec_id):
        """
        Given a spec id, get all tests that generated a monitoring_result row (with a false truth value),
        corresponding with the spec id.

        This is done by joining the specification table (matching our spec id) with the monitoring_result table,
        and then on the test_execution table. Once this is done, we select all rows that contain a false truth value
        for the monitoring_result.
        """
        # get spec row
        spec_rows = self._connection.query(
            "select dsl_type, dsl_text from specification where id = ?",
            spec_id
        )
        if len(spec_rows) == 0:
            print(f"No specification found with ID {spec_id}")
            exit()
        # get dsl text of the spec
        dsl_type, dsl_text = spec_rows[0]
        # initialise final dictionary
        final_dictionary = {}
        # define query
        query = """
        select test_execution.id, test_execution.test_name, test_execution.start_time, monitoring_result.id from (
            specification inner join (
                    monitoring_result inner join test_execution
                        on monitoring_result.test_execution = test_execution.id
                )
                on monitoring_result.specification = specification.id
        ) where monitoring_result.truth_value = 0 and specification.id = ?
        """
        results = self._connection.query(query, spec_id)
        for result in results:
            # store the values from the row
            test_execution_id = result[0]
            test_execution_test_name = result[1]
            test_execution_start_time = result[2]
            monitoring_result_id = result[3]
            # add to final dictionary
            final_dictionary[test_execution_id] = {
                "test_name": test_execution_test_name,
                "start_time": test_execution_start_time,
                "measurements": []
            }
            # get the atomic constraints checks, and their measurements, for the monitoring result
            measurements_query = """
            select
                atomic_constraint_check.atomic_constraint_index,
                atomic_constraint_check.binding,
                measurement.measurement_value,
                measurement.module_name,
                measurement.line_number,
                measurement.expression_index
            from (
                atomic_constraint_check inner join measurement
                    on atomic_constraint_check.id = measurement.atomic_constraint_check
            ) where atomic_constraint_check.monitoring_result = ?
            """
            measurements = self._connection.query(measurements_query, monitoring_result_id)
            # construct a list of dictionaries
            headers = ["atomic_constraint_index", "binding", "measurement",
                       "module_name", "line_number", "expression_index"]
            dictionaries = []
            for row in measurements:
                dictionaries.append(
                    dict(zip(headers, row))
                )
                final_dictionary[test_execution_id]["measurements"] = dictionaries

        return dsl_type, dsl_text, final_dictionary

    def get_specs_violated_during_test(self, test_name):
        """
        Given a test name, get all specifications that were violated during executions of that test.

        This is done by joining the test_execution table (matching our test_name) with the monitoring_result table,
        and then with the specification table.
        """
        # get the full test name
        result = self._connection.query(
            "select test_name from test_execution where test_name like ?",
            f"%{test_name}"
        )
        if len(result) > 0:
            full_test_name = result[0][0]
        else:
            print(f"No test could be found with the name '{test_name}'.")
            exit()
        # initialise final dictionary mapping test_execution IDs to dictionaries,
        # which map monitoring results to measurements
        final_dict = {}
        # get the executions of the given test
        test_execution_rows = self._connection.query(
            "select id, start_time from test_execution where test_name = ?",
            full_test_name
        )
        # for each test execution, get the monitoring results and specification information
        for test_execution_row in test_execution_rows:
            test_execution_id = test_execution_row[0]
            test_execution_start_time = test_execution_row[1]
            # add to final_dict
            final_dict[test_execution_id] = {"monitoring_results": {}, "start_time": test_execution_start_time}
            query = """
            select specification.dsl_type, specification.dsl_text, monitoring_result.id from (
                test_execution inner join (
                    monitoring_result inner join specification on monitoring_result.specification = specification.id
                ) on test_execution.id = monitoring_result.test_execution
            ) where test_execution.id = ? and monitoring_result.truth_value = 0
            """
            results = self._connection.query(query, test_execution_id)
            # for each spec ID, get the list of measurements taken at runtime during the test execution
            for result in results:
                specification_dsl_type = result[0]
                specification_dsl_text = result[1]
                monitoring_result_id = result[2]
                # add entry to final_dict for monitoring result ID
                final_dict[test_execution_id]["monitoring_results"][monitoring_result_id] = {
                    "spec_dsl_text": specification_dsl_text,
                    "spec_dsl_type": specification_dsl_type,
                    "measurements": []
                }
                # get the atomic constraint checks, and corresponding measurements, for the monitoring result
                measurements_query = """
                select
                    atomic_constraint_check.atomic_constraint_index,
                    atomic_constraint_check.binding,
                    measurement.measurement_value,
                    measurement.module_name,
                    measurement.line_number,
                    measurement.expression_index
                from (
                    atomic_constraint_check inner join measurement
                        on atomic_constraint_check.id = measurement.atomic_constraint_check
                ) where atomic_constraint_check.monitoring_result = ?
                """
                measurements = self._connection.query(measurements_query, monitoring_result_id)
                for measurement in measurements:
                    atomic_constraint_index = measurement[0]
                    binding = measurement[1]
                    measurement_value = measurement[2]
                    module_name = measurement[3]
                    line_number = measurement[4]
                    expression_index = measurement[5]
                    final_dict[test_execution_id]["monitoring_results"][monitoring_result_id]["measurements"].append({
                        "atomic_constraint_index": atomic_constraint_index,
                        "measurement": measurement_value,
                        "module_name": module_name,
                        "line_number": line_number,
                        "expression_index": expression_index
                    })

        return full_test_name, final_dict

