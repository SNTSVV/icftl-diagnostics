import atexit
import datetime
import json
import logging
import pathlib
import queue
import sys
import threading
import typing

from typing import List

from SCSL.Specifications.constraints import TimeBetweenLessThanConstant,DurationOfTransitionLessThanNumber
from ..TraceChecker import Monitor, MonitorTreeQuantifierNode,MonitorTreeConjunctionNode,MonitorTreeDisjunctionNode,MonitorTreeNegateNode,MonitorTreeNode

def default_json_format(obj):
    return str(obj)

_monitor: Monitor = None
# to use in offline monitoring
_spec_id_to_event_list: dict = None
# to use in online monitoring
_event_queue = None
# maps spec ids to either _spec_id_to_event_list[spec_id].append (for offline monitoring) or _event_queue.put (for online monitoring)
_spec_id_to_event_appender: dict = None
_event_appender = None
_spec_ids_to_monitors: dict = None
_monitoring_statistics = {}
_online: bool = None
_monitoring_running: bool = False
# This variable is set to repr(<instrumentation specifications>) by
# testing.instrumented_for_specification and is used to check that
# the specification a project is instrumented for matches the one
# that it is being monitored for.
_context_manager_instrumentation_specifications: str = None

# If this flag is True, than process_event will restart monitoring if it has ended
_allow_restart: bool = False

# This semaphore controls setting the boolean _monitoring_running
# (in case two threads run start_monitoring at the same time).
_monitoring_running_semaphore = threading.Semaphore()
_start_time: float = None
_end_monitoring_called: bool = False
_event_processing_thread: threading.Thread = None
_n_events_observed = 0
_debug: bool = False
_project_path: pathlib.Path = None
# For the moment, we assume specifications start with a quantifier
_specifications: list = None
_signals_mentioned_in_specs: List[str] = None

try:
    # JSON encoding fails for traces containing numpy.bool_ objects
    # unless they are converted to bool first

    # noinspection PyUnresolvedReferences
    import numpy


    class CustomJSONizer(json.JSONEncoder):
        def default(self, obj):
            return bool(obj) \
                if isinstance(obj, numpy.bool_) \
                else super().default(obj)
except ImportError:
    # If numpy is not present, do not define a custom JSON encoder
    CustomJSONizer = None


def end_monitoring() -> typing.Optional[dict]:
    """
    Ends monitoring

    For online monitoring, this function wraps up monitoring and obtains a verdict.
    For offline monitoring, it writes out the trace

    :return: for online monitoring, dict with monitoring statistics; for offline, `None`
    """
    global _spec_id_to_event_list, _online, _monitor, _monitoring_statistics,\
        _start_time, _end_monitoring_called, _spec_ids_to_monitors, _monitoring_running

    if _end_monitoring_called:
        logging.warning('end_monitoring called, but monitoring has already ended! Ignoring and returning None.')
        return

    print('Ending monitoring!')
    logging.info('Ending monitoring!')

    with _monitoring_running_semaphore:
        _monitoring_running = False

    if _online:
        for spec_id in _spec_ids_to_monitors:
            _monitoring_statistics[spec_id]["program_duration"] = time.time() - _start_time

    # In case this function is called explicitly, not necessarily at end of execution
    atexit.unregister(end_monitoring)
    if _online:
        _end_monitoring_called = True
        _event_processing_thread.join()
        # wrap up all monitors
        for spec_id in _spec_ids_to_monitors:
            print(f"Performing wrap up procedure for monitor for spec id {spec_id}")
            monitor = _spec_ids_to_monitors[spec_id]
            monitor.wrap_up()
            verdict = monitor.get_verdict()

            print(f"Final verdict for spec id {spec_id} was {verdict}")

            # get measurements data from the monitor
            measurement_data = monitor.get_measurements_for_db()

            _monitoring_statistics[spec_id]['verdict'] = verdict
            _monitoring_statistics[spec_id]['measurement_data'] = measurement_data
            _monitoring_statistics[spec_id]['verdict_explanation'] = monitor.get_verdict_explanation()
            _monitoring_statistics[spec_id]["monitoring_duration"] = time.time() - _start_time
            _monitoring_statistics[spec_id]["lag"] = \
                _monitoring_statistics[spec_id]["monitoring_duration"] - \
                _monitoring_statistics[spec_id]["program_duration"]
            _monitoring_statistics[spec_id]["relative_lag"] = \
                _monitoring_statistics[spec_id]["lag"] / _monitoring_statistics[spec_id]["program_duration"]
            event_processing_times = monitor.get_event_processing_times()
            _monitoring_statistics[spec_id]["event_processing_time"] = sum(event_processing_times)
            _monitoring_statistics[spec_id]["relative_event_processing_time"] = \
                _monitoring_statistics[spec_id]["event_processing_time"] / \
                _monitoring_statistics[spec_id]["program_duration"]
            _monitoring_statistics[spec_id]["number_of_events"] = monitor.get_number_of_events_observed()
            _monitoring_statistics[spec_id]["memory_consumed"] = sys.getsizeof(monitor)

            print(
                f'Lag={_monitoring_statistics[spec_id]["lag"]}s ({_monitoring_statistics[spec_id]["relative_lag"] * 100}% of execution time)')

            with _project_path.joinpath('monitoring-statistics.json').open('w') as out_file:
                json.dump(_monitoring_statistics, out_file, default=default_json_format)
            if _debug:
                monitor.write_tree_to_file(str(_project_path.joinpath("final-tree.gv")))

        return _monitoring_statistics
    else:  # offline monitoring
        # write each trace to a file
        for spec_id, specification in enumerate(_specifications):
            with open(f'trace-{spec_id}.json', "w") as out_file:
                # get event list
                event_list = _spec_id_to_event_list[spec_id]
                print(f'The trace ({len(event_list)} events) was written as trace-{spec_id}.json!')
                out_file.write(json.dumps(event_list, cls=CustomJSONizer))

def start_monitoring(specifications, online: bool, auto_end: bool = False, debug: bool = False,
                     project_path: typing.Union[str, pathlib.Path] = '') -> None:
    logging.info('start_monitoring called')
    global _monitoring_running
    with _monitoring_running_semaphore:
        if _monitoring_running:
            logging.warning('start_monitoring: monitoring is already running! Ignoring!')
            return
        else:
            _monitoring_running = True

    if _context_manager_instrumentation_specifications is not None:
        _monitoring_specification_repr = repr(specifications)
        if _context_manager_instrumentation_specifications == _monitoring_specification_repr:
            logging.debug('Monitoring specifications match instrumentation specifications!')
        else:
            error_message = f'Monitoring specifications do not match instrumentation specifications!\n' \
                            f'Monitoring specifications: {_monitoring_specification_repr}\n' \
                            f'Instrumentation specifications: {_context_manager_instrumentation_specifications}'
            logging.error(error_message)
            raise RuntimeError(error_message)

    print('Starting monitoring!')
    global _monitoring_statistics, _online, _start_time, _event_processing_thread, _spec_id_to_event_appender
    global _event_queue, _spec_id_to_event_list, _project_path, _debug, _specifications, _signals_mentioned_in_specs
    global _event_appender, _spec_ids_to_monitors, _end_monitoring_called
    # All global variables need to be reset in this function, in order to support multiple executions
    _monitoring_statistics.clear()
    _end_monitoring_called = False
    _online = online
    _debug = debug
    _project_path = pathlib.Path(project_path).resolve()
    _specifications = specifications
    try:
        _signals_mentioned_in_specs = []
        for specification in _specifications:
            _signals_mentioned_in_specs += [signal for signal in specification.get_all_signal_names()
                                           if signal not in _signals_mentioned_in_specs]
    except AttributeError:
        logging.error(f'Could not check which signals are mentioned in the specification. '
                      f'All signals will be recorded.')

    if _online:
        # we initialise a single event queue and processing thread
        # all events will go on the same queue, and will be consumed by the same thread
        # the event processing thread will then route each event to the relevant monitor
        _event_queue = queue.Queue()
        _event_appender = _event_queue.put
        # initialise empty dictionary mapping spec ids to monitor instances
        _spec_ids_to_monitors = {}
        # initialise monitor for each specification
        for spec_id, specification in enumerate(_specifications):
            _spec_ids_to_monitors[spec_id] = Monitor(specification)
        # set up and start event processing thread
        _event_processing_thread = threading.Thread(target=online_event_background_processing)
        _event_processing_thread.start()
    else:
        # initialise empty dictionary mapping spec ids to event lists
        _spec_id_to_event_list = {}
        # initialise empty dictionary mapping spec ids to event appender functions
        _spec_id_to_event_appender = {}
        # initialise empty event list for each specification
        for spec_id, specification in enumerate(_specifications):
            _spec_id_to_event_list[spec_id] = []
            _spec_id_to_event_appender[spec_id] = _spec_id_to_event_list[spec_id].append

    # initialise logging
    logging_path = pathlib.Path('./logs')
    logging_path.mkdir(exist_ok=True)
    logging.basicConfig(filename=f'{logging_path}/{datetime.datetime.now().isoformat()}',
                        filemode='a',
                        format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    if auto_end:
        atexit.register(end_monitoring)

    _start_time = time.time()
    # initialise monitoring statistics for each spec id
    for spec_id, specification in enumerate(_specifications):
        _monitoring_statistics[spec_id] = {"program_start_time": _start_time}


def process_event(event):
    global _n_events_observed, _event_appender, _allow_restart
    _n_events_observed += 1
    if not _monitoring_running:
        if _allow_restart and _specifications is not None:
            logging.info('Automatic restart of monitoring is enabled. Restarting monitoring!')
            start_monitoring(_specifications, _online, False, _debug, _project_path)
        else:
            logging.error('Error processing event – monitoring has not yet started! Event ignored.')
            return

    if _online:
        # monitoring - each event is routed to the same event queue
        _event_appender(event)
    else:
        # trace checking - each event is routed to the relevant trace
        # get the spec id
        spec_id = event["spec_id"]
        # get the event appender function
        event_appender = _spec_id_to_event_appender[spec_id]
        event_appender(event)


def process_signal_event(signal_name: str, value: float):
    logging.debug(f'process_signal_event: Recording signal "{signal_name}"={value} of type "{type(value)}"')
    if signal_name not in _signals_mentioned_in_specs:
        return

    process_event({
        "type": "signal",
        "signal_name": signal_name,
        "time": time.time() - _start_time,
        "value": float(value)
    })


def online_event_background_processing():
    """
    Process events in the background during online monitoring
    """
    events_processed = 0
    loop_iterations = 0
    iterations_since_last_event = 0
    main_thread_checks = 0

    while True:
        loop_iterations += 1
        # if loop_iterations % 10000 == 0:
        #     return
        if _event_queue.empty():
            iterations_since_last_event += 1
            # Event queue is empty. This means that either:
            #    1) monitoring was ended by calling end_monitoring(), or
            #    2) all events generated so far have already been processed, and the program under scrutiny has not yet
            #       generated any new events.
            if _end_monitoring_called:
                # End background processing
                logging.info(
                    f'online_event_background_processing finished:\n\t{events_processed=}, {loop_iterations=}, {main_thread_checks=}')
                return
            # elif loop_iterations % 1_000_000 == 0 and not threading.main_thread().is_alive():
            elif iterations_since_last_event % 100 == 0:
                main_thread_checks += 1
                if not threading.main_thread().is_alive():
                    logging.info('The main thread is no longer alive')
                    logging.info(
                        f'online_event_background_processing finished:\n\t{events_processed=}, {loop_iterations=}, {main_thread_checks=}')
                    return
            else:
                # Return control to the program under scrutiny
                time.sleep(0)
        else:  # If the event queue is not empty
            # Process an event
            iterations_since_last_event = 0
            # Process one event
            # If we set block=True, we wouldn't be able to detect the main thread ending
            latest_event = _event_queue.get(block=False)
            # get the spec id for the monitor that it should go to
            spec_id = latest_event["spec_id"]
            # get the relevant monitor
            monitor = _spec_ids_to_monitors[spec_id]
            # process the event
            monitor.process_event(latest_event)
            _event_queue.task_done()
            events_processed += 1


###################################################################################################
#       The functions below are part of diagnosis      #
###################################################################################################
# EVALUATION
import functools
import time

def timer(get_diagnosis):
    @functools.wraps(get_diagnosis)
    def wrapper_timer(*args, **kwargs):
        tic = time.perf_counter()
        value = get_diagnosis(*args, **kwargs)
        toc = time.perf_counter()
        elapsed_time = toc - tic
        print(f"Elapsed time: {elapsed_time*1000} ms")
        return value,elapsed_time*1000
    return wrapper_timer
# end EVALUATION

def get_false_atoms_per_false_bindings(monitor):
    # Get monitoring tree and traverse it each branch depthwise. each branch from root represents a binding
    # start at root of tree which is self._monitoring_tree
    # once you find a node that is no longer a quantifier: if type(current_node) is MonitorTreeQuantifierNode:
    # get next node, and get it value as it is gonna be the result of the boolean connectives
    # get its value (boolean)
    # if its false, then it represents the binding we want so use get binding
    binding_nodes = []
    falsifying_atoms = []
    # traverse the nodes in the monitoring tree
    for node in monitor._all_nodes:
        # if the node we observe is not a quantifier anymore
        if not isinstance(node, MonitorTreeQuantifierNode):
            # we get the parent of that node
            parent= node.get_parent()
            # if the parent is a quantifier
            if isinstance(parent, MonitorTreeQuantifierNode):
                # then the node we observed is a binding
                binding_nodes.append(node)

    # for each binding
    for binding_node in binding_nodes:
        # we get the false bindings
        if binding_node.get_value() == False:
            #for each false binding we find the falsifying atoms
            get_false_atoms(falsifying_atoms, binding_node)

    return falsifying_atoms

def get_false_atoms(falsifying_atoms:list, child):
    unwanted_types_node = [MonitorTreeConjunctionNode,MonitorTreeDisjunctionNode,MonitorTreeNegateNode]
    #stop condition for the recursive algorithm
    if type(child) not in unwanted_types_node:
        # if the binding/child is in one of the unwanted types
        #we check if the child is false
        if child.get_value() == False:
            #if is_normal_atom(child ) or is_mixed_atom(child) then
            #parent is quantifier
            for t in unwanted_types_node:
                # if the parent is in one of the unwanted types
                if isinstance(child.get_parent(), t):
                    # then we check if child is already in falsifying_atoms
                    if child.get_subformula() not in falsifying_atoms:
                        atom_children=[]
                        #get children of the current atom
                        for atom_child in child.get_children():
                            atom_children.append(atom_child.get_value())
                        # we add the subformula of the child (which is an atom)
                        falsifying_atoms.append(tuple((child.get_subformula(),child.get_binding(),atom_children)))

                    return falsifying_atoms
                elif isinstance(child,MonitorTreeNode) and isinstance(child.get_parent(),MonitorTreeQuantifierNode):
                    # then we check if child is already in falsifying_atoms
                    if child.get_subformula() not in falsifying_atoms:
                        atom_children = []
                        # get children of the current atom
                        for atom_child in child.get_children():
                            atom_children.append(atom_child.get_value())
                        # we add the subformula of the child (which is an atom)
                        falsifying_atoms.append(tuple((child.get_subformula(), child.get_binding(), atom_children)))
                    return falsifying_atoms

    # if binding is a disjunction then the only way it is false is only if both children are false
    if isinstance(child,MonitorTreeDisjunctionNode) and child.get_value() == False:
        if child.get_children()[0].get_value() == False and child.get_children()[1].get_value() == False:
            get_false_atoms(falsifying_atoms, child.get_children()[0])
            get_false_atoms(falsifying_atoms, child.get_children()[1])

    # if binding is a conjuction then it is false if the children have the following truth values
    elif isinstance(child,MonitorTreeConjunctionNode) and child.get_value() == False:
        if child.get_children()[0].get_value() == False and child.get_children()[1].get_value() == False:
            get_false_atoms(falsifying_atoms, child.get_children()[0])
            get_false_atoms(falsifying_atoms, child.get_children()[1])
        elif child.get_children()[0].get_value() == False and child.get_children()[1].get_value() != False:
            get_false_atoms(falsifying_atoms, child.get_children()[0])
        elif child.get_children()[0].get_value() != False and child.get_children()[1].get_value() == False:
            get_false_atoms(falsifying_atoms, child.get_children()[1])

    #then binding/child is a complex formula so lets look at it's children
    elif not isinstance(child,MonitorTreeNegateNode):
        children= child.get_children()
        for child_node in children:
            get_false_atoms(falsifying_atoms, child_node)

    # elif isinstance(child.get_parent(),MonitorTreeQuantifierNode):


# parse the json file to get the PNR
@timer
def get_diagnosis(specification, trace:list, monitor):
    falsifying_atoms = get_false_atoms_per_false_bindings(monitor)
    atomic_constraints = specification.get_atoms()
    atomic_constraints_constants = []

    for atom in atomic_constraints:
        # get max time allowed by the timebetween atomic constraint
        constant = atom.get_constant()
        # save the constants of timebetween atomic constraints together with the atomic constaint id it got extracted from
        atomic_constraints_constants.append(tuple((atom, constant)))

    trace_functions = []
    diagnosis = []
    for false_atom in falsifying_atoms:
        # value = {i for i in false_atom[1] if false_atom[1][i] == false_atom[1][0]}
        if "<=" in str(false_atom[0]):
            case_symbol = 0
        elif "<" in str(false_atom[0]):
            case_symbol = 1

        # get time restriction from specification
        for atomic_constraint in atomic_constraints_constants:
            print("false",false_atom[0])
            if false_atom[0] == atomic_constraint[0]:
                # get time constant for each atomic constraint
                constant = atomic_constraint[1]
                # # get atom index
                # atom_index = int (atomic_constraint[0])

                #add events to list if the function are in between lhs and rhs
                add_event = False
                for event in trace:
                    if isinstance(atomic_constraint[0], TimeBetweenLessThanConstant):
                        # extract all functions related to one atom
                        if event.get("value") == false_atom[2][0]:
                            #get the timestamp of the lhs of the atom
                            lhs_value = event.get("time")
                            trace_functions.append(event)
                            add_event=True
                        elif event.get("value") == false_atom[2][1]:
                            #get the timestamp of the rhs of the atom
                            rhs_value = event.get("time")
                            #specification comparison its <=
                            if case_symbol ==0:
                                trace_functions.append(event)
                                add_event=False
                            #specification comparison its <
                            elif case_symbol ==1:
                                add_event=False


                        if add_event and event.get("type")=="function":
                            if event not in trace_functions:
                                trace_functions.append(event)

                    elif isinstance(atomic_constraint[0], DurationOfTransitionLessThanNumber):
                        lhs_value = event.get("time")
                        if event.get("type") == "function":
                            if event not in trace_functions:
                                trace_functions.append(event)


                print("\nFor atom = ", false_atom[0],"at binding =",false_atom[1], "we recorded the following function calls:\n")


                for trace_event in trace_functions:
                    #Find PNR
                    #condition: check if timestamp of an event happens after the allowed time
                    if trace_event.get("type") == "function":
                        if case_symbol == 0:
                            if trace_event.get('time') >= lhs_value+constant:
                                print("In atom =",trace_event.get('atom_index'),"we found the "+'\033[1m'+"point of no return:", trace_event.get('function_name'),'\033[0m',
                                      ", that was called at time =",trace_event.get('time'), "in line number", trace_event.get('line_number'),
                                      ". The call of", trace_event.get('function_name'), "happened after the time",constant,"was consumed.")
                                diagnosis.append(tuple((str(false_atom[0]),(false_atom[1]),len(trace_functions),trace_event.get('function_name'),trace_event.get('line_number'))))

                                # we select only the earliest concrete state that satisfies the condition
                                break
                            else:
                                print("For each atomic constraint we say that something happened between these functions that led to the time being consumed")
                                # print all the functions before the time was consumed
                                print("In atom =", trace_event.get('atom_index'), "the function",  trace_event.get('function_name'),
                                      "was called, at time =",  trace_event.get('time'), "in line number",  trace_event.get('line_number'))
                        elif case_symbol == 1:
                            if trace_event.get('time') > lhs_value+constant:
                                print("In atom =",trace_event.get('atom_index'),"we found the "+'\033[1m'+"point of no return:", trace_event.get('function_name'),'\033[0m',
                                      ", that was called at time =",trace_event.get('time'), "in line number", trace_event.get('line_number'),
                                      ". The call of", trace_event.get('function_name'), "happened after the time",constant,"was consumed.")

                                diagnosis.append(tuple((str(false_atom[0]),(false_atom[1]),len(trace_functions),trace_event.get('function_name'),trace_event.get('line_number'))))

                                # we select only the earliest concrete state that satisfies the condition
                                break

                            else:
                                print("For each atomic constraint we say that something happened between these functions that led to the time being consumed")
                                # print all the functions before the time was consumed
                                print("In atom =", trace_event.get('atom_index'), "the function",  trace_event.get('function_name'),
                                      "was called, at time =",  trace_event.get('time'), "in line number",  trace_event.get('line_number'))

                print("Diagnosis", diagnosis)


    return diagnosis

###################################################################################################
#       The functions below should only be called by code inserted during instrumentation.        #
###################################################################################################


def _start_monitoring_instr(specifications, online: bool, debug: bool = False,
                            project_path: typing.Union[str, pathlib.Path] = '') -> None:
    start_monitoring(specifications, online, auto_end=True, debug=debug, project_path=project_path)

def _wrap_function(function: typing.Callable, spec_id, atom_index, subatom_index, module_name, line_number, *args, **kwargs):
    logging.debug(f'_wrap_function({function=}, {spec_id=}, {atom_index=}, {subatom_index=}, {module_name=},'
                  f' {line_number=}, {args=}, {kwargs=})')
    timestamp_1 = time.time()
    return_value = function(*args, **kwargs)
    timestamp_2 = time.time()

    process_event({"type": "measurement",
                   "spec_id": spec_id,
                   "atom_index": atom_index,
                   "subatom_index": subatom_index,
                   "value": timestamp_2 - timestamp_1,
                   "time": timestamp_2 - _start_time,
                   "line_number": line_number,
                   "module_name": module_name})

    return return_value