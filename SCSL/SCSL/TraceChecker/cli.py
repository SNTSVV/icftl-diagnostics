import argparse
import datetime
import logging
import json
import pathlib
import runpy
import sys

import tracemalloc

from SCSL.TraceChecker import Monitor
from SCSL.Monitoring import get_diagnosis, timer, CustomJSONizer


def main():
    # define command line arguments
    parser = argparse.ArgumentParser(description="Checks traces with respect to SCSL specifications.")
    parser.add_argument("trace_file",
                        help="JSON trace file output by the instrumented program")
    parser.add_argument("project_path",
                        help="Path to the instrumented project (default: '.')",
                        type=pathlib.Path,
                        nargs='?',
                        default=pathlib.Path('.'))
    parser.add_argument("--write-tree",
                        action='store_true',
                        help="Write the final monitoring tree to .gv and .pdf files.")
    parser.add_argument("--down",
                        dest='tree_eval_strategy',
                        action='store_const',
                        const='down',
                        default='up',
                        help="Evaluate the tree from the root down rather than from the leaves up.")

    # parse the arguments
    args = parser.parse_args()

    # initialise logging
    logging_path = pathlib.Path('./logs')
    logging_path.mkdir(exist_ok=True)
    logging.basicConfig(filename=f'{logging_path}/scsl-trace-checker-{datetime.datetime.now().isoformat()}',
                        filemode='a',
                        format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    # read specification from the file generated by instrumentation
    compiled_spec_path: pathlib.Path = args.project_path.joinpath('compiled_spec.py')
    if not compiled_spec_path.exists():
        print('SCSL.TraceChecker: Failed to find a compiled specification in the project directory!')
        print('Has the project been instrumented?')
        sys.exit(-1)

    specifications = runpy.run_path(str(compiled_spec_path))['specifications']

    # read in trace
    with open(args.trace_file) as h:
        trace = json.loads(h.read())

    # use the spec ids stored in the trace to get the specification object we need
    if len(trace) > 0:
        specification = specifications[trace[0]["spec_id"]]
    else:
        print("Trace is empty - nothing to do.")
        exit()

    # instantiate a monitor
    monitor = Monitor(specification, args.tree_eval_strategy)
    for event in trace:
        monitor.process_event(event)

    # perform final tasks (such as tree resolution for inconclusive verdicts)
    monitor.wrap_up()

    # print verdict
    final_verdict = monitor.get_verdict()
    print(f"SIMPLE VERDICT: {final_verdict}\n")

    print(monitor.get_verdict_explanation())

    print("\nSTATISTICS:\n")

    print(f"{monitor.get_number_of_events_observed()} events processed")

    print(f"{monitor.get_tree_size()} monitoring tree nodes")

    # if args.write_tree:
    #     # write out monitoring tree
    #     monitor.write_tree_to_file("final-tree.gv")
    #     print("Final state of monitoring tree written to 'final-tree.gv.pdf'.")

    # EVALUATION
    tracemalloc.start()

    # get diagnosis
    diagnosis, time = get_diagnosis(specification, trace, monitor)

    print(f"Consumed memory: current {tracemalloc.get_traced_memory()[0] / (1024):0.4f} kB"
          f" and the peak {tracemalloc.get_traced_memory()[1] / (1024):0.4f} kB")

    memory = tracemalloc.get_traced_memory()[1] / (1024)
    tracemalloc.stop()

    time_mem = tuple([time, memory])  # Replace with your time and memory data
    with open(f'diagnosis-{0}.json', "w") as out_file:
        print(f'The diagnosis ({len(diagnosis)} events) was written as diagnosis-{0}.json!')
        out_file.write(json.dumps(diagnosis, cls=CustomJSONizer))

    # Reading existing time-mem data from 'time-mem-{0}.json'
    existing_data = []
    try:
        with open(f'time-mem-{0}.json', 'r') as in_file:
            content = in_file.read()
            if content:
                existing_data = json.loads(content)
    except FileNotFoundError:
        print(f'File not found. Creating a new file.')

    # Appending new time_mem to existing_data
    existing_data.append(time_mem)

    # Writing the combined data back to 'time-mem-{0}.json'
    with open(f'time-mem-{0}.json', "w") as out_file:
        print(f'The time and memory was written as time-mem-{0}.json!')
        out_file.write(json.dumps(existing_data, cls=CustomJSONizer, separators=(',', ']')))

