import logging
import sys
from typing import List, Optional

import graphviz

from .symbolic_states import SymbolicState, EnterProcedure, ExitProcedure


class SCFG:
    def __init__(self):
        """
        Create a blank SCFG
        """
        # initialize an empty list which will be used to store the AST of the function definition
        self._program_asts: list = []
        self.procedure_name: Optional[str] = None
        self.procedure_parameters: Optional[List[str]] = None
        self.entry_point: SymbolicState = SymbolicState(EnterProcedure)
        self.exit_point: SymbolicState = SymbolicState(ExitProcedure)
        self.symbolic_states: List[SymbolicState] = [self.entry_point, self.exit_point]

    def relevant_states(self, symbol: str) -> list:
        """
        Given a symbol, determine the list of symbolic states in this SCFG where that symbol appears
        """
        return [
            state for state in self.symbolic_states if symbol in state.all_symbols()
        ]

    def relevant_writing_states(self, symbol: str) -> list:
        """
        Given a symbol, determine the list of symbolic states in this SCFG where that symbol is written
        """
        return [
            state for state in self.symbolic_states if symbol in state.written_symbols()
        ]

    def relevant_reading_states(self, symbol: str) -> list:
        """
        Given a symbol, determine the list of symbolic states in this SCFG where that symbol is read
        """
        return [
            state for state in self.symbolic_states if symbol in state.read_symbols()
        ]

    def relevant_calling_states(self, symbol: str) -> list:
        """
        Given a symbol, determine the list of symbolic states in this SCFG where that symbol is called
        """
        return [
            state for state in self.symbolic_states if symbol in state.called_symbols()
        ]

    def relevant_annotated_states(self, predicate) -> list:
        """
        Given a predicate, determine the list of symbolic states in this SCFG that have the corresponding
        annotation.

        For example, given a predicate Sensitive("x"), we want to find symbolic states with the annotation
        Sensitive -> {..., "x", ...}.
        """
        # initialise empty set of relevant sym states
        relevant_sym_states = []
        # get predicate name
        predicate_name = predicate.get_predicate_name()
        predicate_args = predicate.get_args()
        predicate_arity = len(predicate_args)
        print(predicate_name, predicate_args)
        # iterate through symbolic states
        for sym_state in self.symbolic_states:
            # check for symbolic state being reachable from root of SCFG
            if self.is_reachable(sym_state):
                # get annotation
                annotations = sym_state.annotations
                # get value of predicate name in annotations - this will differ according to the arity of the predicate
                value_of_predicate = annotations[predicate_name]
                print(predicate_name, value_of_predicate)
                # check for presence of args in the value of the predicate
                if predicate_arity == 0:
                    # TODO: check logic for arity 0
                    if value_of_predicate is True:
                        relevant_sym_states.append(sym_state)
                if predicate_arity == 1:
                    if predicate_args[0] in value_of_predicate:
                        relevant_sym_states.append(sym_state)
                elif predicate_arity > 1:
                    # TODO: check assumption that (arity > 1) predicates will use tuples
                    if predicate_args in value_of_predicate:
                        relevant_sym_states.append(sym_state)
        print(relevant_sym_states)
        return relevant_sym_states

    def get_reachable_symbolic_states_from_symbol(self, symbol: str, symbolic_state) -> list:
        """
        Given a symbol and a symbolic state, determine the list of symbolic states in this SCFG
        that indicate a change of symbol, and that are reachable from symbolic_state.
        """
        # get all symbolic states from symbol and then filter on reachability
        return [
            state for state in self.relevant_states(symbol) if self.is_reachable_from(state, symbolic_state)
        ]

    def is_reachable_from(self, target_symbolic_state, source_symbolic_state) -> bool:
        print('Warning: this function could be deprecated!', file=sys.stderr)
        return self.exists_path(source_symbolic_state, target_symbolic_state, True)

    def is_reachable(self,
                    target: SymbolicState,
                    follow_exit_points: bool = False) -> bool:
        return self.exists_path(self.entry_point, target, follow_exit_points)

    def exists_path(self,
                    source: SymbolicState,
                    target: SymbolicState,
                    follow_exit_points: bool = False) -> bool:
        """
        Given source and target symbolic states, determine whether target
        is reachable from source.
        """
        # determine all symbolic states reachable from source_symbolic_state
        all_reachable_symbolic_states = self._get_reachable_symbolic_states(source, follow_exit_points)
        # check to see if target_symbolic_state is in the list
        return target in all_reachable_symbolic_states

    def remove_unreachable(self, follow_exit_points: bool = False):
        reachable = self._get_reachable_symbolic_states(self.entry_point, follow_exit_points)
        self.symbolic_states = [self.entry_point] + \
            [state for state in self.symbolic_states if state in reachable]
        for state in self.symbolic_states:
            if state.exit_state not in self.symbolic_states:
                state.exit_state = None
        if self.exit_point not in self.symbolic_states:
            self.exit_point = None


    def _get_reachable_symbolic_states(self,
                                       source: SymbolicState,
                                       follow_exit_points: bool = False) -> List[SymbolicState]:
        """
        Determine all symbolic states reachable from the source.
        """
        # initialise a stack
        stack = [source]
        # initialise the list of visited symbolic states
        visited = [source]
        # initialise the list of symbolic states reachable from source
        reachable = []
        # iterate while the stack is non-empty
        while len(stack) > 0:
            # get the top of the stack
            top = stack.pop()
            # get children
            if follow_exit_points:
                print(top.statement_type.label, top.next_states, top.exit_state)
                children = top.all_children()
            else:
                children = top.next_states
            # add all unvisited children to the stack
            unvisited_children = [child for child in children if child not in visited]
            # add to stack
            stack += unvisited_children
            # add to reachable
            reachable += unvisited_children
            # add to visited
            visited += unvisited_children

        return reachable

    def get_next_symbolic_states(self, program_variable, base_symbolic_state) -> list:
        """
        Given a program variable and a base symbolic state, determine the symbolic states
        reachable from base_symbolic_state for which there is some path on which they are
        the first symbolic states encountered to change program_variable.

        Do this by recursively traversing the SCFG from base_symbolic_state to simulate
        the possible paths.  Each time a symbolic state is encountered that changes program_variable,
        end recursion there and add that symbolic state to a global list.
        """
        # recurse with shared lists for next and encountered
        list_of_possible_next_symbolic_states = []
        encountered = []
        self._get_next_symbolic_states(program_variable, base_symbolic_state, list_of_possible_next_symbolic_states,
                                       encountered, skip=True)
        return list_of_possible_next_symbolic_states

    def _get_next_symbolic_states(self, program_variable, current_symbolic_state, list_of_nexts: list,
                                  encountered: list, skip=False):
        """
        Recursive case for get_next_symbolic_states.
        """
        # add current_symbolic_state to encountered
        encountered.append(current_symbolic_state)
        # check to see whether program_variable appears in current_symbolic_state
        # skip allows us to ensure we don't capture the base state as next
        if not skip and program_variable in current_symbolic_state.all_symbols():
            # we've found a symbolic state that qualifies as next
            # add to the list of nexts, and don't recurse any further
            if current_symbolic_state not in list_of_nexts:
                list_of_nexts.append(current_symbolic_state)
        else:
            # recurse on each child
            for child in current_symbolic_state.next_states:
                if child not in encountered:
                    self._get_next_symbolic_states(program_variable, child, list_of_nexts, encountered)

    def write_to_file(self,
                      filename: str,
                      graphviz_attributes: Optional[dict] = None,
                      written_first: bool = False,
                      include_line_numbers: bool = False,
                      include_end_line_numbers: bool = False,
                      delete_dot: bool = True):
        """
        Write a dot file of the SCFG.

        :param filename: The (extension-less) filename of the Graphviz and PDF files which will be rendered
        :param graphviz_attributes: Graphviz attributes for all nodes; see [docs](https://graphviz.org/docs/nodes/)
        :param written_first: If True, symbols will be listed in the order <written, read, called>
        :param include_line_numbers: If True, starting line numbers will be written on the graph
        :param include_end_line_numbers: If True, ending line numbers will be written on the graph
        """
        logging.info(f"Writing graph filename = {filename} for SCFG.")
        # instantiate directed graph
        graph = graphviz.Digraph()
        graph.attr("graph", splines="true", fontsize="10")
        common_attributes = {'shape': 'rectangle'}
        if graphviz_attributes is not None:
            common_attributes.update(graphviz_attributes)

        # iterate through symbolic states, draw edges between those that are linked
        # by child/parent
        for symbolic_state in self.symbolic_states:
            logging.info(f"Processing symbolic_state = {symbolic_state}")
            symbolic_state_attributes = common_attributes.copy()

            # Build label string
            label = str(symbolic_state.statement_type.label)
            if include_line_numbers and symbolic_state.line_number is not None:
                if label != '':
                    label += ' '
                # If both starting and ending line numbers should be included, and they are different
                if include_end_line_numbers and symbolic_state.end_line_number not in [None, symbolic_state.line_number]:
                    label += f'({symbolic_state.line_number}-{symbolic_state.end_line_number})'
                else:  # If starting line number is to be included, but the ending line number is not
                    label += f'({symbolic_state.line_number})'

            for expression in symbolic_state.expressions:
                label += f'\n{expression.__str__(written_first)} '

            for key, value in symbolic_state.annotations.items():
                label += f'\n{key}: {value}'

            symbolic_state_attributes['label'] = label

            if symbolic_state.graphviz_attributes is not None:
                symbolic_state_attributes.update(symbolic_state.graphviz_attributes)

            graph.node(str(id(symbolic_state)), **symbolic_state_attributes)
            for child in symbolic_state.next_states:
                graph.edge(
                    str(id(symbolic_state)),
                    str(id(child))
                )
            if symbolic_state.exit_state is not None:
                graph.edge(
                    str(id(symbolic_state)),
                    str(id(symbolic_state.exit_state)),
                    style='dotted'
                )
        graph.render(filename, cleanup=delete_dot)
        logging.info(f"SCFG written to file {filename}")
