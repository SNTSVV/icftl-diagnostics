"""
Module containing functions for constructing an LHS specification.
"""
import sys

from ..Specifications.constraints import (dummy_variable_value_from_quantifier,
                                          is_normal_atom,
                                          is_mixed_atom,
                                          SignalAtTimestamp,
                                          DurationOfTransitionLessThanNumber,
                                          TransitionVariable,
                                          BooleanConstant)
from ..Specifications.predicates import changes, calls, inTimeInterval


def construct_cumulative_binding(quantifier):
    """
    Given `quantifier`, construct the binding (of placeholders) with which its subformula should be instantiated.
    """
    # construct argument dictionary
    argument_dict = {
        quantifier.get_id(): dummy_variable_value_from_quantifier(quantifier)
    }
    # update with binding dictionary
    if quantifier._binding:
        argument_dict.update(quantifier._binding)

    return argument_dict


class SubFormula:
    """
    Base class for subformulae.
    """
    pass


class Specification:
    """
    Base class for specifications.
    """

    def __init__(self, specification):
        self._specification = specification

    def get_specification(self):
        return self._specification

    def __eq__(self, other):
        return Specification in type(other).__bases__ and self.get_specification() == other.get_specification()

    def __repr__(self):
        """
        Note: this is used for a comparison of specifications in SCSL/Monitoring/monitoring.py.
        """
        return repr(self._specification)


class Duration(Specification):
    """
    Class to wrap a duration specification.
    """
    pass


class TimeBetween(Specification):
    """
    Class to wrap a time between specification.
    """
    pass


class Whenever(Specification):
    """
    Class to wrap a whenever-eventually specification.
    """
    pass


class Quantifier:
    """
    Base class for quantifiers.
    """

    def __init__(self, **kwargs):
        """
        `kwargs` is assumed to contain three keys: 1) the name of the variable
        to which values will be bound by the quantifier represented by this
        `forall` instance; and 2) the binding dictionary for the current branch
        of the formula; and 3) the id of the quantifier.
        """

        # ensure there is only one variable
        if len(list(kwargs.keys())) != 3:
            # if we don't have three keys because no binding/id is included, construct an empty binding
            if "binding" not in kwargs.keys():
                kwargs["binding"] = {}
            else:
                # the exception we throw returns to a single argument
                # because the user only gives one argument in their specification -
                # the other is added by us
                raise Exception("forall must be given a single keyword argument.")

        # store variables
        self._predicate = kwargs["predicate"]

        # set up an empty variable for the subformula
        self._subformula = None

        # remember the binding
        self._binding = kwargs["binding"]

        # remember the id
        self._id = kwargs["id"]

    def __sizeof__(self):
        return sys.getsizeof(self._id) +\
               sys.getsizeof(self._binding) +\
               sys.getsizeof(self._predicate) +\
               sys.getsizeof(self._subformula)

    def get_id(self):
        return self._id

    def get_sub_expression(self, index):
        if type(self) in [forall, exists] and type(self.get_predicate()) is inTimeInterval:
            predicate = self.get_predicate()
            sub_expressions = [predicate.get_left_expression(), predicate.get_right_expression()]
            return sub_expressions[index]
        else:
            return None

    def set_sub_expression_value(self, value, sub_expression_index):
        """
        Set the predicate's subexpression at index `sub_expression_index` to `value`.
        """
        # set the subexpression value of this quantifier's predicate
        self._predicate.set_sub_expression_value(value, sub_expression_index)

    def get_quantifiers(self):
        """
        Traverse the specification and construct a list of the quantifiers that it contains.
        """
        # initialise empty list of quantifiers
        quantifiers = []
        # recurse on the specification structure
        self._get_quantifiers(self, quantifiers)
        return quantifiers

    def _get_quantifiers(self, subformula, quantifiers):
        """
        Recursive case for traversing specifications to build up a list of quantifiers.
        """
        if is_normal_atom(subformula) or is_mixed_atom(subformula):
            # base case (but we don't do anything since we haven't found a quantifier)
            pass
        elif type(subformula) in [conjunction, disjunction]:
            # recurse on each subformula
            for conjunction_subformula in subformula.get_subformulae():
                self._get_quantifiers(conjunction_subformula, quantifiers)
        elif type(subformula) is negate:
            # recurse on the subformula
            self._get_quantifiers(subformula.get_subformula(), quantifiers)
        elif type(subformula) in [forall, exists]:
            # add the quantifier to the list
            quantifiers.append(subformula)
            # construct argument dictionary
            argument_dict = construct_cumulative_binding(subformula)
            # get the subformula
            quantifier_subformula = subformula.get_subformula()
            # instantiate the subformula
            instantiated_subformula = quantifier_subformula(argument_dict)
            # recurse
            self._get_quantifiers(instantiated_subformula, quantifiers)

    def get_atoms(self):
        """
        Traverse the specification and construct a list of the atoms that it contains.
        """
        # get atomic constraints used in subformula
        # construct argument dictionary
        argument_dict = construct_cumulative_binding(self)
        # get the subformula
        quantifier_subformula = self.get_subformula()
        # instantiate the subformula
        instantiated_subformula = quantifier_subformula(argument_dict)
        atoms = instantiated_subformula.get_atoms()
        return atoms

    def get_expressions(self):
        """
        Iterate through the list of atoms, extracting the list of expressions from each.
        """
        # get the list of atoms
        atoms = self.get_atoms()
        # initialise empty list of expressions
        expressions = []
        # get the list of expressions for each atom
        for atom in atoms:
            # check for atomic constraints that are constants
            if type(atom) is not BooleanConstant:
                # get the subexpressions
                # in some cases, there is only one, so both expressions are the same
                expression_0 = atom.get_expression(0)
                expression_1 = atom.get_expression(1)
                if expression_0 not in expressions:
                    expressions.append(expression_0)
                if expression_1 not in expressions:
                    expressions.append(expression_1)
        return expressions

    def get_all_signal_names(self):
        # get expressions
        expressions = self.get_expressions()
        # initialise empty list of signal names
        signal_names = []
        # determine which expressions involve signals
        for expression in expressions:
            # check type of expression
            if type(expression) is SignalAtTimestamp:
                signal_name = expression.get_signal_name()
                if signal_name not in signal_names:
                    signal_names.append(signal_name)
        return signal_names

    def get_function_names(self):
        """
        Get the list of names of functions found in predicates used in the specification.
        """
        # get the predicate attached to the quantifier
        predicate = self.get_predicate()
        # get the function name it uses
        predicate_function_names = predicate.get_function_names()
        # get function names used in subformula
        # construct argument dictionary
        argument_dict = construct_cumulative_binding(self)
        # get the subformula
        quantifier_subformula = self.get_subformula()
        # instantiate the subformula
        instantiated_subformula = quantifier_subformula(argument_dict)
        inner_function_names = instantiated_subformula.get_function_names()
        # combine the lists of function names
        final_function_names = predicate_function_names + inner_function_names
        # remove duplicates
        unique_function_names = list(set(final_function_names))
        return unique_function_names

    def get_predicate(self):
        return self._predicate

    def get_subformula(self):
        return self._subformula

    def check(self, subformula):
        """
        Set the subformula to be checked for each value identified by this quantifier.
        """
        self._subformula = subformula
        return self


class forall(Quantifier):
    """
    Models a universal quantifier.
    """

    def __repr__(self):
        if self._subformula:
            # construct argument dictionary
            argument_dict = construct_cumulative_binding(self)
            return f"forall v{self.get_id()} in {self._predicate}\n{self._subformula(argument_dict)}\n"
        else:
            return f"forall v{self.get_id()} in {self._predicate}"


class exists(Quantifier):
    """
    Models an existential quantifier.
    """

    def __repr__(self):
        if self._subformula:
            # construct argument dictionary
            argument_dict = construct_cumulative_binding(self)
            return f"exists v{self.get_id()} in {self._predicate}\n{self._subformula(argument_dict)}\n"
        else:
            return f"exists v{self.get_id()} in {self._predicate}"


class conjunction:
    """
    Models conjunction in a subformula.
    """

    def __init__(self, *args):
        """
        `args` is assumed to be a list of subformulae.
        `binding` is a dictionary whose keys are all variables quantified
        on this branch of the formula.
        """

        # get binding from args
        binding = args[0]

        # store subformulae
        self._subformulae = args

        # attach binding to each of the subformulae
        for subformula in self._subformulae:
            # we don't set the binding for forall or binding dictionaries
            if type(subformula) not in [forall, exists, dict]:
                subformula.set_binding(binding)

        self._binding = binding

    def __sizeof__(self):
        return sys.getsizeof(self._binding) + sum(map(sys.getsizeof, self.get_subformulae()))

    def get_function_names(self):
        all_function_names = []
        for subformula in self._subformulae:
            if type(subformula) is not dict:
                all_function_names += subformula.get_function_names()
        return all_function_names

    def get_atoms(self):
        all_atoms = []
        for subformula in self._subformulae:
            if type(subformula) is not dict:
                all_atoms += subformula.get_atoms()
        return all_atoms

    def get_subformulae(self):
        return self._subformulae

    def set_binding(self, binding):
        self._binding = binding

    def __repr__(self):
        indent = " " * (len(list(self._binding.keys())))
        return (f"\n{indent}and\n").join(
            map(
                lambda subformula: f"{indent}{subformula}",
                filter(lambda item: type(item) is not dict, self._subformulae)
            )
        )


class disjunction:
    """
    Models disjunction in a subformula.
    """

    def __init__(self, *args):
        """
        `args` is assumed to be a list of subformulae.
        `binding` is a dictionary whose keys are all variables quantified
        on this branch of the formula.
        """

        # get binding from args
        binding = args[0]

        # store subformulae
        self._subformulae = args

        # attach binding to each of the subformulae
        for subformula in self._subformulae:
            # we don't set the binding for forall or binding dictionaries
            if type(subformula) not in [forall, exists, dict]:
                subformula.set_binding(binding)

        self._binding = binding

    def __sizeof__(self):
        return sys.getsizeof(self._binding) + sum(map(sys.getsizeof, self.get_subformulae()))

    def get_function_names(self):
        all_function_names = []
        for subformula in self._subformulae:
            if type(subformula) is not dict:
                all_function_names += subformula.get_function_names()
        return all_function_names

    def get_atoms(self):
        all_atoms = []
        for subformula in self._subformulae:
            if type(subformula) is not dict:
                all_atoms += subformula.get_atoms()
        return all_atoms

    def get_subformulae(self):
        return self._subformulae

    def set_binding(self, binding):
        self._binding = binding

    def __repr__(self):
        indent = " " * (len(list(self._binding.keys())))
        return (f"\n{indent}or\n").join(
            map(
                lambda subformula: f"{indent}{subformula}",
                filter(lambda item: type(item) is not dict, self._subformulae)
            )
        )


class negate:
    """
    Models negation in a subformula.
    """

    def __init__(self, subformula, binding=None):
        """
        `subformula` is assumed to be a `SubFormula` instance.
        `binding` is a dictionary whose keys are all variables quantified
        on this branch of the formula.
        """

        # store the subformula
        self._subformula = subformula

        # attach binding to the subformula
        self._subformula.set_binding(binding)

    def __sizeof__(self):
        return sys.getsizeof(self._binding) + sys.getsizeof(self.get_subformula())

    def get_function_names(self):
        return self.get_subformula().get_function_names()

    def get_atoms(self):
        return self.get_subformula().get_atoms()

    def get_subformula(self):
        return self._subformula

    def set_binding(self, binding):
        self._binding = binding

    def __repr__(self):
        return f"negate({self._subformula})"
