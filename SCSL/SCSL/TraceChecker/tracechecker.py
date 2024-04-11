"""
Module holding the logic for offline monitoring of LHS specifications.
"""
# import pprint
import functools
import itertools
import typing

import graphviz
import timeit
import time
import datetime
import os
import logging
import sys

from SCSL.Specifications.predicates import inTimeInterval
from SCSL.Specifications.builder import construct_cumulative_binding
from SCSL.Specifications.builder import forall, exists, conjunction, disjunction, negate
from SCSL.Specifications.predicates import calls, changes
from SCSL.Specifications.constraints import (is_normal_atom,
                                             is_mixed_atom,
                                             SignalAtTimestampEqualsNumber,
                                             SignalAtTimestampLessThanNumber,
                                             SignalAtTimestampGreaterThanNumber,
                                             SignalAtTimestamp,
                                             TimestampExpressionWithAddition,
                                             TimestampVariable,
                                             TimeBetweenLessThanConstant,
                                             ValueInConcreteStateEqualToConstant,
                                             ValueInConcreteStateLessThanConstant,
                                             ValueInConcreteStateGreaterThanConstant,
                                             ValueInConcreteStateNotEqualToConstant,
                                             ValueInConcreteStateLessThanEqualToConstant,
                                             ValueInConcreteStateGreaterThanEqualToConstant,
                                             ValueInConcreteState,
                                             TimeBetween,
                                             ConcreteStateBeforeTransition,
                                             ConcreteStateAfterTransition,
                                             TimestampExpression,
                                             TimeOfConcreteState,
                                             TimeOfTransition,
                                             DurationOfTransitionLessThanNumber,
                                             DurationOfTransition,
                                             BooleanConstant)

class IncompatibleTypeError(Exception):
    pass

class MonitorTreeNode():
    """
    Class representing a node in a monitoring tree.

    The node needs to contain a reference to the subformula to which it corresponds.
    """

    def __init__(self, subformula, binding, monitor):
        self._monitor = monitor
        self._binding = binding
        self._subformula = subformula
        self._children = []
        self._parent = None
        # to be used when evaluating the monitoring tree
        self._value = None
        # # add node to monitor's list
        # self._monitor._monitoring_tree_nodes.append(self)
        # add to list of all nodes
        self._monitor._all_nodes.append(self)

    def __sizeof__(self):
        return sys.getsizeof(self.get_value()) + sys.getsizeof(self.get_subformula())

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value

    def get_binding(self):
        return self._binding

    def get_subformula(self):
        return self._subformula

    def set_parent(self, parent):
        self._parent = parent

    def get_parent(self):
        return self._parent

    def get_children(self):
        return self._children

    def add_child(self, child_node):
        self._children.append(child_node)
        child_node.set_parent(self)

    def evaluate_upwards(self):
        """
        Depending on the type of the parent, update it accordingly.
        """
        # get parent
        parent = self.get_parent()
        # check to see if we're at the root
        if parent:
            if type(parent) is MonitorTreeQuantifierNode:
                # dealing with a quantifier node, so evaluating its truth value
                # just involves either and-ing or or-ing its existing truth value
                # with the value given by evaluating the current node
                if type(parent.get_subformula()) is forall:
                    # and the current value with self.get_value()
                    original_parent_value = parent.get_value()
                    if parent.get_value() is None and self.get_value() is False:
                        parent.set_value(self.get_value())
                    elif parent.get_value() is not None and self.get_value() is not False:
                        parent.set_value(parent.get_value() and self.get_value())
                elif type(parent.get_subformula()) is exists:
                    # or the current value with self.get_value()
                    if parent.get_value() is None:
                        parent.set_value(self.get_value())
                    elif parent.get_value() is not True:
                        parent.set_value(parent.get_value() or self.get_value())
                    # exists is not allowed to be False until the end of the trace,
                    # so check and revert to None if this is the case
                    if parent.get_value() is False:
                        parent.set_value(None)
                    # if the exists is true now, remove it from self._monitor._nodes_with_timestamp_quantifiers
                    # (if it's in there)
                    if parent in self._monitor._nodes_with_timestamp_quantifiers and parent.get_value() is True:
                        self._monitor._nodes_with_timestamp_quantifiers.remove(parent)
                    # if true, remove the quantifier from the list of quantifiers
                    # to which branches can be added
                    if parent.get_value() is True:
                        if parent in parent._monitor.quantifier_id_to_nodes[parent.quantifier_id]:
                            parent._monitor.quantifier_id_to_nodes[parent.quantifier_id].remove(parent)
            elif type(parent) is MonitorTreeConjunctionNode:
                # get truth values of children
                all_truth_values = list(map(lambda child : child.get_value(), parent.get_children()))
                # compute current truth value of conjunction
                current_truth_value = True
                for value in all_truth_values:
                    current_truth_value = current_truth_value and value
                parent.set_value(current_truth_value)
            elif type(parent) is MonitorTreeDisjunctionNode:
                # get truth values of children
                all_truth_values = list(map(lambda child: child.get_value(), parent.get_children()))
                # compute current truth value of disjunction
                current_truth_value = False
                for value in all_truth_values:
                    current_truth_value = current_truth_value or value
                parent.set_value(current_truth_value)
            else:
                # we're dealing with an atomic constraint or expression node
                parent.evaluate()

            # continue upwards evaluation from the parent
            parent.evaluate_upwards()

    def update_subtree_binding(self, additional_entry):
        """
        Given `additional_entry`, recurse on the subtree, adding
        the key-value pair to the binding held by each node.
        """
        # update binding
        self._binding.update(additional_entry)
        # recurse
        for child in self.get_children():
            child.update_subtree_binding(additional_entry)

    def extract_measurements_from_subtree(self, atoms, up_to_id):
        """
        Construct a map from atom and subatom indices to measurements.
        """
        # initialise empty dictionary
        atom_subatom_measurement_map = {}
        # recurse on subtree
        self._extract_measurements_from_subtree(atoms, up_to_id, atom_subatom_measurement_map)
        return atom_subatom_measurement_map

    def _extract_measurements_from_subtree(self, atoms, up_to_id, atom_subatom_measurement_map):
        """
        Recurse and base cases.
        """
        # check whether the current tree root is an atomic constraint
        if is_normal_atom(self.get_subformula()) and type(self.get_subformula()) is not BooleanConstant:
            # only include measurements from this atomic constraint
            # if those measurements are derived from a variable close enough
            # to the root of the specification
            if self.get_children()[0].get_subformula().get_base_variable().get_name() < up_to_id:
                dictionary = {
                    atoms.index(self.get_subformula()): {
                        0: self.get_children()[0].get_value()
                    }
                }
                atom_subatom_measurement_map.update(dictionary)
        elif is_mixed_atom(self.get_subformula()):
            # only include measurements from this atomic constraint
            # if those measurements are derived from a variable close enough
            # to the root of the specification
            atom_index = atoms.index(self.get_subformula())
            dictionary = {
                atom_index: {}
            }
            if self.get_children()[0].get_subformula().get_base_variable().get_name() < up_to_id:
                dictionary[atom_index][0] = self.get_children()[0].get_value()
            if self.get_children()[1].get_subformula().get_base_variable().get_name() < up_to_id:
                dictionary[atom_index][1] = self.get_children()[1].get_value()
            if dictionary != {atom_index: {}}:
                atom_subatom_measurement_map.update(dictionary)
        else:
            # not an atomic constraint, so recurse on children
            for child in self.get_children():
                child._extract_measurements_from_subtree(atoms, up_to_id, atom_subatom_measurement_map)

    def update_newest_branch(self, atoms, measurements):
        """
        Given a dictionary of measurements, traverse the newest branch attached to self
        and set values of nodes to values found on another branch.

        This is used when there are measurements on branches from quantifiers far enough up the
        monitoring tree that those measurements also apply on new branches, hence must be copied over
        when we add a new branch.
        """
        self._update_newest_branch(atoms, measurements)

    def _update_newest_branch(self, atoms, measurements):
        """
        Recursive and base cases.
        """
        # check type of current_node
        if is_normal_atom(self.get_subformula()) or is_mixed_atom(self.get_subformula()):
            # check atom index
            atom_index = atoms.index(self.get_subformula())
            if atom_index in measurements:
                for subatom_index in measurements[atom_index]:
                    self.get_children()[subatom_index].set_value(
                        measurements[atom_index][subatom_index]
                    )
                    # evaluate
                    self.get_children()[subatom_index].evaluate_upwards()
        else:
            # recurse
            for child in self.get_children():
                child._update_newest_branch(atoms, measurements)


class MonitorTreeConjunctionNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds a conjunction.
    """

    def __init__(self, subformula, binding, monitor):
        # superclass call
        super().__init__(subformula, binding, monitor)
        # set value
        # self.set_value(True)

    def evaluate(self):
        if self.get_value() is not False:
            final_value = True
            for child in self.get_children():
                child.evaluate()
                final_value = final_value and child.get_value()
            self.set_value(final_value)

class MonitorTreeDisjunctionNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds a disjunction.
    """

    def __init__(self, subformula, binding, monitor):
        # superclass call
        super().__init__(subformula, binding, monitor)
        # set value
        # self.set_value(True)

    def evaluate(self):
        if self.get_value() is not True:
            final_value = False
            for child in self.get_children():
                child.evaluate()
                final_value = final_value or child.get_value()
            self.set_value(final_value)

class MonitorTreeNegateNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds a disjunction.
    """

    def evaluate(self):
        # evaluate the child
        self.get_children()[0].evaluate()
        # get the child value
        child_value = self.get_children()[0].get_value()
        # reverse the child value, if it's a truth value
        if child_value == True:
            self._value = False
        elif child_value == False:
            self._value = True

class MonitorTreeAtomNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds an atom.
    """

    def __init__(self, subformula, binding, monitor, atom_index):
        # superclass call
        super().__init__(subformula, binding, monitor)
        # store additional variables
        self._atom_index = atom_index
        # update the monitor's atom -> subatom -> nodes map
        if atom_index not in self._monitor._atom_subatom_nodes:
            self._monitor._atom_subatom_nodes[atom_index] = {}
        # if we have a boolean constant, set the node to have a constant value
        if type(subformula) is BooleanConstant:
            self.set_value(subformula.get_value())

    def evaluate(self):
        # depending on the type of atom, get the value of the child (representing the value of an expression)
        if not self.get_value():
            if type(self._subformula) is SignalAtTimestampEqualsNumber:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                self.set_value(bool(child_value == self._subformula.get_constant()))
            if type(self._subformula) is SignalAtTimestampLessThanNumber:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                # check for the existence of a child value
                # if we're performing evaluation of the tree based on observation
                # of a signal entry that is not yet >= the timestamp that is needed
                # the child value will be None
                if child_value is not None:
                    try:
                        self.set_value(bool(child_value < self._subformula.get_constant()))
                    except TypeError as e:
                        raise IncompatibleTypeError(
                            f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                            f"could not be compared under < with the value from the specification "
                            f"({self._subformula.get_constant()}, "
                            f"type {type(self._subformula.get_constant()).__name__})"
                        )
            if type(self._subformula) is SignalAtTimestampGreaterThanNumber:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                # check for the existence of a child value
                # if we're performing evaluation of the tree based on observation
                # of a signal entry that is not yet >= the timestamp that is needed
                # the child value will be None
                if child_value is not None:
                    try:
                        self.set_value(bool(child_value > self._subformula.get_constant()))
                    except TypeError as e:
                        raise IncompatibleTypeError(
                            f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                            f"could not be compared under > with the value from the specification "
                            f"({self._subformula.get_constant()}, "
                            f"type {type(self._subformula.get_constant()).__name__})"
                        )
            elif type(self._subformula) is ValueInConcreteStateEqualToConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                self.set_value(child_value == self._subformula.get_constant())
            elif type(self._subformula) is ValueInConcreteStateLessThanConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                try:
                    self.set_value(child_value < self._subformula.get_constant())
                except TypeError as e:
                    raise IncompatibleTypeError(
                        f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                        f"could not be compared under < with the value from the specification "
                        f"({self._subformula.get_constant()}, "
                        f"type {type(self._subformula.get_constant()).__name__})"
                    )
            elif type(self._subformula) is ValueInConcreteStateGreaterThanConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                try:
                    self.set_value(child_value > self._subformula.get_constant())
                except TypeError as e:
                    raise IncompatibleTypeError(
                        f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                        f"could not be compared under > with the value from the specification "
                        f"({self._subformula.get_constant()}, "
                        f"type {type(self._subformula.get_constant()).__name__})"
                    )
            elif type(self._subformula) is ValueInConcreteStateNotEqualToConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                self.set_value(child_value != self._subformula.get_constant())
            elif type(self._subformula) is ValueInConcreteStateLessThanEqualToConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                try:
                    self.set_value(child_value <= self._subformula.get_constant())
                except TypeError as e:
                    raise IncompatibleTypeError(
                        f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                        f"could not be compared under <= with the value from the specification "
                        f"({self._subformula.get_constant()}, "
                        f"type {type(self._subformula.get_constant()).__name__})"
                    )
            elif type(self._subformula) is ValueInConcreteStateGreaterThanEqualToConstant:
                # evaluate child
                self.get_children()[0].evaluate()
                # get child value
                child_value = self.get_children()[0].get_value()
                try:
                    self.set_value(child_value >= self._subformula.get_constant())
                except TypeError as e:
                    raise IncompatibleTypeError(
                        f"The value recorded at runtime ({child_value}, type {type(child_value).__name__}) "
                        f"could not be compared under >= with the value from the specification "
                        f"({self._subformula.get_constant()}, "
                        f"type {type(self._subformula.get_constant()).__name__})"
                    )
            elif type(self._subformula) is TimeBetweenLessThanConstant:
                # evaluate children
                self.get_children()[0].evaluate()
                self.get_children()[1].evaluate()
                # get values
                lhs_child_value = self.get_children()[0].get_value()
                rhs_child_value = self.get_children()[1].get_value()
                # compare
                if rhs_child_value is not None and lhs_child_value is not None:
                    self.set_value(rhs_child_value - lhs_child_value < self._subformula.get_constant())
            elif type(self._subformula) is DurationOfTransitionLessThanNumber:
                # evaluate child
                self.get_children()[0].evaluate()
                # get values
                child_value = self.get_children()[0].get_value()
                # check constraint, if there is a child value
                if child_value is not None:
                    self.set_value(child_value < self._subformula.get_constant())
            elif type(self._subformula) is BooleanConstant:
                # no need to set value - there's already a value
                pass

class MonitorTreeExpressionNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds an expression found in an atom.
    """

    def __init__(self, expression, binding, monitor, atom_index, subatom_index, is_leaf=False):
        # superclass call
        super().__init__(expression, binding, monitor)
        # store additional variables
        self._atom_index = atom_index
        self._subatom_index = subatom_index
        self._line_number = None
        self._module_name = None
        # if we have a leaf, update the monitor's atom -> subatom -> nodes map
        if is_leaf:
            if subatom_index not in self._monitor._atom_subatom_nodes[atom_index]:
                self._monitor._atom_subatom_nodes[atom_index][subatom_index] = [self]
            else:
                self._monitor._atom_subatom_nodes[atom_index][subatom_index].append(self)
        # if we have a signal.at(t) expression, add to the relevant map
        if type(expression) is SignalAtTimestamp:
            # add signal to map from signal names to expression nodes
            signal_name = expression.get_signal_name()
            if signal_name not in self._monitor._signals_to_expression_nodes:
                self._monitor._signals_to_expression_nodes[signal_name] = [self]
            else:
                self._monitor._signals_to_expression_nodes[expression.get_signal_name()].append(self)

    def set_measurement_location(self, module_name, line_number):
        self._module_name = module_name
        self._line_number = line_number

    def get_measurement_location(self):
        return self._module_name, self._line_number

    def evaluate(self, measurement=None, module_name=None, line_number=None):
        """
        Depending on the type of expression held, if the child node has been replaced by a value,
        evaluate this expression and replace the expression with the new value.
        """
        if self.get_value() is not None:
            # if a value is already set, no need to evaluate further down the tree
            return
        if type(self._subformula) is SignalAtTimestamp:
            # get the child node
            child_node = self.get_children()[0]
            # evaluate the child node
            child_node.evaluate()
            # check the child node for a value
            child_value = child_node.get_value()
            if child_value:
                # set the value of this expression node to be the value
                # of the signal at the timestamp set by the child
                event_dictionary =\
                    self._monitor.get_signal_at_time(self.get_subformula().get_signal_name(), child_value)
                if event_dictionary:
                    self.set_value(event_dictionary["value"])
                else:
                    pass
        elif type(self._subformula) is TimestampExpressionWithAddition:
            # get the child node
            child_node = self.get_children()[0]
            # evaluate the child node
            child_node.evaluate()
            # check the child node for a value
            child_value = child_node.get_value()
            if child_value:
                # derive the arithmetic sequence and apply it
                arithmetic_sequence = self.get_subformula().derive_arithmetic_sequence()
                final_value = child_value
                for f in arithmetic_sequence:
                    final_value = f(final_value)
                self.set_value(final_value)
        elif type(self._subformula) is TimestampVariable:
            variable_name = self._subformula.get_name()
            if variable_name in self._binding:
                # set the value
                self.set_value(self._binding[variable_name])
                # remove this node from the map used during monitoring
                # self._monitor._atom_subatom_nodes[self._atom_index][self._subatom_index].remove(self)
        elif type(self._subformula) in [ValueInConcreteState,
                                        TimeOfConcreteState,
                                        TimeOfTransition,
                                        DurationOfTransition]:
            # if no value exists, assign the measurement given as the new value
            if self.get_value() is None:
                self.set_value(measurement)
                self.set_measurement_location(module_name, line_number)
                # remove this node from the map used during monitoring
                # self._monitor._atom_subatom_nodes[self._atom_index][self._subatom_index].remove(self)
        elif type(self._subformula) is MeasurementVariable:
            # if no value exists, assign the measurement given as the new value
            if not self.get_value():
                # the value to assign is the value held by the binding
                # under the variable with id the same as that held by MeasurementVariable
                quantifier_id = self._subformula.get_name()
                measurement_from_binding = self._binding[quantifier_id]
                self.set_value(measurement_from_binding)
                # remove this node from the map used during monitoring
                # self._monitor._atom_subatom_nodes[self._atom_index][self._subatom_index].remove(self)


class MonitorTreeVariableNode(MonitorTreeNode):
    """
    Class representing a node in a tree that holds a variable found in an atom.
    """

    def evaluate(self):
        """
        Check whether the variable represented by this instance is given a value by `binding`.
        If so, return the value given by the binding.
        """
        variable_name = self._subformula.get_name()
        if variable_name in self._binding:
            # set the value
            self._value = self._binding[variable_name]

class MonitorTreeQuantifierNode(MonitorTreeNode):
    """
    Class representing a node in a monitoring tree that holds a quantifier.
    """

    def __init__(self, quantifier, binding, monitor):
        # superclass call
        super().__init__(quantifier, binding, monitor)
        # update map from quantifier ids to nodes
        self.quantifier_id = quantifier.get_id()
        if self.quantifier_id in self._monitor.quantifier_id_to_nodes:
            self._monitor.quantifier_id_to_nodes[self.quantifier_id].append(self)
        else:
            self._monitor.quantifier_id_to_nodes[self.quantifier_id] = [self]
        # if the quantifier is over timestamps, add to the monitor's list
        if type(quantifier.get_predicate()) is inTimeInterval:
            self._monitor._nodes_with_timestamp_quantifiers.append(self)

    def set_sub_expression_value(self, value, sub_expression_index):
        """
        Set the quantifier's predicate's subexpression at index `sub_expression_index` to `value`.
        """
        self._subformula.set_sub_expression_value(value, sub_expression_index)

    def check_satisfaction(self, event_dict):
        """
        Check to see whether `event_dict` satisfies the predicate of the quantifier held by this node.

        This always involved checking the timestamp.  For signals, this is the only thing that we currently
        constrain with predicates in quantifiers.  For source code, while the predicate places constraints over
        the variable changed or function called, this is checked during instrumentation and so the only thing
        we need to check during monitoring is that the timestamp constraint (if there) is satisfied.
        """
        # check for type of event - either trigger or signal
        if event_dict["type"] == "trigger":
            # we have a trigger placed during static analysis of source code so, if the predicate
            # held by this node places a constraint on the timestamp, check it
            if self._subformula.get_predicate().get_after_timestamp():
                # there is a timestamp
                return self.get_subformula().get_predicate().check_satisfaction(event_dict["time"])
            else:
                # no timestamp constraint, so the existence of a trigger implies satisfaction
                return True
        elif event_dict["type"] == "signal":
            # decide whether the timestamp of the signal falls
            timestamp = event_dict["time"]
            predicate = self._subformula.get_predicate()
            # check for satisfaction
            return predicate.check_satisfaction(timestamp)

    def add_branch(self, event_dict):
        """
        This is called in the case that a trigger is observed for a quantifier.
        """
        # instantiate subformula
        argument_dict = construct_cumulative_binding(self._subformula)
        subformula_instance = self._subformula.get_subformula()(argument_dict)
        # if we have an exists, only add a new branch if the quantifier is not true
        # if we have a forall, only add a new branch if the quantifier is not false

        #REMOVE not adding branches
        # if (not(type(self.get_subformula()) is exists and self.get_value() is True) and
        #         not(type(self.get_subformula()) is forall and self.get_value() is False)):
        # extend self._binding with the value key from event_dict
        # first, copy
        subtree_binding = {}
        for key in self._binding:
            subtree_binding[key] = self._binding[key]
        # update
        if type(self._subformula.get_predicate()) in [changes, calls]:
            # for concrete states and transitions, we don't use the value of individual variables
            # during monitoring - the static counterpart of the value is only used during instrumentation
            subtree_binding[self._subformula.get_id()] = event_dict["time"]
        else:
            # for signals, we actually use the value of the variable
            subtree_binding[self._subformula.get_id()] = event_dict["time"]
        # check for subformula being a Boolean constant
        # if this is the case, we immediately evaluate upwards with the truth value given by the boolean constant
        # if the new node doesn't contain a boolean constant, we recurse
        if type(subformula_instance) is BooleanConstant:
            # check the type of the current quantifier
            if type(self.get_subformula()) is forall and subformula_instance.get_value() is False:
                # set value to False and evaluate upwards
                self.set_value(False)
                self.evaluate_upwards()
            elif type(self.get_subformula()) is exists and subformula_instance.get_value() is True:
                # set value to True and evaluate upwards
                self.set_value(True)
                self.evaluate_upwards()
        else:
            # add subtree with new binding
            self.expand_subtree(subformula_instance, self, subtree_binding)

    def expand_subtree(self, subformula, parent_node, binding, atom_index=None, subatom_index=None):
        """
        Traverse the subformula rooted at the quantifier held by this node in order to construct the subtree.

        If we encounter a quantifier, we add a provisional subtree that doesn't yet have an extended binding.
        """
        if type(subformula) in [forall, exists]:
            # instantiate new node
            new_node = MonitorTreeQuantifierNode(subformula, binding, self._monitor)
            # add the node as a child
            parent_node.add_child(new_node)
            # expand the subformula with a partial binding (nothing has actually been observed
            # for this quantifier yet)
            argument_dict = construct_cumulative_binding(subformula)
            subformula_instance = subformula.get_subformula()(argument_dict)
            # copy the binding
            subtree_binding = {}
            for key in binding:
                subtree_binding[key] = binding[key]
            # expand the subtree, rooted at the quantifier
            self.expand_subtree(subformula_instance, new_node, subtree_binding)
        elif type(subformula) is conjunction:
            # instantiate a new node
            new_node = MonitorTreeConjunctionNode(subformula, binding, self._monitor)
            # add as child
            parent_node.add_child(new_node)
            # recurse on each subformula of the conjunction, adding a child to the new node we just generated
            for conjunct in subformula.get_subformulae():
                self.expand_subtree(conjunct, new_node, binding)
        elif type(subformula) is disjunction:
            # instantiate a new node
            new_node = MonitorTreeDisjunctionNode(subformula, binding, self._monitor)
            # add as child
            parent_node.add_child(new_node)
            # recurse on each subformula of the disjunction, adding a child to the new node we just generated
            for conjunct in subformula.get_subformulae():
                self.expand_subtree(conjunct, new_node, binding)
        elif type(subformula) is negate:
            # instantiate a new node
            new_node = MonitorTreeNegateNode(subformula, binding, self._monitor)
            # add as child
            parent_node.add_child(new_node)
            # recurse on the negation's subformula
            self.expand_subtree(subformula.get_subformula(), new_node, binding)
        elif is_normal_atom(subformula) or is_mixed_atom(subformula):
            # get atom index
            atoms = self._monitor._monitoring_tree._subformula.get_atoms()
            atom_index = atoms.index(subformula)
            # instantiate a new node
            new_node = MonitorTreeAtomNode(subformula, binding, self._monitor, atom_index)
            # add atom to monitor map
            self._monitor.atom_index_to_node[atom_index] = new_node
            # add as child
            parent_node.add_child(new_node)

            # check for types of the subformula

            if type(subformula) is SignalAtTimestampEqualsNumber:
                self.expand_subtree(subformula.get_expression(0), new_node, binding, atom_index, 0)

            elif type(subformula) is SignalAtTimestampLessThanNumber:
                self.expand_subtree(subformula.get_expression(0), new_node, binding, atom_index, 0)

            elif type(subformula) is SignalAtTimestampGreaterThanNumber:
                self.expand_subtree(subformula.get_expression(0), new_node, binding, atom_index, 0)

            elif type(subformula) is TimeBetweenLessThanConstant:
                time_between_expression = subformula.get_time_between_expression()
                expressions = [
                    time_between_expression.get_lhs_expression(),
                    time_between_expression.get_rhs_expression()
                ]
                for (subatom_index, expression) in enumerate(expressions):
                    if TimestampExpression in type(expression).__bases__:
                        # if we're dealing with a timestamp expression, we construct the child node as normal
                        self.expand_subtree(expression, new_node, binding, atom_index, subatom_index)
                    else:
                        # if we're dealing with a concrete state expression,
                        # we wrap the expression in a TimeOfConcreteState object,
                        # so that evaluation of the child node will result in the time entry
                        # in the relevant measurement being taken
                        self.expand_subtree(
                            TimeOfConcreteState(expression), new_node, binding, atom_index, subatom_index
                        )

            elif type(subformula) in [ValueInConcreteStateEqualToConstant,
                                      ValueInConcreteStateLessThanConstant,
                                      ValueInConcreteStateGreaterThanConstant,
                                      ValueInConcreteStateNotEqualToConstant,
                                      ValueInConcreteStateLessThanEqualToConstant,
                                      ValueInConcreteStateGreaterThanEqualToConstant]:
                self.expand_subtree(subformula.get_value_expression(), new_node, binding, atom_index, 0)

            elif type(subformula) is DurationOfTransitionLessThanNumber:
                self.expand_subtree(subformula.get_duration_expression(), new_node, binding, atom_index, 0)

        elif type(subformula) is SignalAtTimestamp:
            # instantiate a new node
            new_node = MonitorTreeExpressionNode(subformula, binding, self._monitor, atom_index, 0)
            # add as child
            parent_node.add_child(new_node)
            self.expand_subtree(subformula.get_timestamp(), new_node, binding, atom_index, 0)
        elif type(subformula) is TimestampExpressionWithAddition:
            # instantiate a new node
            new_node = MonitorTreeExpressionNode(subformula, binding, self._monitor, atom_index, 0)
            # add as child
            parent_node.add_child(new_node)
            # recurse on the structure of the expression
            self.expand_subtree(subformula.get_timestamp_expression(), new_node, binding, atom_index, 0)
        elif type(subformula) is TimestampVariable:
            # recursive base case
            # instantiate a new node
            new_node = MonitorTreeVariableNode(subformula, binding, self._monitor)
            # add as child
            parent_node.add_child(new_node)
        elif type(subformula) in [ConcreteStateBeforeTransition,
                                  ConcreteStateAfterTransition,
                                  ValueInConcreteState,
                                  TimeOfConcreteState,
                                  DurationOfTransition,
                                  TimeOfTransition]:
            # recursive base case
            # instantiate a new node
            # since it's the recursive base case, we count this node as a leaf
            new_node = MonitorTreeExpressionNode(subformula,
                                                 binding,
                                                 self._monitor,
                                                 atom_index,
                                                 subatom_index,
                                                 is_leaf=True)
            # add as child
            parent_node.add_child(new_node)

    def evaluate(self):
        """
        Recurse down the structure of the tree from this node, substituting measurements and deriving
        truth values where possible.
        """
        if type(self.get_subformula()) is forall:
            final_value = self.get_value() if self.get_value() else True
            for child in self.get_children():
                if not child.get_value():
                    child.evaluate()
                    final_value = final_value and child.get_value()
            self.set_value(final_value)
        elif type(self.get_subformula()) is exists:
            if self.get_value() is not True:
                final_value = False
                for child in self.get_children():
                    child.evaluate()
                    final_value = final_value or child.get_value()
                self.set_value(final_value)
                # exists is not allowed to be False until the end of the trace,
                # so check and revert to None if this is the case
                if self.get_value() is False:
                    self.set_value(None)
                # if the exists is true now, remove it from self._monitor._nodes_with_timestamp_quantifiers
                # (if it's in there)
                if self in self._monitor._nodes_with_timestamp_quantifiers and self.get_value() is True:
                    self._monitor._nodes_with_timestamp_quantifiers.remove(self)
                # if true, remove the quantifier from the list of quantifiers
                # to which branches can be added
                if self.get_value() is True:
                    if self in self._monitor.quantifier_id_to_nodes[self.quantifier_id]:
                        self._monitor.quantifier_id_to_nodes[self.quantifier_id].remove(self)
        elif type(self.get_subformula()) is using:
            if self.get_value() is None:
                self.set_value(self.get_children()[0].get_value())
                if self in self._monitor.quantifier_id_to_nodes[self.quantifier_id]:
                    self._monitor.quantifier_id_to_nodes[self.quantifier_id].remove(self)

class Monitor():
    """
    Class representing a monitor that wraps a tree, recursively constructed using MonitorTreeNode instances.
    """

    def __init__(self, specification_instance, tree_evaluation_strategy="up"):
        # store spec instance
        self._specification = specification_instance
        # store the tree evaluation strategy
        self._tree_evaluation_strategy = tree_evaluation_strategy
        # initialise empty list of all nodes
        self._all_nodes = []
        # initialise a map atom index -> subatom index -> nodes
        self._atom_subatom_nodes = {}
        # initialise a map from quantifier ids to nodes in the tree
        self.quantifier_id_to_nodes = {}
        # initialise a map from atom indices to nodes in the tree
        self.atom_index_to_node = {}
        # initialise a list of quantifiers whose predicates concern timestamps
        self._nodes_with_timestamp_quantifiers = []
        # initialise map from signals to expression nodes
        self._signals_to_expression_nodes = {}
        # initialise the map from signal names to timestamps to event dictionaries
        self.signal_map = {}
        # set the root to be a quantifier node (at the moment, we assume specifications start with a quantifier)
        self._monitoring_tree = MonitorTreeQuantifierNode(specification_instance, {}, self)
        # initialise a map from each signal to its most recent value
        all_signal_names = specification_instance.get_all_signal_names()
        self._latest_event_map = {}
        for signal_name in all_signal_names:
            self._latest_event_map[signal_name] = None
        # initialise number of events counter
        self._number_of_events_observed = 0
        # initialise list of event processing times
        self._event_processing_times = []
        # initialise empty map from timestamps to line numbers
        # we use this to determine the line number of the trigger that generated a specific entry in a binding
        self._timestamp_to_line_number = {}

    def __sizeof__(self):
        return sum(map(sys.getsizeof, self._all_nodes))

    def get_measurements_for_db(self):
        """
        Construct a list of dictionaries that model instances of atomic constraints in the final monitoring tree.

        Each dictionary has the form:

        {
        "truth_value": ...,
        "atomic_contraint_index": ...,
        "binding": ...,
        "measurements": [
            {
                "measurement_value": ...,
                "module_name": ...,
                "line_number": ...
            }
        ]
        }

        Note: in modelling the measurements for an atomic constraint with a list,
        we assume that the order of measurements corresponds to the order of expression indices
        in the specification
        """
        # initialise an empty list that we'll populate with dictionaries
        final_list = []
        # get all atoms
        atoms = self._specification.get_atoms()
        # iterate over atoms
        for atomic_constraint_index, atom in enumerate(atoms):
            # get all bindings and values for this atom
            binding_value_location_truth_value_tuples = self.get_bindings_and_values_for_atom(atom)
            # iterate over binding/value/location tuples
            for binding_value_location_truth_value_tuple in binding_value_location_truth_value_tuples:
                binding = binding_value_location_truth_value_tuple[0]
                values = binding_value_location_truth_value_tuple[1]
                measurement_locations = binding_value_location_truth_value_tuple[2]
                truth_value = binding_value_location_truth_value_tuple[3]

                # initialise dictionary to add to final_list
                new_dictionary = {
                    "truth_value": truth_value,
                    "atomic_constraint_index": atomic_constraint_index,
                    "binding": binding,
                    "measurements": []
                }

                # populate the list of measurements
                for (value, location) in zip(values, measurement_locations):
                    new_dictionary["measurements"].append({
                        "measurement_value": value,
                        "module_name": location[0],
                        "line_number": location[1]
                    })

                # add dictionary to list
                final_list.append(new_dictionary)

        return final_list

    def get_measurements_dictionary(self):
        """
        Construct enhanced verdict (atomic constraint -> bindings -> measurements)
        """
        # initialise final dictionary to be populated
        measurements_dictionary = {}
        atoms = self._specification.get_atoms()
        # iterate over atoms
        for atom in atoms:
            # get all the bindings in the monitoring tree at which this atomic constraint was found
            # and get the values
            binding_value_line_number_tuples = self.get_bindings_and_values_for_atom(atom)
            # group bindings by line numbers
            line_number_sequence_to_binding_value_pair = {}
            for binding_value_line_number_tuple in binding_value_line_number_tuples:
                binding = binding_value_line_number_tuple[0]
                values = binding_value_line_number_tuple[1]
                measurement_location = binding_value_line_number_tuple[2]
                # extract timestamps from binding (since it's a map from indices to timestamps)
                timestamps = []
                for entry in binding:
                    timestamps.append(binding[entry])
                # convert timestamps to line numbers
                binding_line_numbers = tuple(
                    map(lambda timestamp: self.get_line_number_from_timestamp(timestamp), timestamps))
                if binding_line_numbers in line_number_sequence_to_binding_value_pair:
                    line_number_sequence_to_binding_value_pair[binding_line_numbers].append(
                        (timestamps, values, measurement_location))
                else:
                    line_number_sequence_to_binding_value_pair[binding_line_numbers] = [
                        (timestamps, values, measurement_location)]

            # iterate through line numbers -> timestamps structure
            for line_number_sequence in line_number_sequence_to_binding_value_pair:
                line_number_string = ", ".join(map(lambda line_number: f"line {line_number}", line_number_sequence))
                print(f"  checks triggered by {line_number_string}")
                for timestamp_sequence, values, measurement_location in line_number_sequence_to_binding_value_pair[
                    line_number_sequence]:
                    value_line_number_pairs = list(zip(values, measurement_location))
                    for value, measurement_location in value_line_number_pairs:
                        module_name, line_number = measurement_location
                        print(f"      {value} ({module_name} @ {line_number})")
            return measurements_dictionary

    def get_line_number_from_timestamp(self, timestamp):
        return self._timestamp_to_line_number[timestamp]

    def get_bindings_and_values_for_atom(self, atomic_constraint):
        """
        Recurse on the monitoring tree to find all occurrences of the given atomic constraint.
        In each case, record the binding, value, and line number.
        """
        # initialise list of relevant bindings
        relevant_bindings = []
        # initialise list of values
        relevant_values = []
        # initialise list of measurement locations (module name and line number pair)
        relevant_measurement_locations = []
        # initialise list of relevant truth values
        relevant_truth_values = []
        # set current node to the root node
        current_node = self._monitoring_tree
        # recurse
        self._get_bindings_and_values_for_atom(atomic_constraint, current_node, relevant_bindings,
                                               relevant_values, relevant_measurement_locations, relevant_truth_values)
        return list(zip(relevant_bindings, relevant_values, relevant_measurement_locations, relevant_truth_values))

    def _get_bindings_and_values_for_atom(self, atomic_constraint, current_node, relevant_bindings,
                                          relevant_values, relevant_measurement_locations, relevant_truth_values):
        """
        Either take the binding from the current node (if it contains the atomic constraint given),
        or recurse.
        """
        # base case - see if current_node holds atomic_constraint
        if type(current_node) is not MonitorTreeAtomNode:
            # recurse on children
            for child in current_node.get_children():
                self._get_bindings_and_values_for_atom(atomic_constraint, child, relevant_bindings,
                                                       relevant_values, relevant_measurement_locations,
                                                       relevant_truth_values)
        else:
            # recursive case
            # we have found an atom, so check its subformula
            if current_node.get_subformula() == atomic_constraint:
                # add binding to list
                relevant_bindings.append(current_node.get_binding())
                # add value to list
                child_values = list(map(lambda child : child.get_value(), current_node.get_children()))
                relevant_values.append(child_values)
                # add code locations to list
                child_measurement_locations =\
                    list(map(lambda child : child.get_measurement_location(), current_node.get_children()))
                relevant_measurement_locations.append(child_measurement_locations)
                # add truth values to list
                relevant_truth_values.append(current_node.get_value())


    def wrap_up(self):
        # resolve the monitoring tree if it has no truth value
        if self.get_verdict() is None:
            self.resolve_monitoring_tree()

    def get_number_of_events_observed(self):
        return self._number_of_events_observed

    def get_verdict(self):
        return self._monitoring_tree.get_value()

    def get_verdict_explanation(self) -> str:
        message_substrings: typing.List[str] = ["VALUES RECORDED:\n"]

        # NOTE: this enhanced verdict code assumes that nesting of quantifiers goes in a straight line
        # if we had a formula with something like ((exists...) and (exists...)), this may break
        # it's done like this because we've never had a formula like the above, so for now this is fine
        # print enhanced verdict (atomic constraint -> bindings -> measurements)
        atoms = self._specification.get_atoms()
        # iterate over atoms
        for atom in atoms:
            message_substrings.append(str(atom))
            # get all the bindings in the monitoring tree at which this atomic constraint was found
            # and get the values
            binding_value_line_number_tuples = self.get_bindings_and_values_for_atom(atom)
            # group bindings by line numbers
            line_number_sequence_to_binding_value_pair = {}
            for binding_value_line_number_tuple in binding_value_line_number_tuples:
                binding = binding_value_line_number_tuple[0]
                values = binding_value_line_number_tuple[1]
                measurement_location = binding_value_line_number_tuple[2]
                # extract timestamps from binding (since it's a map from indices to timestamps)
                timestamps = []
                for entry in binding:
                    timestamps.append(binding[entry])
                # convert timestamps to line numbers
                binding_line_numbers = tuple(
                    map(lambda timestamp: self.get_line_number_from_timestamp(timestamp), timestamps))
                if binding_line_numbers in line_number_sequence_to_binding_value_pair:
                    line_number_sequence_to_binding_value_pair[binding_line_numbers].append(
                        (timestamps, values, measurement_location))
                else:
                    line_number_sequence_to_binding_value_pair[binding_line_numbers] = [
                        (timestamps, values, measurement_location)]

            # iterate through line numbers -> timestamps structure
            for line_number_sequence in line_number_sequence_to_binding_value_pair:
                line_number_string = ", ".join(map(lambda line_number: f"line {line_number}", line_number_sequence))
                message_substrings.append(f"  checks triggered by {line_number_string}")
                for timestamp_sequence, values, measurement_location in line_number_sequence_to_binding_value_pair[
                    line_number_sequence]:
                    value_line_number_pairs = list(zip(values, measurement_location))
                    for value, measurement_location in value_line_number_pairs:
                        module_name, line_number = measurement_location
                        message_substrings.append(f"      {value} ({module_name} @ {line_number})")

        return '\n'.join(message_substrings)


    def get_tree_size(self):
        return len(self._all_nodes)

    def get_tree_evaluation_strategy(self):
        return self._tree_evaluation_strategy

    def resolve_monitoring_tree(self, current_node=None):
        """
        Recurse on the structure of the monitoring tree, assigning a truth value to any node without one.
        """
        # if None, set current_node to root
        current_node = self._monitoring_tree if not current_node else current_node
        # follow this path through the tree if we have no truth value
        if current_node.get_value() is None:
            if type(current_node) is MonitorTreeQuantifierNode:
                if type(current_node.get_subformula()) is forall:
                    # check for no children (so, one child, but with a limited binding)
                    quantifier_id = current_node.get_subformula().get_id()
                    if (len(current_node.get_children()) == 1
                            and quantifier_id not in current_node.get_children()[0].get_binding()):
                        # in this case, set the forall to True
                        final_truth_value = True
                    else:
                        # recurse on subtrees
                        final_truth_value = True
                        for child in current_node.get_children():
                            final_truth_value = final_truth_value and self.resolve_monitoring_tree(child)
                elif type(current_node.get_subformula()) is exists:
                    # recurse on subtrees
                    final_truth_value = False
                    for child in current_node.get_children():
                        final_truth_value = final_truth_value or self.resolve_monitoring_tree(child)
            elif type(current_node) is MonitorTreeConjunctionNode:
                # recurse on subtrees
                final_truth_value = True
                for child in current_node.get_children():
                    final_truth_value = final_truth_value and self.resolve_monitoring_tree(child)
            elif type(current_node) is MonitorTreeDisjunctionNode:
                # recurse on subtrees
                final_truth_value = False
                for child in current_node.get_children():
                    final_truth_value = final_truth_value or self.resolve_monitoring_tree(child)
            elif type(current_node) is MonitorTreeNegateNode:
                # recurse on subtree
                final_truth_value = self.resolve_monitoring_tree(current_node.get_children()[0])
                # current_node.set_value(final_truth_value)
            elif type(current_node) is MonitorTreeAtomNode:
                if type(current_node.get_subformula()) is not BooleanConstant:
                    # an atom has no truth value because the quantity that it constrained was never observed
                    # for now, assume a 'weak' notion of truth and set it to True
                    final_truth_value = True
                else:
                    final_truth_value = current_node.get_subformula().get_value()
            # set the final truth value of the node
            current_node.set_value(final_truth_value)
        else:
            # the node already has a truth value, so use that
            final_truth_value = current_node.get_value()
        return final_truth_value

    def process_event(self, event):
        """
        Given `event`, assumed to be a dictionary, transform `self._monitoring_tree`,
        perform the relevant monitoring actions.
        """
        # take first measurement for event processing time
        event_processing_start_time = timeit.default_timer()

        # increment number of events counter
        self._number_of_events_observed += 1

        # update the most recent event map
        if event["type"] == "signal":
            self._latest_event_map[event["signal_name"]] = event

        # check the type of the event
        if event["type"] == "signal":
            # find quantifiers whose predicate concerns timestamps, and check whether
            # this event satisfies their predicates

            for quantifier_node in self._nodes_with_timestamp_quantifiers:
                satisfied = quantifier_node.check_satisfaction(event)
                if satisfied:
                    # if there is just a single child branch, check its binding
                    # if its binding should be extended then, rather than adding a new branch,
                    # we extend the binding of the existent one
                    children = quantifier_node.get_children()
                    if (len(children) == 1 and
                            (quantifier_node.get_subformula().get_id() not in
                                quantifier_node.get_children()[0].get_binding())):
                        # extend the binding of the entire subtree
                        quantifier_node.get_children()[0].update_subtree_binding(
                            {
                                quantifier_node.get_subformula().get_id(): event["time"]
                            }
                        )
                    else:
                        # get list of atoms
                        atoms = self._monitoring_tree.get_subformula().get_atoms()
                        # get measurements from previous subtree
                        if len(quantifier_node.get_children()) > 0:
                            measurements = quantifier_node.get_children()[-1].extract_measurements_from_subtree(
                                atoms,
                                quantifier_node.get_subformula().get_id()
                            )
                        else:
                            measurements = {}

                        # add a new branch to the quantifier node whose quantifier captures this event
                        quantifier_node.add_branch(event)
                        # update the branch with the measurements extracted from the old branch
                        if len(measurements) != 0:
                            quantifier_node.update_newest_branch(atoms, measurements)


            # iterate through expression nodes associated with this signal
            if event["signal_name"] in self._signals_to_expression_nodes:
                # iterate over copy
                for expression_node in self._signals_to_expression_nodes[event["signal_name"]][:]:
                    # evaluate the parts of the tree that can be evaluated using the value
                    # generated by the quantifier on the new branch
                    expression_node.evaluate_upwards()
                    # if the expression node now has a value, remove it from the list of nodes for this signal
                    if expression_node.get_value() is not None:
                        self._signals_to_expression_nodes[event["signal_name"]].remove(expression_node)

        elif event["type"] == "trigger":
            # add an entry in the map from timestamps to line numbers
            self._timestamp_to_line_number[event["time"]] = event["line_number"]
            # find quantifiers with the quantifier id held by this trigger
            quantifier_id = event["quantifier_id"]
            quantifier_nodes = self.quantifier_id_to_nodes[quantifier_id]
            # add a branch to each of these nodes
            for node in quantifier_nodes:
                children = node.get_children()
                if (len(children) == 1 and
                        (node.get_subformula().get_id() not in
                         node.get_children()[0].get_binding())):
                    # extend the binding of the entire subtree
                    node.get_children()[0].update_subtree_binding(
                        {
                            node.get_subformula().get_id(): event["time"]
                        }
                    )
                else:
                    # get list of atoms
                    atoms = self._monitoring_tree.get_subformula().get_atoms()
                    # get measurements from previous subtree
                    if len(node.get_children()) > 0:
                        measurements = node.get_children()[-1].extract_measurements_from_subtree(
                            atoms,
                            node.get_subformula().get_id()
                        )
                    else:
                        measurements = {}

                    if node.check_satisfaction(event):
                        # add a new branch to the quantifier node whose quantifier captures this event
                        node.add_branch(event)
                        # update the branch with the measurements extracted from the old branch
                        if len(measurements) != 0:
                            node.update_newest_branch(atoms, measurements)
        elif event["type"] == "measurement":
            # find the nodes with the atom and subatom indices matching this measurement
            # and set their values with that given by this measurement
            atom_index = event["atom_index"]
            subatom_index = event["subatom_index"]
            measurement = event["value"]
            module_name = event["module_name"]
            line_number = event["line_number"]
            nodes = self._atom_subatom_nodes[atom_index][subatom_index]
            for n, node in enumerate(nodes):
                # add the measurement to the node
                node.evaluate(measurement, module_name, line_number)
                if self.get_tree_evaluation_strategy() == "up":
                    # evaluate upwards from the node
                    node.evaluate_upwards()
            # check for downwards evaluation
            if self.get_tree_evaluation_strategy() == "down":
                self._monitoring_tree.evaluate()
            # empty the list, since we have now given values to these expressions
            self._atom_subatom_nodes[atom_index][subatom_index] = []
        elif event["type"] == "quantifier-expression":
            # find quantifiers with the quantifier id held by this trace event
            quantifier_id = event["quantifier_id"]
            quantifier_nodes = self.quantifier_id_to_nodes[quantifier_id]
            # update the subexpression of each quantifier node with the value given by this trace event
            sub_expression_index = event["sub_expression_index"]
            value = event["time"]
            for node in quantifier_nodes:
                if type(node.get_subformula().get_predicate()) is inTimeInterval:
                    node.set_sub_expression_value(value, sub_expression_index)
                elif type(node.get_subformula().get_predicate()) in [changes, calls]:
                    node.get_subformula().get_predicate().set_after_timestamp(value)
        elif event["type"] == "function":
            # find the nodes with the atom and subatom indices matching this measurement
            # and set their values with that given by this measurement
            atom_index = event["atom_index"]
            measurement = event["value"]
            module_name = event["module_name"]
            line_number = event["line_number"]
            # functions are not realted to subatoms so we put by default subatom index = 0
            nodes = self._atom_subatom_nodes[atom_index][0]
            for n, node in enumerate(nodes):
                # add the measurement to the node
                node.evaluate(measurement, module_name, line_number)
                if self.get_tree_evaluation_strategy() == "up":
                    # evaluate upwards from the node
                    node.evaluate_upwards()
            # check for downwards evaluation
            if self.get_tree_evaluation_strategy() == "down":
                self._monitoring_tree.evaluate()
            # empty the list, since we have now given values to these expressions
            self._atom_subatom_nodes[atom_index][0] = []

        # take second measurement for the time taken to process the event
        event_processing_end_time = timeit.default_timer()
        # compute time taken
        event_processing_time_taken = event_processing_end_time - event_processing_start_time
        # append to list
        self._event_processing_times.append(event_processing_time_taken)

        # self.write_tree_to_file(f"{self.get_number_of_events_observed()}.gv")

    def get_event_processing_times(self):
        """
        Get the list of event processing times constructed during monitoring.

        Assumes monitoring has taken place.
        """
        return self._event_processing_times

    def get_signal_at_time(self, signal_name, timestamp):
        """
        Assume `timestamp` is a float, and get the value of the signal `signal_name` at time `timestamp`.
        To do this, look at self._latest_event_map for the relevant signal name.
        If the signal entry there has timestamp >= the given timestamp,
        use it as the value of the signal at the given timestamp (this way, we interpolate by looking at the
        closest value available to a timestamp in the future).
        """
        # get the signal entry held in the most recent event map
        most_recent_signal_entry = self._latest_event_map[signal_name]
        if most_recent_signal_entry:
            if most_recent_signal_entry["time"] >= timestamp:
                return most_recent_signal_entry

    def write_tree_to_file(self, filename):
        """
        Write the state of the monitoring tree to a dot file.
        """
        graph = graphviz.Digraph()
        graph.attr("graph", splines="true", fontsize="10")
        shape = "rectangle"
        # construct a node in the graph for each node in the tree
        for node in self._all_nodes:
            if hasattr(node, "_atom_index") and node._atom_index is not None:
                if hasattr(node, "_subatom_index") and node._subatom_index is not None:
                    pair = (node._atom_index, node._subatom_index)
                else:
                    pair = (node._atom_index,)
            else:
                pair = ""
            graph.node(
                str(id(node)),
                f"{node.get_subformula()}\n{node.get_binding()}\n{node.get_value()}\n{pair}",
                shape=shape
            )
        # construct edges
        for node in self._all_nodes:
            for child_node in node.get_children():
                graph.edge(str(id(node)), str(id(child_node)))
        # write to file
        graph.render(filename)


def event_loop(specification, event_queue, monitoring_statistics):
    """
    Starts a while loop that consumes from an event queue.
    The loop stops when it consumes an end signal.
    """
    # configure logging
    # set up the logging directory
    if not os.path.isdir("logs"):
        os.mkdir("logs")

    # (taken from https://stackoverflow.com/questions/6386698/how-to-write-to-a-file-using-the-logging-python-module)
    logging.basicConfig(filename=f"logs/{datetime.datetime.now().isoformat()}",
                        filemode='a',
                        format='[%(asctime)s %(msecs)3d] [%(threadName)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)
    # initialise monitor
    monitor = Monitor(specification)
    # initialise flag to end loop
    end_loop = False
    # loop while we're not told to end the loop
    event_loop_start_time = time.time()
    while not end_loop:
        # consume from the queue
        event = event_queue.get()
        # process the event
        monitor.process_event(event)
        # check for end signal
        if event["type"] == "end":
            # record the end time of the program under scrutiny
            program_end_time = event["time"]
            # set the loop end variable
            end_loop = True
    event_loop_end_time = time.time()
    event_loop_time_taken = event_loop_end_time - event_loop_start_time
    # add to statistics
    monitoring_statistics["event_loop_time_taken"] = event_loop_time_taken
    monitoring_statistics["program_end_time"] = program_end_time

    # resolve the monitoring tree if it has no truth value
    if monitor.get_verdict() is None:
        monitor.resolve_monitoring_tree()

    # compute average event processing time
    event_processing_times = monitor.get_event_processing_times()
    monitoring_statistics["event_processing_time"] = event_processing_times

    # store monitoring statistics
    monitoring_statistics["number_of_events"] = monitor.get_number_of_events_observed()

def combine_verdicts(verdicts: typing.List[typing.Optional[bool]]):
    def combine_two(A, B):
        if A is None or B is None:
            return None
        else:
            return A and B

    return functools.reduce(combine_two, verdicts)