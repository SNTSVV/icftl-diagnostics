"""
Module to hold all logic for searching a set of SCFGs for symbolic state/pairs of symbolic states
based on a predicate found in an iCFTL specification.
"""
import logging

from ..Specifications.predicates import changes, calls
from ..Specifications.constraints import (ConcreteStateAfterTransition,
                                                   ConcreteStateBeforeTransition,
                                                   NextTransitionAfterTransition,
                                                   NextConcreteStateAfterTransition,
                                                   NextTransitionAfterConcreteState,
                                                   NextConcreteStateAfterConcreteState,
                                                   SignalAtTimestamp,
                                                   TimestampExpressionWithAddition,
                                                   DurationOfTransition,
                                                   derive_sequence_of_temporal_operators)

class SCFGSearcher():
    """
    Class to represent a map from function names to SCFGs, and then provide
    methods to determine the set of symbolic states
    that satisfy a given predicate from an iCFTL specification.
    """

    def __init__(self, function_name_to_scfg_map):
        """
        Store the function_scfg_map for later.
        """
        self._function_name_to_scfg_map = function_name_to_scfg_map
    
    def find_symbolic_states(self, predicate):
        """
        Given a predicate find the relevant symbolic states.
        """
        logging.info(f"Finding symbolic states satisfying predicate {predicate}")
        # get the function at whose SCFG we will look
        function_name = predicate.get_during_function()
        # get the relevant SCFG
        logging.info(f"Getting symbolic control-flow graph for function '{function_name}'")
        relevant_scfg = self._function_name_to_scfg_map[function_name]
        # get the relevant symbolic states
        if type(predicate) is changes:
            symbol = predicate.get_program_variable()
            relevant_symbolic_states = relevant_scfg.relevant_writing_states(symbol)
        else:
            symbol = predicate.get_function_name()
            relevant_symbolic_states = relevant_scfg.relevant_calling_states(symbol)
        
        logging.info(f"Symbolic states found for predicate {predicate} for symbol {symbol} are {relevant_symbolic_states}")
        
        return relevant_symbolic_states
    
    def get_symbolic_states_from_temporal_operator(self, temporal_operator, base_symbolic_state) -> list:
        """
        Given a temporal operator object and a base symbolic state, either traverse
        forwards in the current symbolic control-flow graph, or search in others to determine the list of
        relevant symbolic states.
        """

        # check the type of the temporal operator
        if type(temporal_operator) in [NextTransitionAfterTransition,
                                       NextConcreteStateAfterTransition,
                                       NextTransitionAfterConcreteState,
                                       NextConcreteStateAfterConcreteState]:
            # we have a Next... operator, so we have two options:
            # 1) if the function in the predicate matches the function containing base_symbolic_state,
            #    we search forwards in that function's SCFG for appropriate symbolic states, or
            # 2) if the function in the predicate differs from the function containign base_symbolic_state,
            #    we search everywhere in the other function's SCFG (no reachability constraints).

            # get the function name of base_symbolic_state
            base_function_name = self.get_function_name_of_symbolic_state(base_symbolic_state)
            # get the function name from the predicate in temporal_operator
            temporal_operator_function_name = temporal_operator.get_predicate().get_during_function()
            # get the program variable from the temporal operator's predicate
            temporal_operator_predicate = temporal_operator.get_predicate()
            if type(temporal_operator_predicate) is changes:
                program_variable = temporal_operator_predicate.get_program_variable()
            else:
                program_variable = temporal_operator_predicate.get_function_name()
            # check for equality
            if base_function_name == temporal_operator_function_name:
                # get the relevant SCFG
                relevant_scfg = self._function_name_to_scfg_map[base_function_name]
                # the functions are equal, so we traverse forwards in the relevant SCFG
                relevant_symbolic_states = \
                    relevant_scfg.get_next_symbolic_states(
                        program_variable,
                        base_symbolic_state
                    )
            else:
                # the functions are not equal, so we get relevant symbolic states without looking
                # at reachability
                # get the relevant SCFG
                relevant_scfg = self._function_name_to_scfg_map[temporal_operator_function_name]
                # get relevant symbolic states
                relevant_symbolic_states = relevant_scfg.relevant_states(program_variable)
        
        elif type(temporal_operator) is ConcreteStateAfterTransition:
            # since we represent edges with the symbolic states immediately after them,
            # here we can just return base_symbolic_state
            relevant_symbolic_states = [base_symbolic_state]

        elif type(temporal_operator) is ConcreteStateBeforeTransition:
            # we get the same symbolic state as in the ConcreteStateBeforeTransition case - we leave it to
            # the final instrument placement to adjust indices accordingly
            relevant_symbolic_states = [base_symbolic_state]

        elif type(temporal_operator) is TimestampExpressionWithAddition:
            # we use the same symbolic state as is given, since addition just represents
            # applying a function to a measurement
            relevant_symbolic_states = [base_symbolic_state]

        elif type(temporal_operator) is DurationOfTransition:
            relevant_symbolic_states = [base_symbolic_state]
        
        return relevant_symbolic_states
    
    def get_function_name_of_symbolic_state(self, symbolic_state) -> str:
        """
        Given a symbolic state, search through self._function_name_to_scfg_map
        and return the name of the function whose SCFG contains the symbolic state.
        """
        logging.info(f"Determining function that generated symbolic state {symbolic_state}")
        # iterate through the function -> scfg map
        for function_name in self._function_name_to_scfg_map:
            # check whether symbolic_state is contained by the corresponding SCFG
            scfg = self._function_name_to_scfg_map[function_name]
            # there must be an SCFG containing the symbolic state we're searching for
            # this function cannot return None
            if symbolic_state in scfg.symbolic_states:
                logging.info(f"Found symbolic state in function '{function_name}'")
                return function_name
    
    def get_instrumentation_points_for_atomic_constraint(self, atomic_constraint, variable_symbolic_state_map: dict) -> dict:
        """
        Given an atomic constraint and a map from variables to symbolic states,
        determine the map from sub-atom indices to lists of symbolic states that are relevant to that part of the constraint.
        """
        logging.info(f"determining symbolic states for {atomic_constraint}")
        # initialise the empty map
        subatom_index_to_symbolic_states = {}
        # get the map of sequences of temporal operators for the atomic constraint given
        temporal_operator_sequence_map = derive_sequence_of_temporal_operators(atomic_constraint)
        # for each sequence of temporal operators (1 for normal atoms, 2 for mixed atoms),
        # determine the appropriate list of symbolic states
        for subatom_index in temporal_operator_sequence_map:
            # check to see whether the subatom at subatom_index is signal based
            # if it is signal based, we do not instrument for it
            subatom = atomic_constraint.get_subatom_at_index(subatom_index)
            # if the subatom is signal-based, or taken from the measurement performed by
            # a with-quantifier, we don't instrument for it
            # TODO: subatoms may use a timestamp variable at the root, but the chain of temporal operators
            # could require instrumentation
            if not subatom.is_signal_based():
                # get the composition sequence
                composition_sequence = temporal_operator_sequence_map[subatom_index]
                # get the symbolic states
                symbolic_states = self.get_instrumentation_points_from_composition_sequence(
                    composition_sequence,
                    variable_symbolic_state_map
                )
                # add to the subatom index map
                subatom_index_to_symbolic_states[subatom_index] = symbolic_states
            elif subatom.is_signal_based() and type(subatom) is DurationOfTransition:
                # duration of transition with a timestamp as a variable
                # get the transition expression
                transition_expression = subatom.get_transition_expression()
                # get predicate
                predicate = transition_expression.get_predicate()
                # get symbolic states
                symbolic_states = self.find_symbolic_states(predicate)
                # add to map
                subatom_index_to_symbolic_states[subatom_index] = symbolic_states

        return subatom_index_to_symbolic_states

    def get_instrumentation_points_from_composition_sequence(self, composition_sequence, variable_to_sym_states):
        """
        Given a `composition_sequence` and a map `variable_to_sym_states`, derive a set of symbolic states
        identified by application of `composition_sequence` to a starting symbolic state.
        """
        # get the base variable from the composition sequence
        base_variable = composition_sequence[-1]
        # get the temporal operator sequence
        temporal_operator_sequence = composition_sequence[:-1]
        # set the starting symbolic states
        current_symbolic_states = variable_to_sym_states[base_variable.get_name()]
        # iterate through the list of temporal operators
        for temporal_operator in temporal_operator_sequence:
            # for each symbolic state in current_symbolic_states, determine the relevant next
            # symbolic state based on temporal_operator

            # initialise empty list of symbolic states from the next stage of traversal
            new_symbolic_states = []
            # iterate through current_symbolic_states
            for current_symbolic_state in current_symbolic_states:
                # get the list of next ones based on temporal_operator
                next_symbolic_states = self.get_symbolic_states_from_temporal_operator(
                    temporal_operator,
                    current_symbolic_state
                )
                # add to new_symbolic_states
                new_symbolic_states += next_symbolic_states

            # overwrite current_symbolic_states
            current_symbolic_states = new_symbolic_states

        return current_symbolic_states