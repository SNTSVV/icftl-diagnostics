# Standard library imports
import contextlib
import datetime
import json
import logging
import os
import subprocess
import traceback
import pathlib
import sys
import typing
from typing import Optional, List, Union, Tuple
import unittest
import time

from InstrumentPythonSCSL import Instrument
from InstrumentPythonSCSL.Database.database import Connection, check_database
from SCSL.Specifications.simplified_lang_translator import _compile_specification_to_python_code, \
    _eval_specification_from_python_code, _write_specification, _compile_specification_to_dsl_list
from SCSL.TraceChecker import combine_verdicts
import SCSL.Monitoring
import SCSL.Monitoring.monitoring


# initialise dictionary mapping specification filenames to indices, to database ids
_spec_filename_index_db_id_map = {}
# initialise a global variable for the current specification file being used
_current_spec_filename = None


@contextlib.contextmanager
def _working_directory(path: Union[str, pathlib.Path]):
    """
    Temporarily change working directory

    This context manager temporarily sets the working directory to `path`
    and adds it to `sys.path`. On exit, the previous working directory
    will be restored and `path` will be removed from `sys.path` (unless
    it was also added there independently of the execution of the
    context manager).
    """
    # Based on: https://stackoverflow.com/a/42441759
    prev_cwd = pathlib.Path.cwd()
    temp_cwd = str(pathlib.Path(path).resolve())

    os.chdir(temp_cwd)
    # Also add the working directory to PATH
    sys.path.append(temp_cwd)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
        try:
            # Note that if temp_cwd is present in sys.path more than once,
            # it will only be removed once. This is the desired behaviour.
            sys.path.remove(temp_cwd)
        except ValueError:
            # If, for any reason, temp_cwd is no longer present in sys.path,
            # do nothing.
            pass


def instrument_run_and_verify(
        specification_path: Union[str, pathlib.Path],
        entry_point: Union[str, pathlib.Path],
        project_root: Union[str, pathlib.Path] = '.',
        cli_arguments: List[str] = None,
        additional_paths: Optional[List[Union[str, pathlib.Path]]] = None
) -> dict:
    """
    Instruments, runs, and verifies a project with respect to a specification

    :param specification_path: Path to the specification (.scsl) file.
    :param entry_point: Path to the Python program to execute
    :param cli_arguments: List of command-line arguments to provide to the Python program
    :param project_root: The directory where the project is located. Paths mentioned in the specification are relative
        to this directory.
    :param additional_paths: Any additional paths that need to be added to PYTHONPATH before executing the program
    :return: Monitoring statistics
    """
    d = evaluate_performance(1,
                             specification_path,
                             entry_point,
                             cli_arguments,
                             project_root,
                             additional_paths)

    # The dictionary returned by evaluate_performance should never be empty
    assert d != {}

    for key in d.keys():
        if 'error' in key:
            raise RuntimeError
    # return d['individual_executions'][0]
    return {
        spec_id: d[spec_id]['individual_executions'][0][spec_id]
        for spec_id in d
    }

def setup_specifications(specification_path, project_root):
    """
    Given the path to a specification file, and the root directory of a project,
    perform the setup procedure ready for testing code to be executed.

    The setup procedure involves:
    1) Compiling the specification, and
    2) Inserting the specifications into the results database.
    """
    global _current_spec_filename, _spec_filename_index_db_id_map
    # set the current spec file
    _current_spec_filename = str(specification_path)

    # Compile the DSL specifications in the specification file into Python code
    logging.info(f'Processing specification file {specification_path}')
    python_code = _compile_specification_to_python_code(str(specification_path))
    specifications = _eval_specification_from_python_code(python_code)
    _write_specification(python_code, str(project_root) + '/compiled_spec.py')

    # get the DSL text for each specification, create a row in the specification table in the database,
    # and update the global map from spec filenames to indices and db ids
    connection = Connection({"type": "sqlite", "filename": "results.db"})
    dsl_type_text_list = _compile_specification_to_dsl_list(str(specification_path))
    for spec_index, (spec_dsl_type, spec_dsl_text) in enumerate(dsl_type_text_list):
        spec_path = str(specification_path)
        # perform the insertion
        # this will check for existence of the specification, and give us the id if it's already in the db
        spec_db_id = connection.insert_specification(spec_dsl_type, spec_dsl_text)
        # update the global dictionary
        if spec_path in _spec_filename_index_db_id_map:
            _spec_filename_index_db_id_map[spec_path][spec_index] = spec_db_id
        else:
            _spec_filename_index_db_id_map[spec_path] = {
                spec_index: spec_db_id
            }

    return specifications

@contextlib.contextmanager
def instrumented_for_specification(specification_path: Union[str, pathlib.Path],
                                   project_root: Union[str, pathlib.Path] = '.',
                                   online: bool = True,
                                   debug: bool = False):
    # setup specifications
    specifications = setup_specifications(specification_path, project_root)

    SCSL.Monitoring.monitoring._context_manager_instrumentation_specifications = repr(specifications)

    # Perform the instrumentation
    instrument = Instrument(specifications, str(project_root), online, debug)
    instrument.insert_instruments()
    instrument.compile()

    try:
        # Return control to caller
        yield
    finally:
        # With the context closed, reset the instrumented files
        Instrument.reset_instrumented_files(project_root)


def run_and_verify_online(
        entry_point: Union[str, pathlib.Path],
        project_root: Union[str, pathlib.Path] = '.',
        cli_arguments: List[str] = None,
        additional_paths: Optional[List[Union[str, pathlib.Path]]] = None
) -> dict:
    """
    Runs and verifies a project instrumented for online monitoring

    :param entry_point: Path to the Python program to execute
    :param cli_arguments: List of command-line arguments to provide to the Python program
    :param project_root: The directory where the project is located. Paths mentioned in the specification are relative
        to this directory.
    :param additional_paths: Any additional paths that need to be added to PYTHONPATH before executing the program

    :return: A dict with performance statistics.
    :raises FileNotFoundError: If the file with monitoring statistics (which should be produced by the instrumented
        program) was not found.
    """
    # Since we'll be changing the working directory, paths need to be resolved
    project_root = pathlib.Path(project_root).resolve()
    entry_point = pathlib.Path(entry_point).resolve()

    with _working_directory(project_root):
        # Copy the environment variables and add the necessary paths to PYTHONPATH
        env = os.environ.copy()
        env['PYTHONPATH'] = f'{env.get("PYTHONPATH", "")}:{str(entry_point.parent)}:{str(project_root)}'
        if additional_paths is not None:
            for path in additional_paths:
                env['PYTHONPATH'] += ':' + str(pathlib.Path(path).resolve())
        logging.info(f'Project will be executed with PYTHONPATH = "{env["PYTHONPATH"]}"')

        # Execute
        command = [sys.executable, str(entry_point)] + (cli_arguments if cli_arguments is not None else [])
        logging.info(f'Command: {command}')
        subprocess.run(command, env=env)

        # Collect results
        statistics_path = project_root.joinpath('monitoring-statistics.json')
        with statistics_path.open() as in_file:
            statistics = json.load(in_file)

        try:
            os.remove(statistics_path)
        except FileNotFoundError:
            pass

        return statistics


def evaluate_performance(number_of_executions: int,
                         specification_path: Union[str, pathlib.Path],
                         entry_point: Union[str, pathlib.Path],
                         cli_arguments: List[str] = None,
                         project_root: Union[str, pathlib.Path] = '.',
                         additional_paths: Optional[List[Union[str, pathlib.Path]]] = None) -> dict:
    """
    Instruments, runs and verifies a project N times and measures performance for evaluation purposes

    :param number_of_executions: How many times the Python program should be executed
    :param specification_path: Path to the specification (.scsl) file.
    :param entry_point: Path to the Python program to execute
    :param cli_arguments: List of command-line arguments to provide to the Python program
    :param project_root: The directory where the project is located. Paths mentioned in the specification are relative
        to this directory.
    :param additional_paths: Any additional paths that need to be added to PYTHONPATH before executing the program

    :return: A dict with performance statistics. In the event of an error,
    {'<instrumentation|specification|runtime>_error': '<error description>'} will be
        returned.
    """
    # Since we'll be changing the working directory, paths need to be resolved
    project_root = pathlib.Path(project_root).resolve()
    specification_path = pathlib.Path(specification_path).resolve()
    entry_point = pathlib.Path(entry_point).resolve()
    if additional_paths is None:
        additional_paths = []
    else:
        additional_paths = [pathlib.Path(path).resolve() for path in additional_paths]

    logging.info(f'test_specification({number_of_executions=}, {project_root=}, {specification_path=}, {entry_point=}, '
                 f'{cli_arguments=}, {additional_paths=})')

    with _working_directory(project_root):
        try:
            # Compile the DSL specification into Python code
            logging.info(f'Compiling specification {specification_path}')
            python_code = _compile_specification_to_python_code(str(specification_path))
            specifications = _eval_specification_from_python_code(python_code)
        except Exception:
            error_msg = f'test_specification: An error was encountered ' \
                        f'while parsing the specification {specification_path}:\n' \
                        + ''.join(traceback.format_exc())
            logging.error(error_msg)
            print(error_msg)
            return {"specification_error": error_msg}

        compiled_spec_path = project_root.joinpath('compiled_spec.py')
        _write_specification(python_code, str(compiled_spec_path))

        try:
            # Perform the instrumentation
            instrument = Instrument(specifications, str(project_root), True, debug=False)
            instrument.insert_instruments()
            instrument.compile()
        except Exception:
            error_msg = 'test_specification: An error was encountered during instrumentation (see below):\n' \
                        + ''.join(traceback.format_exc())
            logging.error(error_msg)
            print(error_msg)
            return {"instrumentation_error": error_msg}

        # Each row of each table contains the verdict, lag, relative lag, and memory consumed
        # for one execution of the program under scrutiny

        spec_ids: typing.List[str] = [str(i) for i in range(len(specifications))]
        tables: typing.Dict[str, typing.List[tuple]] = {
            spec_id: []
            for spec_id in spec_ids
        }
        individual_execution_results: typing.Dict[str, list] = {
            spec_id: []
            for spec_id in spec_ids
        }

        for i in range(1, number_of_executions + 1):
            logging.info(f'Execution {i}')
            print('Execution', i)

            # Collect results from this execution
            try:
                execution_result = run_and_verify_online(entry_point, project_root, cli_arguments, additional_paths)

                for spec_id in spec_ids:
                    tables[spec_id].append((
                        execution_result[spec_id]['verdict'],
                        execution_result[spec_id]['lag'],
                        execution_result[spec_id]['relative_lag'],
                        execution_result[spec_id]['memory_consumed'],
                        execution_result[spec_id]['event_processing_time'],
                        execution_result[spec_id]['relative_event_processing_time'],
                        execution_result[spec_id]['number_of_events']
                    ))
                    individual_execution_results[spec_id].append(execution_result)

            except FileNotFoundError:
                statistics_path = project_root.joinpath('monitoring-statistics.json')
                error_msg = f'test_specification: Could not read {statistics_path}.\n' \
                            f'Maybe the instrumented program encountered an error?'
                print(error_msg)
                return {"runtime_error": error_msg}

        # We don't need the instrumented code anymore
        Instrument.reset_instrumented_files(project_root)

        # Return results
        result_statistics: typing.Dict[str, dict] = {}
        for spec_id in spec_ids:
            result_statistics[spec_id] = {
                'execution_count': number_of_executions,
                'average_verdict': sum(1 for entry in tables[spec_id] if entry[0] is True) / number_of_executions,
                'average_lag': sum(entry[1] for entry in tables[spec_id]) / number_of_executions,
                'average_relative_lag': sum(entry[2] for entry in tables[spec_id]) / number_of_executions,
                'average_memory_consumed': sum(entry[3] for entry in tables[spec_id]) / number_of_executions,
                'average_event_processing_time': sum(entry[4] for entry in tables[spec_id]) / number_of_executions,
                'average_relative_event_processing_time': sum(
                    entry[5] for entry in tables[spec_id]) / number_of_executions,
                'average_number_of_events': sum(entry[6] for entry in tables[spec_id]) / number_of_executions,
                'individual_executions': individual_execution_results[spec_id],
            }
        return result_statistics


class TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        SCSL.Monitoring.monitoring._allow_restart = True

        print(f"running tests for test suite {cls.__name__}")

        # initialise logging
        log_directory = pathlib.Path('./logs')
        log_directory.mkdir(exist_ok=True)
        log_file = log_directory.joinpath(f'scsl-unittest-{datetime.datetime.now().isoformat().replace(":", ".")}')
        logging.basicConfig(filename=str(log_file),
                            filemode='a',
                            format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)

        print(f'Log: {log_file}')

        # initialise database connection, ready for test/monitoring information to be written
        connection_data = {
            "type": "sqlite",
            "filename": "results.db"
        }
        # check the state of the database
        check_database(connection_data)
        # by attaching _database_connection to cls, we're assuming that
        # the class will only be instantiated once and, if instantiated multiple times, the database connection will
        # be the same for each new instance (since we're defining a class variable, rather than an instance variable)
        cls._database_connection = Connection(connection_data)

        # create a row in the database for the current test suite execution
        test_suite_name = f"{cls.__module__}.{cls.__name__}"
        test_suite_start_time = time.time()
        test_suite_execution_id = cls._database_connection.insert_test_suite_execution(
            test_suite_name,
            test_suite_start_time
        )
        # store the test suite execution id
        cls._test_suite_execution_id = test_suite_execution_id

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"finished running tests for test suite {cls.__name__}")

    def setUp(self):
        # store start time of the test
        self._test_start_time = time.time()
        # initialise empty dictionary for monitoring results
        self._monitoring_results = {}

    def tearDown(self):
        global _spec_filename_index_db_id_map
        # insert the test execution and get its id
        test_execution_id = self._database_connection.insert_test_execution(
            self.id(),
            self._test_start_time,
            self._test_suite_execution_id
        )
        # get the map from spec indices (in individual spec files) to db ids
        spec_index_to_db_id = _spec_filename_index_db_id_map[_current_spec_filename]
        self._database_connection.insert_monitoring_results(
            self._monitoring_results,
            test_execution_id,
            spec_index_to_db_id
        )

    @staticmethod
    def _getChildProcessVerdictAndExplanation(specification_path: Union[str, pathlib.Path],
                                              entry_point: Union[str, pathlib.Path],
                                              project_root: Union[str, pathlib.Path] = '.',
                                              cli_arguments: List[str] = None,
                                              additional_paths: Optional[List[Union[str, pathlib.Path]]] = None
                                              ) -> Tuple[List[Optional[bool]], List[str]]:

        # setup specifications
        specifications = setup_specifications(specification_path, project_root)

        # instrument the source code, execute it and get trace checking results
        result = instrument_run_and_verify(
            specification_path,
            entry_point,
            project_root,
            cli_arguments,
            additional_paths
        )
        measurements_data = [
            result[spec_id]["measurement_data"]
            for spec_id in result
        ]
        verdicts = [
            result[spec_id]['verdict']
            for spec_id in result
        ]
        verdict_explanations = [
            '\n' + result[spec_id]['verdict_explanation']
            for spec_id in result
        ]

        return verdicts, verdict_explanations, measurements_data

    def assertOnlineVerdictTrue(self):
        # get the results of monitoring, with explanation messages
        results = self.getAllOnlineVerdictsAndExplanations()

        # we first get all monitoring results, and then assert on them
        # if we got monitoring results and then asserted in the same loop, an assertion failing would
        # prevent us from recording the other monitoring results
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # assert on result
            self.assertTrue(verdict, msg="Use scsl-inspect to investigate.")

    def assertOnlineVerdictFalse(self):
        # get the results of monitoring, with explanation messages
        results = self.getAllOnlineVerdictsAndExplanations()

        # we first get all monitoring results, and then assert on them
        # if we got monitoring results and then asserted in the same loop, an assertion failing would
        # prevent us from recording the other monitoring results
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # assert on result
            self.assertFalse(verdict, msg="Use scsl-inspect to investigate.")

    def assertOnlineVerdictIsNone(self):
        # get the results of monitoring, with explanation messages
        results = self.getAllOnlineVerdictsAndExplanations()

        # we first get all monitoring results, and then assert on them
        # if we got monitoring results and then asserted in the same loop, an assertion failing would
        # prevent us from recording the other monitoring results
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # assert on result
            self.assertIsNone(verdict, msg="Use scsl-inspect to investigate.")

    def assertOnlineVerdictIsNotNone(self):
        # get the results of monitoring, with explanation messages
        results = self.getAllOnlineVerdictsAndExplanations()

        # we first get all monitoring results, and then assert on them
        # if we got monitoring results and then asserted in the same loop, an assertion failing would
        # prevent us from recording the other monitoring results
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # assert on result
            self.assertIsNotNone(verdict, msg="Use scsl-inspect to investigate.")

    def assertVerdictTrue(self,
                          specification_path: Union[str, pathlib.Path],
                          entry_point: Union[str, pathlib.Path],
                          project_root: Union[str, pathlib.Path] = '.',
                          cli_arguments: List[str] = None,
                          additional_paths: Optional[List[Union[str, pathlib.Path]]] = None):
        # get the results of monitoring
        results = self._getChildProcessVerdictAndExplanation(
                specification_path, entry_point, project_root, cli_arguments, additional_paths)

        # store the measurements
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        # assert on the verdicts
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            self.assertTrue(verdict, explanation)

    def assertVerdictFalse(self,
                           specification_path: Union[str, pathlib.Path],
                           entry_point: Union[str, pathlib.Path],
                           project_root: Union[str, pathlib.Path] = '.',
                           cli_arguments: List[str] = None,
                           additional_paths: Optional[List[Union[str, pathlib.Path]]] = None):
        # get the results of monitoring
        results = self._getChildProcessVerdictAndExplanation(
            specification_path, entry_point, project_root, cli_arguments, additional_paths)

        # store the measurements
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        # assert on the verdicts
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            self.assertFalse(verdict, explanation)

    def assertVerdictIsNone(self,
                            specification_path: Union[str, pathlib.Path],
                            entry_point: Union[str, pathlib.Path],
                            project_root: Union[str, pathlib.Path] = '.',
                            cli_arguments: List[str] = None,
                            additional_paths: Optional[List[Union[str, pathlib.Path]]] = None):
        # get the results of monitoring
        results = self._getChildProcessVerdictAndExplanation(
            specification_path, entry_point, project_root, cli_arguments, additional_paths)

        # store the measurements
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        # assert on the verdicts
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            self.assertTrue(verdict, explanation)

    def assertVerdictIsNotNone(self,
                               specification_path: Union[str, pathlib.Path],
                               entry_point: Union[str, pathlib.Path],
                               project_root: Union[str, pathlib.Path] = '.',
                               cli_arguments: List[str] = None,
                               additional_paths: Optional[List[Union[str, pathlib.Path]]] = None):
        # get the results of monitoring
        results = self._getChildProcessVerdictAndExplanation(
            specification_path, entry_point, project_root, cli_arguments, additional_paths)

        # store the measurements
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            # store the measurements, ready for them to be inserted during tearDown
            self._monitoring_results[index] = {
                "verdict": verdict,
                "atomic_constraint_checks": measurements_data
            }

        # assert on the verdicts
        for index, (verdict, explanation, measurements_data) in \
                enumerate(zip(*results)):
            self.assertTrue(verdict, explanation)

    @staticmethod
    def getOnlineVerdictAndExplanation() -> Tuple[Optional[bool], str]:
        verdicts, explanations = TestCase.getAllOnlineVerdictsAndExplanations()
        verdict = combine_verdicts(verdicts)
        verdict_explanation = '\n'.join(explanations)

        return verdict, verdict_explanation

    @staticmethod
    def getAllOnlineVerdictsAndExplanations() -> Tuple[List[Optional[bool]], List[str]]:
        if not SCSL.Monitoring.monitoring._online:
            raise RuntimeError('Online verdict can only be retrieved during online testing!')
        elif not SCSL.Monitoring.monitoring._monitoring_running:
            raise RuntimeError('Verdict could not be retrieved as monitoring is no longer running!')

        test_result = SCSL.Monitoring.end_monitoring()

        measurements_data = [
            test_result[spec_id]["measurement_data"]
            for spec_id in test_result
        ]

        verdicts = [
            test_result[spec_id]['verdict']
            for spec_id in test_result
        ]
        verdict_explanations = [
            '\n' + test_result[spec_id]['verdict_explanation']
            for spec_id in test_result
        ]

        return verdicts, verdict_explanations, measurements_data
