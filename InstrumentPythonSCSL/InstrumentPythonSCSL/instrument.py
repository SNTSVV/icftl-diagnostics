"""
Module containing the logic for adding instrumentation code based on the results of static analysis
with respect to SCSL specifications.
"""

import ast
import logging
import os
import pathlib
import typing
from shutil import copyfile
import importlib

from SCFGPython import scfg_from_qualified_name
from SCSL.Analysis.analyse import Analyser
from SCSL.Specifications.constraints import TimeBetweenLessThanConstant,DurationOfTransitionLessThanNumber, TransitionVariable, ConcreteStateVariable, NextTransitionAfterTransition, NextConcreteStateAfterConcreteState,NextTransitionAfterConcreteState
from .callGraph import getPath,get_call_graph
from .CodeGenerators import InstrumentationLine

class Instrument:
    """
    Class used to invoke Analyser in order to perform static analysis,
    modify the ASTs of files to be instrumented and perform the final compilation.
    """

    def __init__(self, specifications, root_directory: str, online: bool, debug: bool = False):
        """
        Store the given list of specifications, along with the root directory of the project, and various flags.
        """
        self._debug = debug
        self._root_directory = root_directory
        self._online = online

        logging.info("Importing specifications to set self._specification")

        self._specifications = specifications

        # reset instrumented files
        print("Looking for existing instrumented files")
        self._reset_instrumented_files()

        # initialise empty map from function names to SCFGs
        self._function_name_to_scfg_map = {}

        # initialise empty map from module names to asts
        self._ast_modules = {}

        # initialise empty map from module names to lists of lines
        self._module_to_lines = {}

        # initialise empty map from spec IDs to instrumentation data
        self._spec_id_to_inst_data = {}

        # initialise empty list of modules
        self._all_modules = []

        # initialise empty list of functions
        self._all_functions = []

        #initialise a dictionary defining the after and before types of expressions
        self._expressions_types = {'before': ['ConcreteStateBeforeTransition'],
                                    'after': ['ConcreteStateAfterTransition', 'NextConcreteStateAfterConcreteState']
                                   }
        # iterate through specifications given
        for spec_id, specification in enumerate(self._specifications):
            print(specification)
            logging.info(f"Imported specification is\n{specification}")

            # get a list of all functions used in the specification
            spec_function_names = specification.get_function_names()
            self._all_functions += [function_name for function_name in spec_function_names
                                    if function_name not in self._all_functions]
            logging.info(f"All functions in specification: {self._all_functions}")
            # get the list of all modules that contain functions referred to in the specification
            spec_modules = self._derive_list_of_modules()
            self._all_modules += [module_name for module_name in spec_modules
                                    if module_name not in self._all_modules]
            logging.info(f"All modules in specification: {self._all_modules}")

            # get the ASTs and lines of each of these modules
            logging.info("Getting AST and source code line list for each module")
            # iterate through modules and construct ASTs for each
            for module in self._all_modules:
                # get asts
                if module not in self._ast_modules:
                    self._ast_modules[module] = self._get_ast_from_module(module)
                # get code lines
                if module not in self._module_to_lines:
                    self._module_to_lines[module] = self._get_lines_from_module(module)

            # get the scfg of each of these functions
            logging.info("Constructing SCFGs of each function")
            # get SCFG and AST for each function
            for function in self._all_functions:
                # check whether the function's SCFG has already been constructed as part of instrumentation
                # for another specification
                if function not in self._function_name_to_scfg_map:
                    logging.info(f"Calling construct_scfg_of_function on function '{function}'")
                    # get module from function
                    module = self._extract_module_name_from_function(function)
                    # get scfg for this function based on self._filename_to_ast_list[filename]
                    self._function_name_to_scfg_map[function] = scfg_from_qualified_name(function, self._root_directory)

                    # write to file
                    if self._debug:
                        self._function_name_to_scfg_map[function].write_to_file(f"{function.partition(':')[2]}.gv")

            # initialise the analyser class
            logging.info("Instantiating Analyser")
            self._analyser = Analyser(specification, self._function_name_to_scfg_map)

            # compute the instrumentation tree and the list of elements to instrument based on quantifiers
            logging.info("Determining statements in modules that must be instrumented")
            # compute instrumentation data
            quantifier_instrumentation_points, instrumentation_tree, \
            quantifier_expression_instrumentation_points = \
                self._analyser.compute_instrumentation_points()
            # update spec -> instrumentation data map
            self._spec_id_to_inst_data[spec_id] = {
                "quantifier_instrumentation_points": quantifier_instrumentation_points,
                "instrumentation_tree": instrumentation_tree,
                "quantifier_expression_instrumentation_points": quantifier_expression_instrumentation_points
            }

    def _derive_list_of_modules(self):
        """
        Derive the list of modules from self._all_functions.

        For now, just split by ., remove the last element of the list, and join back together.
        """
        # initialise empty list of modules
        all_modules = []
        # iterate through functions, getting the module name
        for function in self._all_functions:
            module_name = self._extract_module_name_from_function(function)
            # add to list
            if module_name not in all_modules:
                all_modules.append(module_name)

        return all_modules

    def _reset_instrumented_files(self):
        Instrument.reset_instrumented_files(self._root_directory)

    @staticmethod
    def reset_instrumented_files(self, root_directory: typing.Union[str, pathlib.Path] = '.'):
        """
        Find, restore, and delete all backup files found in root_directory
        """
        # iterate through modules
        for backup in pathlib.Path(root_directory).glob('**/*_uninstrumented_original*'):
            if backup.is_file():
                original_path = pathlib.Path(backup.parent, backup.name.replace('_uninstrumented_original', ''))
                print(f'Restoring {original_path} from {backup}')
                os.rename(backup, original_path)

    def _extract_module_name_from_function(self, function_name: str) -> str:
        """
        Given a function name, extract the module.
        """
        return function_name.rpartition(':')[0]

    def _extract_function_name_from_module(self, function_name: str) -> str:
        """
        Given a function name, extract the module.
        """
        return function_name.rpartition(':')[2]

    def _get_ast_from_module(self, module: str) -> ast.Module:
        """
        Given a module, get its filename, read in the code from it and construct the ASTs.
        """
        # reconstruct filepath
        path = pathlib.Path(self._root_directory, module)
        # read file
        with path.open() as h:
            code = h.read()
            return ast.parse(code)

    def _get_lines_from_module(self, module: str) -> list:
        """
        Given a module, gets its filename and read in the code lines from it.
        """
        # reconstruct filepath
        path = pathlib.Path(self._root_directory, module)
        # read file
        with path.open() as h:
            # get trippes lines
            lines = list(map(lambda line: line.rstrip(), h.readlines()))

        return lines

    def insert_instruments(self):
        """
        Traverse the instrumentation tree structure and, for each symbolic state,
        place an instrument at an appropriate position around the AST provided by the symbolic state.

        We do this for each specification.
        """
        logging.info("Inserting instruments into source code")
        # initialise list of instrumentation lines
        instrumentation_lines: list[InstrumentationLine] = []
        # iterate over specifications
        for spec_id, specification in enumerate(self._specifications):
            atomic_constraints = specification.get_atoms()

            atomic_constraints_functions = []
            atomic_constraints_symbols = []
            duration_functions=[]
            atomic_constraints_during_function = []
            classified_expressions =[]

            for i in range(len(atomic_constraints)):
                #check what type of atomic constraint we have
                if isinstance(atomic_constraints[i],TimeBetweenLessThanConstant):
                    lhs_expression_timeBetween = atomic_constraints[i].get_lhs_expression()
                    rhs_expression_timeBetween = atomic_constraints[i].get_rhs_expression()
                    # checking if lhs expression in the timeBetween is a quantifier
                    if isinstance(lhs_expression_timeBetween,TransitionVariable) or isinstance(lhs_expression_timeBetween,ConcreteStateVariable):
                        quantifier_id = lhs_expression_timeBetween.get_base_variable().get_name()
                        # for all quantifiers in the specification check which one coincides with the quantifier in the atom
                        for quantifier in specification.get_quantifiers():
                            if quantifier_id == quantifier.get_id():
                                if 'changes' in str(type(quantifier.get_predicate())):
                                    during_function = quantifier.get_predicate().get_during_function()
                                    # in case we have a quantifier that captures the changes of a variable we extract the name of the during function of that quantifier
                                    function_name_lhs = quantifier.get_predicate().get_during_function()
                                    # get name of variable in changes of the quantifier
                                    predicate_function =  quantifier.get_predicate().get_program_variable()
                                elif 'calls' in str(type(quantifier.get_predicate())):
                                    # in case we have a quantifier that captures the call of a function we extract the name of that function
                                    predicate_function = quantifier.get_predicate().get_function_name()
                                    during_function = quantifier.get_predicate().get_during_function()
                                    during_module = self._extract_module_name_from_function(during_function)
                                    # get the function name together with the module
                                    function_name_lhs = during_module + ":" + predicate_function
                                else:
                                    print("there is no 'changes' or 'calls' in str(type(quantifier.get_predicate()))")

                    else:
                        # find the expression in the specification
                        expression = lhs_expression_timeBetween.get_transition()

                        # from the atom get the function within calls()
                        atom_expression = expression.get_predicate().get_function_name()
                        # from the atom get the function in during()
                        during_function = expression.get_predicate().get_during_function()
                        # extract module of the during function
                        during_module = self._extract_module_name_from_function(during_function)
                        # add the extracted module to the name of the function in calls()
                        function_name_lhs = during_module + ":" + atom_expression

                        # print("transition in before:", atomic_constraints[i].get_expression(1).get_transition())
                        # print("predicate in transition before:", atomic_constraints[i].get_expression(1).get_transition().get_predicate())
                        # print("function name used in predicate",
                        #       atomic_constraints[i].get_expression(1).get_transition().get_predicate().get_during_function())

                        # get name of variable in calls of the expression
                        predicate_function = atom_expression
                    # make a list of tuples containing function names and their "during" function
                    atomic_constraints_during_function.append(tuple((i, function_name_lhs, during_function)))
                    # we record the symbols used in teh atom, we have the atom id we are considering,
                    # which expression we have lhs and the name of the variable
                    atomic_constraints_symbols.append(tuple((i,"lhs",predicate_function)))
                    # checking if rhs expression in the timeBetween is a quantifier
                    if isinstance(rhs_expression_timeBetween,TransitionVariable) or isinstance(rhs_expression_timeBetween,ConcreteStateVariable):
                        quantifier_id = rhs_expression_timeBetween.get_base_variable().get_name()

                        #for all quantifiers in the specification check which one coincides with the quantifier in the atom
                        for quantifier in specification.get_quantifiers():
                            if quantifier_id == quantifier.get_id():
                                if 'changes' in str(type(quantifier.get_predicate())):
                                    # get name of variable in changes of the quantifier
                                    predicate_function = quantifier.get_predicate().get_program_variable()
                                    during_function = quantifier.get_predicate().get_during_function()
                                    # in case we have a quantifier that captures the changes of a variable we extract the name of the during function of that quantifier
                                    function_name_rhs = quantifier.get_predicate().get_during_function()
                                elif 'calls' in str(type(quantifier.get_predicate())):
                                    # in case we have a quantifier that captures the call of a function we extract the name of that function
                                    predicate_function = quantifier.get_predicate().get_function_name()
                                    during_function = quantifier.get_predicate().get_during_function()
                                    during_module = self._extract_module_name_from_function(during_function)
                                    # get the function name together with the module
                                    function_name_rhs = during_module + ":" + predicate_function
                                else:
                                    print("there is no 'changes' or 'calls' in type(quantifier.get_predicate())")

                    elif isinstance(rhs_expression_timeBetween,NextConcreteStateAfterConcreteState):
                        predicate_function = rhs_expression_timeBetween.get_predicate().get_program_variable()
                        during_function = rhs_expression_timeBetween.get_predicate().get_during_function()

                        function_name_rhs = during_function

                        # function_name_rhs = quantifier.get_predicate().get_during_function()
                    elif isinstance(rhs_expression_timeBetween,NextTransitionAfterConcreteState):
                        predicate_function = rhs_expression_timeBetween.get_predicate().get_function_name()
                        during_function = rhs_expression_timeBetween.get_predicate().get_during_function()
                        function_name_rhs = during_function

                        # function_name_rhs = quantifier.get_predicate().get_during_function()
                    else:
                        # find the expression in the specification
                        expression = rhs_expression_timeBetween.get_transition()

                        # from the atom get the function within calls()
                        atom_expression = expression.get_predicate().get_function_name()
                        # from the atom get the function in during()
                        during_function = expression.get_predicate().get_during_function()
                        # extract module of the during function
                        during_module = self._extract_module_name_from_function(during_function)
                        function_name_rhs = during_function

                        # add the extracted module to the name of the function in calls()
                        # function_name_rhs = during_module + ":" + atom_expression
                        # get name of variable in calls of the expression
                        predicate_function = atom_expression

                    # make a list of tuples containing function names and their "during" function
                    atomic_constraints_during_function.append(tuple((i,function_name_rhs, during_function)))
                    #make a list of tuples of functions of an atomic constraint, the order doesnt matter as we consider undirected call graph
                    atomic_constraints_functions.append(tuple((function_name_lhs,function_name_rhs,i)))
                    # we record the symbols used in teh atom, we have the atom id we are considering,
                    # which expression we have rhs and the name of the variable
                    atomic_constraints_symbols.append(tuple((i,"rhs",predicate_function)))

                    # keep track of what type of expressions were used (does the expression contain before or after)
                    for expression_type in self._expressions_types:
                        for code_generator_class in self._expressions_types[expression_type]:
                            for index in range(2):
                                if code_generator_class in str(type(atomic_constraints[i].get_expression(index))):
                                    #check if current atomic constraint coincides with rhs or lhs
                                    if atomic_constraints[i].get_expression(index)==rhs_expression_timeBetween:
                                        classified_expressions.append(tuple((expression_type,function_name_rhs)))
                                    else:
                                        classified_expressions.append(tuple((expression_type,function_name_lhs)))

                elif isinstance(atomic_constraints[i],DurationOfTransitionLessThanNumber):
                    if isinstance(atomic_constraints[i].get_expression(0).get_transition_expression(), NextTransitionAfterTransition):
                        # find the expression in the specification
                        expression = atomic_constraints[i].get_expression(0).get_transition_expression()

                        # from the atom get the function within calls()
                        during_call_function = expression.get_predicate().get_function_name()
                        # from the atom get the function in during()
                        during_function = expression.get_predicate().get_during_function()
                        # extract module of the during function
                        during_module = self._extract_module_name_from_function(during_function)
                        # add the extracted module to the name of the function in calls()
                        during_call_function_module = during_module + ":" + during_call_function
                    # expressio in duration atom is a quantifier
                    elif isinstance(atomic_constraints[i].get_expression(0).get_transition_expression(),TransitionVariable):
                        expression = atomic_constraints[i].get_expression(
                            0).get_base_variable().get_name()

                        for quantifier in specification.get_quantifiers():
                            if expression == quantifier.get_id():
                                during_function = quantifier.get_predicate().get_during_function()
                                during_module = self._extract_module_name_from_function(during_function)
                                during_call_function = quantifier.get_predicate().get_function_name()

                                during_call_function_module = during_module + ":" + during_call_function

                    # make a list of tuples of functions of an atomic constraint, the order doesnt matter as we consider undirected call graph
                    duration_functions.append(tuple((during_call_function_module,during_function)))


            logging.info(f"atoms = {atomic_constraints}")
            # get the instrumentation data for this specification
            instrumentation_data = self._spec_id_to_inst_data[spec_id]
            quantifier_instrumentation_points = instrumentation_data["quantifier_instrumentation_points"]
            quantifier_expression_instrumentation_points = \
                instrumentation_data["quantifier_expression_instrumentation_points"]
            instrumentation_tree = instrumentation_data["instrumentation_tree"]
            # traverse self._quantifier_instrumentation_points in order to insert instrumentation points for quantifiers
            logging.info("Inserting instruments for quantifiers")
            for variable in quantifier_instrumentation_points:
                for sym_state in quantifier_instrumentation_points[variable]:
                    # get the line number at which to insert the code
                    line_number = sym_state.line_number
                    # get the index in the list of lines
                    line_index = line_number - 1
                    # get the function inside which symbolic_state is found
                    function = self._analyser.get_scfg_searcher().get_function_name_of_symbolic_state(sym_state)
                    # derive the module name from the function
                    module = self._extract_module_name_from_function(function)
                    # generate the code
                    quantifier_instrument_code = self._generate_quantifier_instrument_code(
                        spec_id,
                        module,
                        line_index,
                        variable
                    )
                    # append
                    instrumentation_lines.append(
                        InstrumentationLine(module, line_index, quantifier_instrument_code, "trigger"))

            # process the instrumentation points for expressions found in quantifiers
            for quantifier_id in quantifier_expression_instrumentation_points:
                for sub_expression_index in quantifier_expression_instrumentation_points[quantifier_id]:
                    logging.info(f"sub expression index = {sub_expression_index}")
                    # iterate through instrumentation points
                    for symbolic_state in \
                            quantifier_expression_instrumentation_points[quantifier_id][sub_expression_index]:
                        # get the line number at which to insert the code
                        line_number = symbolic_state.line_number
                        # get the index in the list of lines
                        line_index = line_number - 1
                        # get the function inside which symbolic_state is found
                        function = self._analyser.get_scfg_searcher().get_function_name_of_symbolic_state(
                            symbolic_state)
                        # derive the module name from the function
                        module = self._extract_module_name_from_function(function)
                        quantifier_expression_instrument_code = self._generate_quantifier_expression_instrument_code(
                            spec_id,
                            module,
                            line_index,
                            quantifier_id,
                            sub_expression_index
                        )
                        # append
                        instrumentation_lines.append(
                            InstrumentationLine(module, line_index, quantifier_expression_instrument_code, "quantifier-measurement"))

            # traverse self._instrumentation_tree in order to insert instrumentation points for constraints
            logging.info("Inserting instruments for constraints")
            for atom_index in instrumentation_tree:
                # get the atom at atom_index
                relevant_atom = atomic_constraints[atom_index]
                # iterate through the maps from atom sub indices to lists of symbolic states
                for subatom_index in instrumentation_tree[atom_index]:
                    # get the subatom at subatom_index
                    relevant_subatom = relevant_atom.get_expression(subatom_index)
                    # iterate through symbolic states
                    for symbolic_state in instrumentation_tree[atom_index][subatom_index]:
                        # get the line number at which to insert the code
                        line_number = symbolic_state.line_number
                        # get the index in the list of lines
                        line_index = line_number - 1
                        # get the function inside which symbolic_state is found
                        function = self._analyser.get_scfg_searcher().get_function_name_of_symbolic_state(
                            symbolic_state)
                        # derive the module name from the function
                        module = self._extract_module_name_from_function(function)
                        # generate and append the instrument code
                        instrumentation_lines += self._generate_constraint_instrument_code(
                            spec_id,
                            module,
                            line_index,
                            atom_index,
                            subatom_index,
                            relevant_subatom
                        )


                #add instrumentation for functions

            # Method2: Less Instrumentation: record execution start timestamp for each function in the path
            logging.info("Inserting instruments for timeBetween functions")
            modules_atomic_constraints=[]
            #for each pair of quantifier and expression in the specification we do:
            for atom in atomic_constraints_functions:
                #extract modules of the atom we are considering
                #extract the module of the quantifier in the atom
                modules_atomic_constraints.append(os.path.join(self._root_directory , self._extract_module_name_from_function(atom[0])))
                #insert fault in first module
                # self.insert_fault(self._extract_module_name_from_function(atom[0]))
                # extract the module of the expression in the atom
                modules_atomic_constraints.append(os.path.join(self._root_directory , self._extract_module_name_from_function(atom[1])))

                atoms =[atom[0],atom[1]]
                atom_functions = []
                for atom_name in atoms:
                    for classified_expression in classified_expressions:
                        if atom_name == classified_expression[1]:

                            if classified_expression[0] == 'before':
                                function_processed = atom_name.split(':')[1]
                                atom_functions.append(tuple((atom[2],"before",atom_name,function_processed)))
                            elif classified_expression[0] =="after":
                                function_processed = atom_name.split(':')[1]
                                atom_functions.append(tuple((atom[2],"after",atom_name,function_processed)))

                #get all function call between the 2 functions of an atom
                graph_function = getPath(modules_atomic_constraints,atom[0],atom[1])
                graph_function.append(atom[0])
                # print("Call graph path in time between atom",graph_function)

                func_atom = []
                #call function to get all function calls between lhs and rhs using static analysis
                self.find_called_atom_functions(atom[2],
                                           atoms, atom_functions, atomic_constraints_symbols, atomic_constraints_during_function, func_atom)

                unique_called_functions = []
                list_fu = []
                #combine list obtained from call graph path and the list from static analysis
                graph_function.extend(func_atom)
                for function in graph_function:
                    try:
                        list_fu.extend(self.find_called_functions(list_fu,function))
                    # except FileNotFoundError:
                    #     logging.info(f"{function} may not be a file")
                    # except BaseException:
                    #     logging.info("BaseException encountered",function)
                    except Exception:
                        pass

                # traverse for all elements in order to get unique functions only
                for called_function in list_fu:
                    # check if exists in unique_list or not
                    if called_function not in unique_called_functions:
                        unique_called_functions.append(called_function)

                # print("unique f",unique_called_functions)

                atom_index = atomic_constraints_functions.index(atom)

            for function in unique_called_functions:
                if "(global)" not in function:
                    try:
                        # get scfg for this function based on self._filename_to_ast_list[filename]
                        self._function_name_to_scfg_map[function] = scfg_from_qualified_name(function,
                                                                                             self._root_directory)
                    except:
                        # if we can not build teh scfg of a function that means that its not availble in the module (could be library etc.)
                        continue
                    # get first state in the scfg of the function f
                    symbolic_state_entry = \
                        self._function_name_to_scfg_map[function].entry_point.next_states[0]

                    # derive the module name from the function
                    module = self._extract_module_name_from_function(function)

                    # # code for inserting instrumentation line at the end of the function
                    for symbolic_state in self._function_name_to_scfg_map[function].symbolic_states:
                        for i in range(len(symbolic_state.next_states)):
                            if symbolic_state.next_states[i].statement_type.label == "ExitProcedure":
                                line_number = symbolic_state.end_line_number
                                line_index = line_number
                                #trying to detect last line in function in corner case of proj: split_folder_into_subfolders
                                if isinstance(line_number,type(None)):
                                    for i in range(len(self._function_name_to_scfg_map[function].symbolic_states)):
                                        if self._function_name_to_scfg_map[function].symbolic_states[i] == symbolic_state:
                                            prev = self._function_name_to_scfg_map[function].symbolic_states[i +1]
                                            line_index = prev.line_number
                                # GEnerate an element index such that we have time function (tf) + the atom index and line number
                                element_index = "tb_" + str(atom_index) + '_' + str(line_number)
                                # generate the instrument code
                                instrumentation_lines += self._generate_function_instrument_code_after(
                                    spec_id,
                                    module,
                                    line_index,
                                    element_index,
                                    function,
                                    atom_index
                                )

                    line_number = symbolic_state_entry.line_number
                    line_index = line_number - 1
                    # GEnerate an element index such that we have time function (tf) + the atom index and line number
                    element_index = "tb_" + str(atom_index) + '_' + str(line_number)

                    # generate the instrument code
                    instrumentation_lines += self._generate_function_instrument_code(
                        spec_id,
                        module,
                        line_index,
                        element_index,
                        function,
                        atom_index
                    )



                    #get end execution time for atom that has keyword "after"
                    for classified_expression in classified_expressions:
                        if function == classified_expression[1]:
                            if classified_expression[0] == 'after':
                                #if we have an expression that checks "after"  a function happenns we have to determine the callee of this function
                                for i in range(atomic_constraints_during_function.__len__()):
                                    if function == atomic_constraints_during_function[i][0]:
                                        # get scfg of the callee function for this function based on self._filename_to_ast_list[filename]
                                        self._function_name_to_scfg_map[atomic_constraints_during_function[i][1]] = scfg_from_qualified_name(atomic_constraints_during_function[i][1],
                                                                                                             self._root_directory)
                                        #determine the symbolic state where the function was called
                                        for symbolic_state in self._function_name_to_scfg_map[atomic_constraints_during_function[i][1]].symbolic_states:
                                            for symbol_name in symbolic_state.all_symbols():
                                                if symbol_name == function.split(":")[1]:
                                                    line_number = symbolic_state.line_number
                                                    line_index = line_number

                                                    # GEnerate an element index such that we have time function (tf) + the atom index and line number
                                                    element_index = "tb_" + str(atom_index) + '_' + str(line_number)

                                                    # generate the instrument code for "after" the function call site
                                                    instrumentation_lines += self._generate_function_instrument_code(
                                                        spec_id,
                                                        module,
                                                        line_index,
                                                        element_index,
                                                        function,
                                                        atom_index
                                                    )
                    # generate the instrument code for sleep function call site
                    # if "sleep_function" in function:
                    #     #take into consideration the inserted lines of def of sleep function
                    #     line_number = self._fault_injection_line +5
                    #     line_index = self._fault_injection_line +5
                    #
                    #     # GEnerate an element index such that we have time function (tf) + the atom index and line number
                    #     element_index = "tb_sl_" + str(atom_index) + '_' + str(line_number)
                    #
                    #     instrumentation_lines += self._generate_function_instrument_code(
                    #         spec_id,
                    #         module,
                    #         line_index,
                    #         element_index,
                    #         function,
                    #         atom_index
                    #     )

            logging.info("Inserting instruments for duration functions")
            for i in range(duration_functions.__len__()):
                atom = duration_functions[i][0]
                #initialise a list of called functions starting with our atom
                called_functions = [atom]
                #call recursive function "find called functions" for getting all nested functions
                called_functions = self.find_called_functions(called_functions, atom)
                unique_called_functions =[]
                # traverse for all elements in order to get unique functions only
                for called_function in called_functions:
                    # check if exists in unique_list or not
                    if called_function not in unique_called_functions:
                        unique_called_functions.append(called_function)

                # print("Call graph path in duration atom", unique_called_functions)

                # the atom index becomes the index of the tuple
                atom_index = i

                #for each function in unique called functions generate instruments
                for function in unique_called_functions:
                    # get scfg for this function based on self._filename_to_ast_list[filename]
                    self._function_name_to_scfg_map[function] = scfg_from_qualified_name(function,
                                                                                         self._root_directory)
                    # get first state in the scfg of the function f
                    symbolic_state = self._function_name_to_scfg_map[function].entry_point.next_states[0]
                    line_number = symbolic_state.line_number
                    line_index = line_number - 1
                    # GEnerate an element index such that we have time function (tf) + the atom index and line number
                    element_index = "dur_" + str(atom_index) + '_' + str(line_number)
                    # derive the module name from the function
                    module = self._extract_module_name_from_function(function)
                    # generate the instrument code
                    instrumentation_lines += self._generate_function_instrument_code(
                        spec_id,
                        module,
                        line_index,
                        element_index,
                        function,
                        atom_index
                    )

                #generate instrument for the execution time end of the atom
                # get scfg for this function based on self._filename_to_ast_list[filename]
                self._function_name_to_scfg_map[duration_functions[i][1]] = scfg_from_qualified_name(duration_functions[i][1],
                                                                                     self._root_directory)
                # determine the symbolic state where the function was called
                for symbolic_state in self._function_name_to_scfg_map[
                    duration_functions[i][1]].symbolic_states:
                    for symbol_name in symbolic_state.all_symbols():
                        if symbol_name == atom.split(":")[1]:
                            line_number = symbolic_state.line_number
                            line_index = line_number
                            # GEnerate an element index such that we have time function (tf) + the atom index and line number
                            element_index = "dur_" + str(atom_index) + '_' + str(line_number)
                            # derive the module name from the function
                            module = self._extract_module_name_from_function(atom)
                            # generate the instrument code for "after" the function call site
                            instrumentation_lines += self._generate_function_instrument_code(
                                spec_id,
                                module,
                                line_index,
                                element_index,
                                atom,
                                atom_index
                            )


        # sort instrument code by line index descending (that way we don't have to recompute line numbers)
        # we rely on this sorting being stable - otherwise some variables defined by instruments could be undefined
        # if they're used before their definition
        # get list of instrumentation lines
        # we sort with respect to priority
        # a trigger for a quantifier must always be the first in a block of instrumentation code
        # because, otherwise, some measurements may be received before there are nodes to hold them
        priorities = ["trigger", "end-timestamp", "measurement", "quantifier-measurement", "before-measurement",
                      "start-timestamp","function"]
        instrumentation_lines = list(reversed(sorted(
            instrumentation_lines,
            key=lambda line: (line.line_number, priorities.index(line.priority_key))
        )))

        # delete lines as needed
        # self._module_to_lines = {
        #     module_name: [
        #         line for i, line in enumerate(self._module_to_lines[module_name])
        #         if not any(instr_line.lines_to_delete is not None
        #                    and i + 1 in instr_line.lines_to_delete
        #                    and instr_line.module_name == module_name
        #                    for instr_line in instrumentation_lines)
        #     ] for module_name in self._module_to_lines
        # }

        # insert the instruments
        for line in instrumentation_lines:
            # get the module inside which this instrument should be placed
            module_name = line.module_name

            if module_name not in self._all_modules:
                self._all_modules += [module_name]
                # otherwise for newly function that we discovered by analysing the code/call graph
                # we need to build the ast of the new module
                self._ast_modules[module_name] = self._get_ast_from_module(module_name)
                # get the lines from the new module
                self._module_to_lines[module_name] = self._get_lines_from_module(module_name)

            if line.lines_to_delete is not None:
                for i in line.lines_to_delete:
                    self._module_to_lines[module_name][i - 1] = ''

            # insert instrument
            self._module_to_lines[module_name].insert(line.line_number, line.code)


        # now, insert additional imports
        imports = [
            'import time as scsl_monitoring_time',
            'import compiled_spec',
            'import SCSL.Monitoring',
            f'SCSL.Monitoring.monitoring._start_monitoring_instr(compiled_spec.specifications, ' # Continues on same line
            f'online={self._online}, debug={self._debug}, project_path="{self._root_directory}")'
        ]

        # for each module, insert these lines at the beginning
        for module_name in self._module_to_lines:
            # insert lines (reversed, since each time we insert at the beginning)
            for line in reversed(imports):
                self._module_to_lines[module_name].insert(0, line)

    #recursive function that finds all called symbolic states in a scfg
    def find_called_functions(self, called_functions:list, function:str):
        try:
            #generate scfg for 'function'
            self._function_name_to_scfg_map[function] = scfg_from_qualified_name(function,
                                                                             self._root_directory)
            #extract module from function
            module = self._extract_module_name_from_function(function)
        except:
            module = self._extract_module_name_from_function(function)

        module_path = []
        module_path.append(str(self._get_original_path_from_module(module)))
        module_graph = get_call_graph(module_path)

        # get program path (so that we can search in that directory)
        path_to_directory = self._root_directory
        for n in range(len(str(module_path[0]))):
            if "/" == str(module_path[0])[-n - 1]:
                # get directory of the program
                path_to_directory = str(module_path[0])[:-n - 1]
                break

        symbols_list_function_module_called = ""
        #recurse over the symbolic states
        for symbolic_state in self._function_name_to_scfg_map[function].symbolic_states:
            # if duration/timebetween function body has functions calls we add them to the list of called functions
            if len(symbolic_state.called_symbols()) != 0:
                # symbols_list = list(symbolic_state.all_symbols())
                #exception: skip for loops (with range)
                if "range" not in symbolic_state.all_symbols():
                    for called_symbol in symbolic_state.called_symbols():
                        for node in module_graph:
                            if called_symbol == node.split(":")[1]:
                                symbolic_state_found = 1
                                break
                            else:
                                symbolic_state_found = 0
                        #if we didnt find the called symbol (function) defined in the same module
                        if symbolic_state_found == 0:
                            # we search if it has "." which mean that it could be defined in another file
                            if "." in called_symbol:
                                file_symbolic_state_called = called_symbol.rsplit(".")[0]
                                func_symbolic_state_called = called_symbol.rsplit(".")[1]
                                module_sym_state = file_symbolic_state_called + ".py"

                                # we search if there is a file with the name of the function
                                # if not then we say the function is in the same module as lhs
                                if module_sym_state not in os.listdir(path_to_directory):
                                    module_sym_state = module
                                else:
                                    # we iterate over files in the directory
                                    for file in os.listdir(path_to_directory):
                                        # for each python file we find
                                        if file.endswith(".py"):
                                            # we check if we can find a match to the first assumption
                                            if module_sym_state == file:
                                                module_sym_state = file
                                #before called symbols was func_symbolic_state_called
                                symbols_list_function_module_called = module_sym_state + ":" + called_symbol

                        elif symbolic_state_found == 1:
                            symbols_list_function_module_called = str(module) + ":" + \
                                                                  called_symbol

                    if 'print' not in symbols_list_function_module_called and symbols_list_function_module_called != "":
                        #add function to the list of called functions
                        called_functions.append(symbols_list_function_module_called)
                        #recursively call the find_called_functions on each function we find
                        try:
                            self.find_called_functions(called_functions, symbols_list_function_module_called)
                        except FileNotFoundError:
                            logging.info(f"{symbols_list_function_module_called} may not be a function")
                        except BaseException:
                            logging.info("BaseException encountered")

        return called_functions

    # recursive function that finds all called symbolic states in a scfg for a given atom
    #function that does statoic analysis to get the necessary function calls from the lhs and rhs function in the atom
    # it gets the interval in lhs and rhs were we look for function calls.
    def find_called_atom_functions(self, atom_index, expression_functions: list, atom_functions, atomic_constraints_symbols,atomic_constraints_during_function,func_atom:list):
        lhs=expression_functions[0]
        rhs=expression_functions[1]

        # atomic_constraints_during_function contains function name and its during function
        for during_function in atomic_constraints_during_function:
            if during_function[0] == atom_functions[0][0]:
                # get during function of the atom
                #NEW could be that during functions coincide for lhs and rhs
                if lhs == during_function[1]:
                    lhs_during_function=during_function[2]
                if rhs == during_function[1]:
                    rhs_during_function=during_function[2]

        # get the names of atom triggers, in order to later find their line number
        for i in range(len(atomic_constraints_symbols)):
            if atomic_constraints_symbols[i][0] == atom_index and atomic_constraints_symbols[i][1] =="lhs":
                lhs_trigger = atomic_constraints_symbols[i][2]
            elif atomic_constraints_symbols[i][0] == atom_index and atomic_constraints_symbols[i][1] =="rhs":
                rhs_trigger = atomic_constraints_symbols[i][2]

        # generate scfg for lhs atom
        self._function_name_to_scfg_map[lhs_during_function] = scfg_from_qualified_name(lhs_during_function,
                                                                             self._root_directory)
        # generate scfg for rhs atom
        # self._function_name_to_scfg_map[rhs] = scfg_from_qualified_name(rhs,
        #                                                                      self._root_directory)
        self._function_name_to_scfg_map[rhs_during_function] = scfg_from_qualified_name(rhs_during_function,
                                                                        self._root_directory)
        # extract module from lhs expression
        module_lhs = self._extract_module_name_from_function(lhs_during_function)
        # extract module from rhs expression
        module_rhs = self._extract_module_name_from_function(rhs)

        rhs_trigger_list=[]
        # recurse over the symbolic states in rhs scfg to find rhs_trigger line number
        for symbolic_state in self._function_name_to_scfg_map[rhs_during_function].symbolic_states:
            for symbolic_state_name in symbolic_state.all_symbols():
                # if function name equal to symbolic state record all the function call afterwards

                # if rhs_trigger.split(".")[1] in symbolic_state_name:
                if rhs_trigger in symbolic_state_name:
                    rhs_trigger_list.append(symbolic_state.line_number)

        rhs_trigger_line_number = min(rhs_trigger_list)

        atom_constraint_lhs_line_number = []
        atom_constraint_rhs_line_number = []
        functions_connected_to_rhs =[]
        # recurse over the symbolic states to find connection to rhs from lhs during function
        for symbolic_state in self._function_name_to_scfg_map[lhs_during_function].symbolic_states:
            # if symbolic state not a set() () empty
            if len(symbolic_state.all_symbols()) !=0:
                symbols_list = list(symbolic_state.all_symbols())

                #get program path (so that we can search in that directory)
                lhs_path = self._get_original_path_from_module(lhs_during_function)
                path_to_directory = self._root_directory
                for n in range(len(str(lhs_path))):
                    if "/" == str(lhs_path)[-n-1]:
                        # get directory of the program
                        path_to_directory = str(lhs_path)[:-n-1]
                        break

                symbols_list_function_module_called = ""
                if symbolic_state.called_symbols() != 0:
                    for symbolic_state_called in symbolic_state.called_symbols():
                        #in case we have a call to an external file we extract the file name and the function that was called from that file
                        file_symbolic_state_called = func_symbolic_state_called = symbolic_state_called

                        # if a call to a function is of type "file.func1()"
                        if "." in symbolic_state_called:
                            file_symbolic_state_called = symbolic_state_called.rsplit(".")[0]
                            func_symbolic_state_called  = symbolic_state_called.rsplit(".")[1]
                            module_sym_state = file_symbolic_state_called + ".py"
                        else:
                            module_sym_state = module_lhs


                        #we search if there is a file with the name of the function
                        # if not then we say the function is in the same module as lhs
                        if module_sym_state not in os.listdir(path_to_directory):
                            module_sym_state = module_lhs
                        else:
                            # we iterate over files in the directory
                            for file in os.listdir(path_to_directory):
                                # for each python file we find
                                if file.endswith(".py"):
                                    # we check if we can find a match to the first assumption
                                    if module_sym_state == file:
                                        module_sym_state = file
                        symbols_list_function_module_called = module_sym_state +":"+func_symbolic_state_called

                if lhs_trigger in symbols_list:
                    # detect the line number of the called atom (if lhs is in the same function )
                    if symbolic_state.line_number != None:
                        atom_constraint_lhs_line_number.append(symbolic_state.line_number)
                # second try to find the line number of a function that can reach rhs
                # if rhs is in the same function as lhs
                if lhs_during_function == rhs_during_function:
                    if rhs_trigger in symbols_list:
                        if symbolic_state.line_number != None:
                            atom_constraint_rhs_line_number.append(symbolic_state.line_number)
                # if symbolic state is the same as the rhs during function
                elif symbols_list_function_module_called != "" and symbols_list_function_module_called == rhs_during_function:
                    if symbolic_state.line_number != None:
                        atom_constraint_rhs_line_number.append(symbolic_state.line_number)
                # if symbolic state is a function
                # try to find rhs connection to lhs but calling a recursive function on the symbolic states
                # try to find rhs_trigger parent that connect to lhs
                elif len(symbolic_state.called_symbols()) != 0:
                    # functions_connected_to_rhs.append(symbolic_state.line_number)
                    functions_connected_to_rhs1 = self.find_rhs_parent(symbols_list_function_module_called,
                                                                       rhs_during_function,
                                                                       functions_connected_to_rhs,
                                                                       symbolic_state.line_number, module_lhs)

                    #if there is a function that can connect to rhs in lhs function then we append the min to the atom_constraint_rhs_line_number
                    if functions_connected_to_rhs1 != None:
                        atom_constraint_rhs_line_number.append(min(functions_connected_to_rhs1))

                #append the last line in lhs function in order to include all functions that were called in lhs
                if atom_constraint_rhs_line_number == [] and symbolic_state.next_states != [] :
                    for i in range(len(symbolic_state.next_states)):
                        if symbolic_state.next_states[i].statement_type.label == "ExitProcedure":
                            atom_constraint_rhs_line_number.append(symbolic_state.end_line_number)

        # lhs func: these are line numbers of the trigger in lhs and the parent of rhs
        #we need these to find the interval in which we search the function calls in lhs
        lhs_line_number_lowest = min(atom_constraint_lhs_line_number)
        rhs_parent_line_number_lowest = min(atom_constraint_rhs_line_number)
        for symbolic_state in self._function_name_to_scfg_map[lhs_during_function].symbolic_states:
            for i in range(len(atomic_constraints_symbols)):
                # identify if the atom we analyze is on rhs or lhs  by checking if atom index is the same
                if atomic_constraints_symbols[i][0] == atom_functions[0][0]:
                    if atomic_constraints_symbols[i][1] =='lhs':
                        # we need to choose all the sym states that happen after including the sym state we analyse
                        if atom_functions[0][1] =='before':
                            try:
                                comparison_lhs = symbolic_state.line_number >= lhs_line_number_lowest
                            except:
                                comparison_lhs = False
                        # we need to choose all the sym states that happen after including the sym state we analyse
                        elif atom_functions[0][1] =='after':
                            try:
                                comparison_lhs = symbolic_state.line_number > lhs_line_number_lowest
                            except:
                                comparison_lhs = False

            if comparison_lhs and symbolic_state.called_symbols() != 0:
                for called_symbol in symbolic_state.called_symbols():
                    # generate the name of the function together with its module
                    last_called_function = self.find_module_symbolic_state(module_lhs,called_symbol)

                    # if the symbolic state line number is not rhs line number
                    if 'print' not in last_called_function:
                        # and list(symbolic_state.all_symbols())[0] != "sleep_function":
                        if symbolic_state.line_number < rhs_parent_line_number_lowest:
                            # append the function to the list of functions
                            func_atom.append(last_called_function)
                            # recursively call the find_called_functions on each function we find
                            try:
                                self.find_called_functions(func_atom, last_called_function)
                            except FileNotFoundError:
                                logging.info(f"{last_called_function} may not be a function")
                            except BaseException:
                                logging.info("BaseException encountered")


                        elif symbolic_state.line_number == rhs_parent_line_number_lowest:
                            func_atom.append(last_called_function)
                            # recursively call the find_called_functions on each function we find
                            try:
                                self.find_called_functions(func_atom, last_called_function)
                            except FileNotFoundError:
                                logging.info(f"{last_called_function} may not be a function")
                            except BaseException:
                                logging.info("BaseException encountered")

        for symbolic_state in self._function_name_to_scfg_map[rhs_during_function].symbolic_states:
            for i in range(len(atomic_constraints_symbols)):
                # identify if the atom we analyze is on rhs or lhs by checking if atom index is the same
                if atomic_constraints_symbols[i][0] == atom_functions[0][0]:
                    if atomic_constraints_symbols[i][1] =='rhs':
                        if atom_functions[0][1] =='before':
                            try:
                                comparison_rhs = symbolic_state.line_number < rhs_trigger_line_number
                            except:
                                comparison_rhs = False
                        elif atom_functions[0][1] =='after':
                            try:
                                comparison_rhs = symbolic_state.line_number <= rhs_trigger_line_number
                            except:
                                comparison_rhs = False

            # recurse over the symbolic states in rhs scfg to extract all function calls until rhs_trigger
            if comparison_rhs and symbolic_state.called_symbols() != 0:
                # check comparison and check if symbolic state is a function to record all the function call afterwards
                for called_symbol in symbolic_state.called_symbols():
                    # generate the name of the function together with its module
                    last_called_function = self.find_module_symbolic_state(module_rhs,called_symbol)

                    # last_called_function = module_rhs + ":" + called_symbol
                    if 'print' not in last_called_function:
                        # and list(symbolic_state.all_symbols())[0] != "sleep_function":
                        # add function to the list of called functions
                        func_atom.append(last_called_function)
                        # recursively call the find_called_functions on each function we find
                        try:
                            self.find_called_functions(func_atom, last_called_function)
                        except BaseException:
                            logging.info("BaseException encountered")

        return func_atom

    def find_module_symbolic_state(self,module,called_symbol):
        func_symbolic_state_called = called_symbol
        module_path = []
        module_path.append(str(self._get_original_path_from_module(module)))
        # get program path (so that we can search in that directory)
        path_to_directory = self._root_directory
        for n in range(len(str(module_path[0]))):
            if "/" == str(module_path[0])[-n - 1]:
                # get directory of the program
                path_to_directory = str(module_path[0])[:-n - 1]
                break

        # we search if it has "." which mean that it could be defined in another file
        if "." in called_symbol:
            file_symbolic_state_called = called_symbol.rsplit(".")[0]
            func_symbolic_state_called = called_symbol.rsplit(".")[1]
            module_sym_state = file_symbolic_state_called + ".py"
        else:
            module_sym_state = module

        # we search if there is a file with the name of the function
        # if not then we say the function is in the same module as lhs
        if module_sym_state not in os.listdir(path_to_directory):
            module_sym_state = module
        else:
            # we iterate over files in the directory
            for file in os.listdir(path_to_directory):
                # for each python file we find
                if file.endswith(".py"):
                    # we check if we can find a match to the first assumption
                    if module_sym_state == file:
                        module_sym_state = file
        symbols_list_function_module_called = module_sym_state + ":" + func_symbolic_state_called
        return symbols_list_function_module_called

    def find_rhs_parent(self, symbolic_state_module_caller, rhs,functions_connected_to_rhs:list,caller_line_number,parent_module):
        try:
            self._function_name_to_scfg_map[symbolic_state_module_caller] = scfg_from_qualified_name(symbolic_state_module_caller,
                                                                                                 self._root_directory)
            # extract module from lhs expression
            module = self._extract_module_name_from_function(symbolic_state_module_caller)
        except:
            module = self._extract_module_name_from_function(symbolic_state_module_caller)

        module_path = []
        module_path.append(str(self._get_original_path_from_module(module)))
        module_graph = get_call_graph(module_path)

        if symbolic_state_module_caller not in module_graph:
            #function does not exist in this graph
            return None
        # recurse over the symbolic states to find connection to rhs from lhs during function
        for symbolic_state in self._function_name_to_scfg_map[symbolic_state_module_caller].symbolic_states:
            symbols_list = list(symbolic_state.all_symbols())
            if len(symbolic_state.called_symbols()) != 0 and "range" not in symbolic_state.all_symbols():
                for called_symbol in symbolic_state.called_symbols():
                    for node in module_graph:
                        if called_symbol == node.split(":")[1]:
                            symbolic_state_found = 1
                            break
                        else:
                            symbolic_state_found = 0

                    if symbolic_state_found == 1:
                        # if function name equal to symbolic state record all the function call afterwards
                        if (module + ":" + called_symbol) == rhs:
                            if caller_line_number not in functions_connected_to_rhs:
                                functions_connected_to_rhs.append(caller_line_number)
                            if symbolic_state.line_number not in functions_connected_to_rhs:
                                functions_connected_to_rhs.append(symbolic_state.line_number)
                            return functions_connected_to_rhs
                        elif len(symbolic_state.called_symbols()) != 0 and symbolic_state.called_symbols() != set():
                            # generate the name of the function together with its module
                            last_called_function = str(module) + ":" + called_symbol
                            if 'print' not in last_called_function:
                                # add function to the list of called functions
                                # check if module is the parent module, as we are interested to find the parent of rhs in lhs and not in other directories
                                if symbolic_state.line_number not in functions_connected_to_rhs and module == parent_module:
                                    functions_connected_to_rhs.append(symbolic_state.line_number)
                                # we ignore the other functions called in sleep function
                                if "sleep_function" not in list(symbolic_state.all_symbols()) and module == parent_module:
                                    # recursively call the find_called_functions on each function we find
                                    self.find_rhs_parent(module + ":" + called_symbol, rhs,
                                                         functions_connected_to_rhs, symbolic_state.line_number,
                                                         parent_module)

    # def insert_loop(self,trace,loop_size):
    #     for event in trace:
    #         if event.get("type") == "function":
    #             module_name = event.get("module_name")
    #             line_number = event.get("line_number")
    #             function_name = event.get("function_name").split(":")[1]
    #             break;
    #
    #     with open(module_name, "r") as file:
    #         lines = file.readlines()
    #         file.close()
    #
    #     line_index = line_number
    #     # get the module lines
    #     module_lines = self._module_to_lines[module_name]
    #     # get the indentation level of the code to be inserted
    #     indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index])
    #     if indentation_level == 0:
    #         indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index - 1])
    #     # generate instrument code
    #     # construct the indentation string
    #     indentation = " " * indentation_level
    #     lines[line_number] = indentation + f"for i in range({loop_size}): {function_name}"
    #
    #     with open(module_name, "w") as file:
    #         file.writelines(lines)
    #         file.close()

    def get_indentation_level_of_stmt(self, stmt: str) -> int:
        """
        Given a statement, assuming indentation is performed using spaces, count the number of spaces.
        """
        # initialise number of spaces
        number_of_spaces = 0
        # iterate through the string until a non-space character is found
        for i in range(len(stmt)):
            if stmt[i] != " ":
                break
            else:
                number_of_spaces += 1

        return number_of_spaces

    def _generate_quantifier_instrument_code(self, spec_id: int, module_name: str, line_index: int, quantifier_id: int):
        """
        Given all necessary information, generate the instrumentation code for a quantifier.
        """
        logging.info(f"Getting lines of module_name = {module_name}")
        # get the module lines
        module_lines = self._module_to_lines[module_name]
        # get the indentation level of the code to be inserted
        indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index])
        # generate instrument code
        # construct the indentation string
        indentation = " " * indentation_level
        # define instrument function
        instrument_function = "SCSL.Monitoring.process_event"
        # check the instrument type
        logging.info(f"Generating instrument code for quantifier with id = {quantifier_id}")
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = f"\"time\": {total_seconds_expression} - SCSL.Monitoring.monitoring._start_time"
        line_number = line_index + 1
        line_number_code = f"\"line_number\": {line_number}"
        code = f"{indentation}{instrument_function}" \
               f"({{\"type\": \"trigger\", \"spec_id\": {spec_id}, " \
               f"\"quantifier_id\": {quantifier_id}, {time}, {line_number_code}}})"
        return code

    def _generate_quantifier_expression_instrument_code(self, spec_id: int, module_name: str, line_index: int,
                                                        quantifier_id, sub_expression_index):
        """
        Given all necessary information, generate the instrumentation code for a quantifier's sub expression.
        """
        logging.info(f"Getting lines of module_name = {module_name}")
        # get the module lines
        module_lines = self._module_to_lines[module_name]
        # get the indentation level of the code to be inserted
        indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index])
        # generate instrument code
        # construct the indentation string
        indentation = " " * indentation_level
        # define instrument function
        instrument_function = "SCSL.Monitoring.monitoring.process_event"
        # check the instrument type
        logging.info(f"Generating instrument code for quantifier with id = {quantifier_id}")
        total_seconds_expression = "scsl_monitoring_time.time()"
        time = f"\"time\": {total_seconds_expression} - SCSL.Monitoring.monitoring._start_time"
        code = f"{indentation}{instrument_function}" \
               f"({{\"type\": \"quantifier-expression\", \"spec_id\": {spec_id}, " \
               f"\"quantifier_id\": {quantifier_id}, \"sub_expression_index\": {sub_expression_index}, {time}}})"
        return code

    def _generate_constraint_instrument_code(self, spec_id: int, module_name: str, line_index: int, atom_index: int,
                                             subatom_index: int, subatom) -> list[InstrumentationLine]:
        """
        Given all of the necessary information, generate the instrumentation code for a constraint.
        """
        logging.info(f"Getting lines of module_name = {module_name}")
        # get the module lines
        module_lines = self._module_to_lines[module_name]
        # get the indentation level of the code to be inserted
        indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index])
        # generate instrument code
        # construct the indentation string
        indentation = " " * indentation_level
        # define instrument function
        instrument_function = "SCSL.Monitoring.monitoring.process_event"
        # check the instrument type
        logging.info(
            f"Generating measurement instrument code according to subatom = {subatom} with type {type(subatom)}")
        # import class to generate the code, according to the type of the subatom
        class_name = type(subatom).__name__
        module = importlib.import_module(f"InstrumentPythonSCSL.CodeGenerators.{class_name}")
        generator_class = module.Generator
        # instantiate class
        generator_instance = generator_class(
            indentation,
            spec_id,
            module_name,
            self._ast_modules[module_name],
            line_index,
            module_lines[line_index],
            instrument_function,
            atom_index,
            subatom_index,
            subatom
        )
        # generate code
        instrumentation_lines = generator_instance.generate_code_line_list()

        logging.info(f'Instrumentation code: {instrumentation_lines}')

        return instrumentation_lines

    # genrate instrumenttion code for functions
    def _generate_function_instrument_code(self,spec_id, module_name: str, line_index: int, element_index: int, function_name:str, atom_index:int):
        """
        Given all of the necessary information, generate the instrumentation code for a function.
        """
        logging.info(f"Getting lines of module_name = {module_name}")
        # get the module lines
        #if module is already in the list of modules then we can ge the lines directly
        try:
            module_lines = self._module_to_lines[module_name]
        except:
            #otherwise for newly function that we discovered by analysing the code/call graph
            #we need to build the ast of the new module
            self._ast_modules[module_name] = self._get_ast_from_module(module_name)
            #get the lines from the new module
            self._module_to_lines[module_name] = self._get_lines_from_module(module_name)

            module_lines = self._module_to_lines[module_name]
        # get the indentation level of the code to be inserted
        try:
            indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index])
            module_lines_index = module_lines[line_index]
        # for atoms with "after" we need to insert instrument in the next line after
        # the call site which may be outside the function so we need to copy the indenatation of the line before
        # if indentation_level == 0:
        except:
            indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index - 1])
            module_lines_index = module_lines[line_index - 1]
        # generate instrument code
        # construct the indentation string
        indentation = " " * indentation_level

        # define instrument function
        instrument_function = "SCSL.Monitoring.monitoring.process_event"
        class_name = "FunctionConcreteState"
        module = importlib.import_module(f"InstrumentPythonSCSL.CodeGenerators.{class_name}")

        generator_class = module.Generator
        # instantiate class
        generator_instance = generator_class(
            indentation,
            spec_id,
            module_name,
            self._ast_modules[module_name],
            line_index,
            module_lines_index,
            instrument_function,
            element_index,
            function_name,
            atom_index
        )

        # generate code
        instrumentation_lines = generator_instance.generate_code_line_list()

        logging.info(f'Instrumentation code: {instrumentation_lines}')

        return instrumentation_lines

        # genrate instrumenttion code for functions

    def _generate_function_instrument_code_after(self, spec_id, module_name: str, line_index: int, element_index: int,
                                           function_name: str, atom_index: int):
        """
        Given all of the necessary information, generate the instrumentation code for a function.
        """
        logging.info(f"Getting lines of module_name = {module_name}")
        # get the module lines
        # if module is already in the list of modules then we can ge the lines directly
        try:
            module_lines = self._module_to_lines[module_name]
        except:
            # otherwise for newly function that we discovered by analysing the code/call graph
            # we need to build the ast of the new module
            self._ast_modules[module_name] = self._get_ast_from_module(module_name)
            # get the lines from the new module
            self._module_to_lines[module_name] = self._get_lines_from_module(module_name)

            module_lines = self._module_to_lines[module_name]

        indentation_level = self.get_indentation_level_of_stmt(module_lines[line_index - 1])
        module_lines_index = module_lines[line_index - 1]
        # generate instrument code
        # construct the indentation string
        indentation = " " * indentation_level

        # define instrument function
        instrument_function = "SCSL.Monitoring.monitoring.process_event"
        class_name = "FunctionConcreteState"
        module = importlib.import_module(f"InstrumentPythonSCSL.CodeGenerators.{class_name}")

        generator_class = module.Generator
        # instantiate class
        generator_instance = generator_class(
            indentation,
            spec_id,
            module_name,
            self._ast_modules[module_name],
            line_index,
            module_lines_index,
            instrument_function,
            element_index,
            function_name,
            atom_index
        )

        # generate code
        instrumentation_lines = generator_instance.generate_code_line_list()

        logging.info(f'Instrumentation code: {instrumentation_lines}')

        return instrumentation_lines


    def _get_original_path_from_module(self, module: str) -> pathlib.Path:
        """
        Given a module name, derive its filename.
        """
        return pathlib.Path(self._root_directory, module)

    def _get_backup_path_from_module(self, module: str) -> pathlib.Path:
        """
        Given a module name, derive its filename.
        """

        original_path = pathlib.Path(self._root_directory, module)
        return pathlib.Path(original_path.parent,
                            f'{original_path.stem}_uninstrumented_original{original_path.suffix}')

    def compile(self):
        """
        Given the modified source code of the modules, write new files (backup old files).
        """
        logging.info("Writing instrumented code")
        # iterate through modules
        for module in self._all_modules:
            logging.info(f"Processing module = {module}")

            # get lines for this module
            lines = self._module_to_lines[module]
            # add new lines
            lines = list(map(lambda line: f"{line}\n", lines))

            # get the original and backup filenames from the module
            original_path = self._get_original_path_from_module(module)
            backup_path = self._get_backup_path_from_module(module)

            print(
                f"Instrumenting original_path = {original_path}, while keeping a backup in backup_path = {backup_path}")

            # if it exists, rename the backup to the original
            if backup_path.is_file():
                os.rename(backup_path, original_path)

            # copy the original to a backup
            copyfile(original_path, backup_path)

            # write the lines for the module to the source file
            with open(original_path, "w") as h:
                h.writelines(lines)