import argparse
import datetime
import logging
import pathlib
import runpy
import shutil

from .instrument import Instrument
from SCSL.Specifications.translator import compile_specification as compile_spec_scsl
from SCSL.Specifications.simplified_lang_translator import compile_specification as compile_spec_simplified


def main():
    # initialise logging
    logging_path = pathlib.Path('./logs')
    logging_path.mkdir(exist_ok=True)
    logging.basicConfig(filename=f'{logging_path}/scsl-instrument-python-{datetime.datetime.now().isoformat()}',
                        filemode='a',
                        format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    # define command line arguments
    parser = argparse.ArgumentParser(
        'scsl-instrument-python',
        description="Instruments Python projects with respect to SCSL specifications.")
    parser.add_argument("--online",
                        help="Instrument for online monitoring",
                        action='store_true')
    parser.add_argument('--debug',
                        help="Write some additional files useful for debugging and measurements",
                        action='store_true')
    parser.add_argument("specification_path",
                        type=str,
                        help="Path to the specification with respect to which to instrument.")
    parser.add_argument("project_path",
                        help="Path to the project to instrument (default: '.')",
                        nargs='?',
                        default='.')

    # parse the arguments
    args = parser.parse_args()

    if args.specification_path.endswith('.py'):
        # Specification is already pre-compiled
        compiled_spec = args.specification_path
        shutil.copyfile(args.specification_path, args.project_path + "/compiled_spec.py")
    elif args.specification_path.endswith(".scsl"):
        # specification is in DSL: compile it first and then place it into project directory
        compiled_spec = args.project_path + "/compiled_spec.py"
        compile_spec_scsl(args.specification_path, compiled_spec)
    elif args.specification_path.endswith(".pecl"):
        # specification is in simplified DSL: compile it first and then place it into project directory
        compiled_spec = args.project_path + "/compiled_spec.py"
        compile_spec_simplified(args.specification_path, compiled_spec)

    # load the specifications
    specifications = runpy.run_path(compiled_spec)['specifications']

    # perform instrumentation
    instrument = Instrument(specifications, args.project_path, args.online, debug=args.debug)
    instrument.insert_instruments()
    instrument.compile()


def restore():
    # initialise logging
    logging_path = pathlib.Path('./logs')
    logging_path.mkdir(exist_ok=True)
    logging.basicConfig(filename=f'{logging_path}/scsl-instrument-restore-{datetime.datetime.now().isoformat()}',
                        filemode='a',
                        format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.DEBUG)

    # define command line arguments
    parser = argparse.ArgumentParser(
        'scsl-instrument-restore',
        description="Restores instrumented files from backup.")

    parser.add_argument("project_path",
                        help="Path to the project to instrument (default: '.')",
                        nargs='?',
                        default='.')

    args = parser.parse_args()
    Instrument.reset_instrumented_files(args.project_path)
