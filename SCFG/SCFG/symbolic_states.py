"""
Module to contain definitions of various kinds of symbolic states.
"""

from dataclasses import dataclass
import logging
from typing import List, Set, Optional


class Expression:
    def __init__(self, read: Set[str], written: Set[str], called: Set[str]):
        self.read = read
        self.written = written
        self.called = called

    def __str__(self, written_first: bool = False):
        def str_set(s: Set[str]):
            return '{' + ', '.join(sorted(s)) + '}'
        if written_first:
            return f"({str_set(self.written)}, {str_set(self.read)}, {str_set(self.called)})"
        else:
            return f"({str_set(self.read)}, {str_set(self.written)}, {str_set(self.called)})"

    def __repr__(self):
        return f"Expression ({self.read}, {self.written}, {self.called})"

    def __or__(self, other):
        return Expression(self.read | other.read,
                          self.written | other.written,
                          self.called | other.called)

    def all_symbols(self) -> Set[str]:
        return self.read | self.written | self.called


@dataclass
class StatementType:
    label: str
    is_loop: bool = False
    exits_procedure: bool = False
    diverts_flow: bool = False


EnterProcedure = StatementType(
    label='EnterProcedure',
    is_loop=False
)

ExitProcedure = StatementType(
    label='ExitProcedure',
    is_loop=False
)

class SymbolicState:
    """
    Base class for all types of symbolic states.
    """
    def __init__(self,
                 statement_type: StatementType,
                 expressions: Optional[List[Expression]] = None,
                 next_states: Optional[List['SymbolicState']] = None,
                 exit_state: Optional['SymbolicState'] = None,
                 line_number: Optional[int] = None,
                 column_offset: Optional[int] = None,
                 end_line_number: Optional[int] = None,
                 end_column_offset: Optional[int] = None,
                 graphviz_attributes: Optional[dict] = None
    ):
        self.statement_type = statement_type
        self.expressions = [] if expressions is None else expressions
        self.next_states = [] if next_states is None else next_states
        self.exit_state = exit_state
        self.line_number = line_number
        self.column_offset = column_offset
        self.end_line_number = end_line_number
        self.end_column_offset = end_column_offset
        self.annotations = {}
        self.parents: List[SymbolicState] = []
        if graphviz_attributes is None:
            self.graphviz_attributes = {}
        else:
            self.graphviz_attributes = graphviz_attributes
    
    def __repr__(self):
        return f"<{self.statement_type.label} (id {id(self)})>"

    def get_flattened_aspects(self):
        """
        Transform self.annotations into a map from string representations of static aspects (and arguments)
        to their values.

        For example, output could be

        {
            "aspect1(arg1, arg2)" : {"value" : True, "type" : set},
            "aspect2(arg1)" : {"value" : 2, "type" : dict}
        }
        """
        # initialise final dictionary
        final_dictionary = {}
        # iterate over aspects
        for aspect_name in self.annotations:
            aspect = self.annotations[aspect_name]
            # check type
            if type(aspect) is not list:
                # get all arguments
                flattened_aspect = self.get_flattened_aspect(aspect_name, aspect)
                # update dictionary
                final_dictionary.update(flattened_aspect)
        return final_dictionary

    def get_flattened_aspect(self, aspect_name, aspect):
        """
        Give a dictionary mapping a string representation of the aspect (name + args) to the aspect's value
        under the given args.
        """
        # initialise final dictionary
        final_dictionary = {}
        # what we do depends on the type of the aspect
        if type(aspect) not in [set, dict]:
            final_dictionary[aspect_name] = {"value": aspect, "type": type(aspect).__name__}
        else:
            if type(aspect) is set:
                # get arguments
                argument_sequences = list(
                    map(
                        lambda entry : (entry, ) if type(entry) is not tuple else entry,
                        aspect
                    )
                )
                # get value - true for every argument
                values = [{"value": True, "type": type(aspect).__name__} for seq in argument_sequences]
            elif type(aspect) is dict:
                # get arguments
                argument_sequences = list(
                    map(
                        lambda key : key if type(key) is tuple else (key,),
                        aspect.keys()
                    )
                )
                # get values
                values = list(map(
                    lambda value : {"value": value, "type": type(aspect).__name__}, aspect.values()
                ))
            for argument_seq, value in zip(argument_sequences, values):
                arg_list = ", ".join(argument_seq)
                arg_string = f"({arg_list})"
                string_representation = f"{aspect_name}{arg_string}"
                final_dictionary[string_representation] = value

        return final_dictionary

    def get_value_of_aspect(self, aspect):
        """
        Given an aspect (aspect name + args), gets its value in this symbolic state.

        The value depends on the type of the aspect.

        For now, the Boolean case is implemented. For example, for an aspect Sensitive = {"x", "y",...},
        we evaluate Sensitive("x") to True.
        """
        # get the aspect name
        aspect_name = aspect.get_predicate_name()
        # get the aspect args
        aspect_args = aspect.get_args()
        # get the arity
        aspect_arity = len(aspect_args)
        # for now, cover the case of arity = 1
        if aspect_arity == 0:
            aspect_value = self.annotations[aspect_name]
            return aspect_value
        else:
            # check type of aspect (predicate, function)
            if aspect_arity == 1:
                # get aspect value in this symbolic state
                aspect_value = self.annotations[aspect_name]
                if type(aspect_value) is set:
                    return aspect_args[0] in aspect_value
                elif type(aspect_value):
                    return aspect_value[aspect_args[0]]

    def all_symbols(self) -> Set[str]:
        """
        Returns the set of all symbols appearing in each expression
        """
        return set().union(*[e.all_symbols() for e in self.expressions])

    def read_symbols(self) -> Set[str]:
        """
        Returns the set of read symbols appearing in each expression
        """
        return set().union(*[e.read for e in self.expressions])

    def written_symbols(self) -> Set[str]:
        """
        Returns the set of written symbols appearing in each expression
        """
        return set().union(*[e.written for e in self.expressions])

    def called_symbols(self) -> Set[str]:
        """
        Returns the set of called symbols appearing in each expression
        """
        return set().union(*[e.called for e in self.expressions])

    def add_child(self, child_symbolic_state, exit_state: bool = False):
        """
        Add a child symbolic state to self.
        """
        logging.info(f"Appending child_symbolic_state = {child_symbolic_state} to children with self = {self} and exit_state={exit_state}")
        if child_symbolic_state is None:
            logging.warn("child_symbolic_state is None; it will not be added!")
        if exit_state:
            self.exit_state = child_symbolic_state
        else:
            if child_symbolic_state not in self.next_states:
                self.next_states.append(child_symbolic_state)

        # also set self as parent of child
        logging.info(f"Also calling child_symbolic_state.add_parent to add self = {self} as parent of child_symbolic_state = {child_symbolic_state}")
        if child_symbolic_state not in self.parents:
            self.parents.append(child_symbolic_state)

    def add_parent(self, parent_symbolic_state):
        """
        Add a parent symbolic state to self.
        """
        logging.info(f"Appending parent_symbolic_state = {parent_symbolic_state} to self._parents with self = {self}")
        self.parents.append(parent_symbolic_state)
    
    def all_children(self) -> List['SymbolicState']:
        if self.exit_state is None or self.exit_state in self.next_states:
            return self.next_states
        else:
            return self.next_states + [self.exit_state]

