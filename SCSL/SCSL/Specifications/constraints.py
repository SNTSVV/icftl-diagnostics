"""
Module holding classes for constructing constraints to be included in specifications.
"""
import sys

from ..Specifications.predicates import inTimeInterval, changes, calls

def dummy_variable_value_from_quantifier(quantifier):
    """
    Given a quantifier, `quantifier`, instantiate a placeholder
    value to be used in the specification as if it were given by the quantifier
    """
    if type(quantifier.get_predicate()) is inTimeInterval:
        return TimestampVariable(quantifier.get_id())
    elif type(quantifier.get_predicate()) is changes:
        return ConcreteStateVariable(quantifier.get_id())
    elif type(quantifier.get_predicate()) is calls:
        return TransitionVariable(quantifier.get_id())
    else:
        # print((type(quantifier.get_predicate()))
        # we're dealing with a predicate for a 'using' quantifier
        return MeasurementVariable(quantifier.get_id(), quantifier.get_predicate())

def is_measurement(obj):
    """
    Decide whether `obj` represents a measurement being taken (with no constraint).
    """
    return Measurement in type(obj).__bases__

def _is_constraint_base(obj):
    """
    Decide whether obj has ConstraintBase as a base class.
    """
    return ConstraintBase in type(obj).__bases__

def _is_connective(obj):
    """
    Decide whether obj is a logical connective (and, or, not).
    """
    return type(obj) in [Conjunction, Disjunction, Negation]

def is_complete(obj):
    """
    Decide whether obj is complete, or needs to be completed by further method calls.
    """
    return _is_connective(obj) or _is_constraint_base(obj)

def is_normal_atom(obj):
    """
    Decide whether an atomic constraint is normal (it requires only one measurement).
    """
    return NormalAtom in type(obj).__bases__

def is_mixed_atom(obj):
    """
    Decide whether an atomic constraint is mixed (it requires multiple measurements).
    """
    return MixedAtom in type(obj).__bases__

def derive_sequence_of_temporal_operators(obj) -> dict:
    """
    Traverse the structure of the given atomic constraint in order to determine the sequence
    of temporal operators used.
    """
    # initialise map from subatom index to sequence of temporal operators
    # check whether the atomic constraint given is normal or mixed
    if is_mixed_atom(obj):
        # mixed atomic constraint case
        return {
            0: _derive_sequence_of_temporal_operators(obj.get_lhs_expression()),
            1: _derive_sequence_of_temporal_operators(obj.get_rhs_expression())
        }
    else:
        return {
            0: _derive_sequence_of_temporal_operators(obj)
        }

def _derive_sequence_of_temporal_operators(obj) -> list:
    """
    Traverse the structure of the given atomic constraint.  This function is called by
    derive_sequence_of_temporal_operators in order to generate either 1 or 2 sequences
    of temporal operators (1 for normal case, 2 for mixed case).
    """
    # initialise empty sequence of temporal operators
    temporal_operator_sequence = []
    # initialise the current object to be used during the traversal
    current_obj = obj
    # traverse the structure of current_obj until we reach a variable
    while type(current_obj) not in [ConcreteStateVariable, TransitionVariable, TimestampVariable]:
        # check the type of current_obj
        # we only add to the temporal operator sequence in certain cases
        if type(current_obj) in [ValueInConcreteStateEqualToConstant,
                                 ValueInConcreteStateLessThanConstant,
                                 ValueInConcreteStateGreaterThanConstant,
                                 ValueInConcreteStateNotEqualToConstant,
                                 ValueInConcreteStateLessThanEqualToConstant,
                                 ValueInConcreteStateGreaterThanEqualToConstant]:
            current_obj = current_obj.get_value_expression()

        elif type(current_obj) is ValueInConcreteStateWithAddition:
            current_obj = current_obj.get_value_expression()
        
        elif type(current_obj) in [SignalAtTimestampGreaterThanNumber,
                                   SignalAtTimestampEqualsNumber,
                                   SignalAtTimestampLessThanNumber]:
            current_obj = current_obj.get_signal_timestamp_expression().get_timestamp()
        
        elif type(current_obj) in [ConcreteStateBeforeTransition, ConcreteStateAfterTransition]:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_transition()
        
        elif type(current_obj) is ValueInConcreteState:
            current_obj = current_obj.get_concrete_state_expression()

        elif type(current_obj) in [NextConcreteStateAfterConcreteState,
                                   NextTransitionAfterConcreteState]:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_concrete_state_expression()

        elif type(current_obj) in [NextConcreteStateAfterTransition,
                                   NextTransitionAfterTransition]:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_transition_expression()

        elif type(current_obj) in [NextConcreteStateAfterTimestamp,
                                   NextTransitionAfterTimestamp]:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_timestamp_expression()

        elif type(current_obj) is TimeOfConcreteState:
            current_obj = current_obj.get_concrete_state_expression()

        elif type(current_obj) is TimeOfTransition:
            current_obj = current_obj.get_transition_expression()

        elif type(current_obj) is TimestampExpressionWithAddition:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_timestamp_expression()

        elif type(current_obj) is DurationOfTransition:
            temporal_operator_sequence.append(current_obj)
            current_obj = current_obj.get_transition_expression()

        elif type(current_obj) is DurationOfTransitionLessThanNumber:
            current_obj = current_obj.get_duration_expression()
    
    # add the variable to the end of the sequence
    temporal_operator_sequence.append(current_obj)
    
    return temporal_operator_sequence

class ConstraintBase():
    """
    Class for representing the root of a combination of constraints.
    """

    def set_binding(self, binding):
        self._binding = binding

class NormalAtom():
    """
    Class representing an atomic constraint for which a single measurement must be taken.
    """

    pass

class MixedAtom():
    """
    Class representing an atomic constraint for which multiple measurements must be taken.
    """

    pass

"""
Classes defining the types of data that can be identified by quantifiers,
and found in bindings.
"""


class Measurement():
    """
    Class to represent any measurement (before a constraint is placed on it).
    """
    pass


class TimestampExpression():
    """
    Class to represent any expression whose value when evaluated will be a timestamp.
    """

    def __add__(self, other):
        return TimestampExpressionWithAddition(self, other)

    def derive_arithmetic_sequence(self):
        # base case for deriving arithmetic sequences
        return []

    def next(self, predicate):
        if type(predicate) is changes:
            return NextConcreteStateAfterTimestamp(self, predicate)
        elif type(predicate) is calls:
            return NextTransitionAfterTimestamp(self, predicate)


class TimestampExpressionWithAddition(TimestampExpression):
    """
    Class to represent a TimestampExpression instance with addition performed.
    """

    def __init__(self, timestamp_expression, number):
        self._timestamp_expression = timestamp_expression
        self._number = number

    def __sizeof__(self):
        return sys.getsizeof(self._timestamp_expression) + sys.getsizeof(self._number)

    def __eq__(self, other):
        return (type(self) is type(other) and
                self._timestamp_expression == other._timestamp_expression and
                self._number == other._number)

    def __repr__(self):
        return f"{self._timestamp_expression} + {self._number}"

    def get_function_names(self):
        return self._timestamp_expression.get_function_names()

    def get_base_variable(self):
        return self._timestamp_expression.get_base_variable()

    def get_number(self):
        return self._number

    def get_timestamp_expression(self):
        return self._timestamp_expression

    def is_signal_based(self):
        return self._timestamp_expression.is_signal_based()

    def derive_arithmetic_sequence(self):
        return [lambda x : x + self._number] + self._timestamp_expression.derive_arithmetic_sequence()


class ConcreteStateExpression():
    """
    Class to represent any expression whose value when evaluated will be a concrete state.
    """

    def __call__(self, program_variable):
        return ValueInConcreteState(self, program_variable)

    def time(self):
        return TimeOfConcreteState(self)

    def next(self, predicate):
        if type(predicate) is changes:
            return NextConcreteStateAfterConcreteState(self, predicate)
        elif type(predicate) is calls:
            return NextTransitionAfterConcreteState(self, predicate)


class TransitionExpression():
    """
    Class to represent any expression whose value when evaluated will be a transition.
    """

    def time(self):
        return TimeOfTransition(self)

    def duration(self):
        return DurationOfTransition(self)

    def before(self):
        return ConcreteStateBeforeTransition(self)

    def after(self):
        return ConcreteStateAfterTransition(self)

    def next(self, predicate):
        if type(predicate) is changes:
            return NextConcreteStateAfterTransition(self, predicate)
        elif type(predicate) is calls:
            return NextTransitionAfterTransition(self, predicate)


class TimestampVariable(TimestampExpression):
    """
    Class to represent a variable holding a timestamp.
    """

    def __init__(self, variable_name):
        """
        Store `variable_name`, the name of the variable that holds the timestamp.
        """
        self._variable_name = variable_name

    def __sizeof__(self):
        return sys.getsizeof(self._variable_name)

    def get_function_names(self):
        return []

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._variable_name == other._variable_name)

    def get_base_variable(self):
        return self
    
    def get_name(self):
        return self._variable_name
    
    def is_signal_based(self):
        return True
    
    def __repr__(self):
        return f"v{self._variable_name}"

class ConcreteStateVariable(ConcreteStateExpression):
    """
    Class to represent a variable holding a concrete state.
    """

    def __init__(self, variable_name):
        """
        Store `variable_name`, the name of the variable that holds the concrete state.
        """
        self._variable_name = variable_name

    def __sizeof__(self):
        return sys.getsizeof(self._variable_name)

    def get_function_names(self):
        return []

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._variable_name == other._variable_name)

    def is_signal_based(self):
        return False

    def get_base_variable(self):
        return self
    
    def get_name(self):
        return self._variable_name
    
    def __repr__(self):
        return f"v{self._variable_name}"

class TransitionVariable(TransitionExpression):
    """
    Class to represent a variable holding a transition.
    """

    def __init__(self, variable_name):
        """
        Store `variable_name`, the name of the variable that holds the transition.
        """
        self._variable_name = variable_name

    def __sizeof__(self):
        return sys.getsizeof(self._variable_name)

    def get_function_names(self):
        return []

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._variable_name == other._variable_name)

    def is_signal_based(self):
        return False

    def get_base_variable(self):
        return self
    
    def get_name(self):
        return self._variable_name
    
    def __repr__(self):
        return f"v{self._variable_name}"


"""
Classes that extend the base Timestamp, ConcreteState and Transition types.
"""

class TimeOfConcreteState(TimestampExpression, Measurement):
    """
    Class to represent time at which a concrete state is attained.
    """

    def __init__(self, concrete_state):
        """
        Store `concrete_state`.
        """
        self._concrete_state = concrete_state

    def __sizeof__(self):
        return sys.getsizeof(self._concrete_state)

    def get_function_names(self):
        return self._concrete_state.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._concrete_state == other._concrete_state)

    def get_base_variable(self):
        return self._concrete_state.get_base_variable()

    def is_signal_based(self):
        return self._concrete_state.is_signal_based()

    def get_concrete_state_expression(self):
        return self._concrete_state

    def get_temporal_operator(self):
        return self.get_concrete_state_expression()

    def __repr__(self):
        return f"{self._concrete_state}.time()"


class TimeOfTransition(TimestampExpression, Measurement):
    """
    Class to represent time at which a transition started.
    """

    def __init__(self, transition):
        """
        Store `transition`.
        """
        self._transition = transition

    def __sizeof__(self):
        return sys.getsizeof(self._transition)

    def get_function_names(self):
        return self._transition.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._transition == other._transition)

    def get_base_variable(self):
        return self._transition.get_base_variable()

    def is_signal_based(self):
        return self._transition.is_signal_based()

    def get_transition_expression(self):
        return self._transition

    def get_temporal_operator(self):
        return self.get_transition_expression()

    def __repr__(self):
        return f"{self._transition}.time()"


def time(expression):
    """
    Depending on the type of `expression`, construct an object representing the timestamp held by a concrete
    state or transition.
    """
    if ConcreteStateExpression in type(expression).__bases__:
        return TimeOfConcreteState(expression)
    elif TransitionExpression in type(expression).__bases__:
        return TimeOfTransition(expression)


class NextConcreteStateAfterTimestamp(ConcreteStateExpression):
    """
    Class to represent the next concrete state after a given timestamp, satisfying a predicate.
    """

    def __init__(self, timestamp, predicate):
        """
        Store `timestamp` and `predicate`.
        """
        self._timestamp = timestamp
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._timestamp) + sys.getsizeof(self._predicate)

    def get_function_names(self):
        return self._timestamp.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._timestamp == other._timestamp and
                self._predicate == other._predicate)

    def get_base_variable(self):
        return self._timestamp.get_base_variable()

    def get_predicate(self):
        return self._predicate

    def get_timestamp_expression(self):
        return self._timestamp

    def is_signal_based(self):
        return self._timestamp.is_signal_based()

    def __repr__(self):
        return f"{self._timestamp}.next({self._predicate})"


class NextTransitionAfterTimestamp(TransitionExpression):
    """
    Class to represent the next transition after a given timestamp, satisfying a predicate.
    """

    def __init__(self, timestamp, predicate):
        """
        Store `timestamp` and `predicate`.
        """
        self._timestamp = timestamp
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._timestamp) + sys.getsizeof(self._predicate)

    def get_function_names(self):
        return self._timestamp.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._timestamp == other._timestamp and
                self._predicate == other._predicate)

    def get_base_variable(self):
        return self._timestamp.get_base_variable()

    def get_predicate(self):
        return self._predicate

    def get_timestamp_expression(self):
        return self._timestamp

    def is_signal_based(self):
        return self._timestamp.is_signal_based()

    def __repr__(self):
        return f"{self._timestamp}.next({self._predicate})"


class NextConcreteStateAfterTransition(ConcreteStateExpression):
    """
    Class to represent the next concrete state after a given transition, satisfying a predicate.
    """

    def __init__(self, transition, predicate):
        """
        Store `transition` and `predicate`.
        """
        self._transition = transition
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._transition) + sys.getsizeof(self._predicate)

    def is_signal_based(self):
        return self._transition.is_signal_based()

    def get_function_names(self):
        return self._transition.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._transition == other._transition and
                self._predicate == other._predicate)

    def get_base_variable(self):
        return self._transition.get_base_variable()

    def get_predicate(self):
        return self._predicate

    def get_transition_expression(self):
        return self._transition

    def __repr__(self):
        return f"{self._transition}.next({self._predicate})"

class NextTransitionAfterTransition(TransitionExpression):
    """
    Class to represent the next transition after a given transition, satisfying a predicate.
    """

    def __init__(self, transition, predicate):
        """
        Store `transition` and `predicate`.
        """
        self._transition = transition
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._transition) + sys.getsizeof(self._predicate)

    def get_function_names(self):
        return self._transition.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._transition == other._transition and
                self._predicate == other._predicate)

    def is_signal_based(self):
        return self._transition.is_signal_based()

    def get_base_variable(self):
        return self._transition.get_base_variable()

    def get_predicate(self):
        return self._predicate

    def get_transition_expression(self):
        return self._transition

    def __repr__(self):
        return f"{self._transition}.next({self._predicate})"

class NextConcreteStateAfterConcreteState(ConcreteStateExpression):
    """
    Class to represent the next concrete state after a given concrete state, satisfying a predicate.
    """

    def __init__(self, concrete_state, predicate):
        """
        Store `concrete_state` and `predicate`.
        """
        self._concrete_state = concrete_state
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._concrete_state) + sys.getsizeof(self._predicate)

    def get_function_names(self):
        return self._concrete_state.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._concrete_state == other._concrete_state and
                self._predicate == other._predicate)

    def get_base_variable(self):
        return self._concrete_state.get_base_variable()

    def is_signal_based(self):
        return self._concrete_state.is_signal_based()

    def get_predicate(self):
        return self._predicate

    def get_concrete_state_expression(self):
        return self._concrete_state

    def __repr__(self):
        return f"{self._concrete_state}.next({self._predicate})"

class NextTransitionAfterConcreteState(TransitionExpression):
    """
    Class to represent the next transition after a given concrete state, satisfying a predicate.
    """

    def __init__(self, concrete_state, predicate):
        """
        Store `concrete_state` and `predicate`.
        """
        self._concrete_state = concrete_state
        self._predicate = predicate

    def __sizeof__(self):
        return sys.getsizeof(self._concrete_state) + sys.getsizeof(self._predicate)

    def is_signal_based(self):
        return self._concrete_state.is_signal_based()

    def get_function_names(self):
        return self._concrete_state.get_function_names() + self._predicate.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._concrete_state == other._concrete_state and
                self._predicate == other._predicate)

    def get_base_variable(self):
        return self._concrete_state.get_base_variable()

    def get_predicate(self):
        return self._predicate

    def get_concrete_state_expression(self):
        return self._concrete_state

    def __repr__(self):
        return f"{self._concrete_state}.next({self._predicate})"

class ConcreteStateBeforeTransition(ConcreteStateExpression):
    """
    Class to represent the concrete state immediately before a transition.
    """

    def __init__(self, transition):
        """
        Store `transition`, assumed to be a `Transition` instance.
        """
        self._transition = transition

    def __sizeof__(self):
        return sys.getsizeof(self._transition)

    def get_function_names(self):
        return self._transition.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._transition == other._transition)

    def get_base_variable(self):
        return self._transition.get_base_variable()
    
    def is_signal_based(self):
        return self._transition.is_signal_based()
    
    def get_transition(self):
        return self._transition
    
    def __repr__(self):
        return f"{self._transition}.before()"

class ConcreteStateAfterTransition(ConcreteStateExpression):
    """
    Class to represent the concrete state immediately after a transition.
    """

    def __init__(self, transition):
        """
        Store `transition`, assumed to be a `Transition` instance.
        """
        self._transition = transition

    def __sizeof__(self):
        return sys.getsizeof(self._transition)

    def get_function_names(self):
        return self._transition.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._transition == other._transition)

    def get_base_variable(self):
        return self._transition.get_base_variable()
    
    def is_signal_based(self):
        return self._transition.is_signal_based()
    
    def get_transition(self):
        return self._transition
    
    def __repr__(self):
        return f"{self._transition}.after()"

"""
Logic related to signal constants
"""

class Signal():
    """
    Class to represent a signal whose values we can extract using (for now) timestamps.
    """

    def __init__(self, signal_name):
        """
        Store `signal_name`.
        """

        self._signal_name = signal_name

    def __sizeof__(self):
        return sys.getsizeof(self._signal_name)

    def get_function_names(self):
        return []

    def get_signal_name(self):
        return self._signal_name

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._signal_name == other._signal_name)
    
    def __repr__(self):
        return f"signal({self._signal_name})"
    
    def at(self, timestamp):
        """
        Construct a `SignalAtTimestamp` instance.
        """
        return SignalAtTimestamp(self, timestamp)

def signal(signal_name):
    """
    Factory function for `Signal` instances.
    """
    return Signal(signal_name)

"""
Expressions
"""

class SignalAtTimestamp(Measurement):
    """
    Class to represent the value held by a signal at a given timestamp.
    """

    def __init__(self, signal_variable, timestamp):
        """
        Store `signal_variable` and `timestamp`.

        Assume `timestamp` is an instance of `Timestamp`.
        """

        if TimestampExpression not in type(timestamp).__bases__:
            raise Exception("Type of timestamp used to refer to a value in a signal must have base class `Timestamp`.")

        self._signal_variable = signal_variable
        self._timestamp = timestamp

    def __sizeof__(self):
        return sys.getsizeof(self._signal_variable) + sys.getsizeof(self._timestamp)

    def get_function_names(self):
        return self._timestamp.get_function_names()

    def get_base_variable(self):
        return self._timestamp.get_base_variable()

    def get_signal_name(self):
        return self._signal_variable.get_signal_name()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._signal_variable == other._signal_variable and
                self._timestamp == other._timestamp)
    
    def is_signal_based(self):
        return self._timestamp.is_signal_based()
    
    def get_timestamp(self):
        return self._timestamp
    
    def __repr__(self):
        return f"{self._signal_variable}.at({self._timestamp})"
    
    def __gt__(self, other):
        """
        Overload the > operator on `SignalAtTimestamp` instances.
        """

        return SignalAtTimestampGreaterThanNumber(self, other)

    def __lt__(self, other):
        """
        Overload the < operator on `SignalAtTimestamp` instances.
        """

        return SignalAtTimestampLessThanNumber(self, other)

    def equals(self, other):
        return SignalAtTimestampEqualsNumber(self, other)

class TimeBetween(Measurement):
    """
    Class to represent the time taken to reach one point from another.
    """

    def __init__(self, lhs_expression, rhs_expression):
        """
        `lhs_expression` and `rhs_expression` can be either concrete states or timestamps,
        but both cannot be timestamps.
        """

        self._lhs_expression = lhs_expression
        self._rhs_expression = rhs_expression

    def is_signal_based(self):
        return self._lhs_expression.is_signal_based() or self._rhs_expression.is_signal_based()

    def __sizeof__(self):
        return sys.getsizeof(self._lhs_expression) + sys.getsizeof(self._rhs_expression)

    def get_function_names(self):
        return self._lhs_expression.get_function_names() + self._rhs_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._lhs_expression == other._lhs_expression and
                self._rhs_expression == other._rhs_expression)
    
    def get_lhs_expression(self):
        return self._lhs_expression
    
    def get_rhs_expression(self):
        return self._rhs_expression
    
    def __repr__(self):
        return f"timeBetween({self._lhs_expression}, {self._rhs_expression})"
    
    def __lt__(self, other):
        """
        Given `other`, generate the appropriate atom, depending on the type of `other`.
        """
        if type(other) in [float, int]:
            return TimeBetweenLessThanConstant(self, other)

def timeBetween(lhs_expression, rhs_expression):
    """
    Instantiate a `TimeBetween` instance.
    """
    return TimeBetween(lhs_expression, rhs_expression)

class ValueInConcreteState(Measurement):
    """
    Class to represent the value to which a program variable is mapped by a concrete state.
    """

    def __init__(self, concrete_state, program_variable):
        """
        Store `concrete_state` and `program_variable`.
        """
        self._concrete_state = concrete_state
        self._program_variable = program_variable

    def __sizeof__(self):
        return sys.getsizeof(self._concrete_state) + sys.getsizeof(self._program_variable)

    def get_function_names(self):
        return self._concrete_state.get_function_names()
    
    def get_base_variable(self):
        return self._concrete_state.get_base_variable()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._concrete_state == other._concrete_state and
                self._program_variable == other._program_variable)
    
    def get_concrete_state_expression(self):
        return self._concrete_state

    def get_program_variable(self):
        return self._program_variable
    
    def is_signal_based(self):
        return self._concrete_state.is_signal_based()
    
    def __repr__(self):
        return f"{self._concrete_state}({self._program_variable})"
    
    def equals(self, other):
        """
        Given `other`, generate the appropriate atom.
        """
        return ValueInConcreteStateEqualToConstant(self, other)

    def __lt__(self, other):
        return ValueInConcreteStateLessThanConstant(self, other)

    def __gt__(self, other):
        return ValueInConcreteStateGreaterThanConstant(self, other)

    def __le__(self, other):
        return ValueInConcreteStateLessThanEqualToConstant(self, other)

    def __ge__(self, other):
        return ValueInConcreteStateGreaterThanEqualToConstant(self, other)

    def notEqual(self, other):
        return ValueInConcreteStateNotEqualToConstant(self, other)

    def __add__(self, other):
        if type(other) in [int, float]:
            return ValueInConcreteStateWithAddition(self, other)

class ValueInConcreteStateWithAddition(Measurement):
    """
    Class to represent a ValueInConcreteState instance with addition performed.
    """

    def __init__(self, value_expression, number):
        self._value_expression = value_expression
        self._number = number

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._number)

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) is type(other) and
                self._value_expression == other._value_expression and
                self._number == other._number)

    def __repr__(self):
        return f"{self._value_expression} + {self._number}"

    def get_number(self):
        return self._number

    def get_value_expression(self):
        return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def derive_arithmetic_sequence(self):
        return [lambda x : x + self._number] + self._value_expression.derive_arithmetic_sequence()

    def equals(self, other):
        """
        Given `other`, generate the appropriate atom.
        """
        return ValueInConcreteStateWithAdditionEqualToValueInConcreteState(self, other)

class DurationOfTransition(Measurement):
    """
    Class to represent the duration of a transition.
    """
    def __init__(self, transition):
        """
        Store `transition`.
        """
        self._transition = transition

    def __sizeof__(self):
        return sys.getsizeof(self._transition)

    def get_function_names(self):
        return self._transition.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and self._transition == other._transition)

    def __repr__(self):
        return f"{self._transition}.duration()"

    def get_base_variable(self):
        return self._transition.get_base_variable()

    def set_sub_expression_value(self, value, sub_expression_index):
        self._measurement = value

    def get_transition_expression(self):
        return self._transition

    def is_signal_based(self):
        return self._transition.is_signal_based()

    def __lt__(self, other):
        if type(other) in [int, float]:
            return DurationOfTransitionLessThanNumber(self, other)

"""
Atoms
"""

class SignalAtTimestampGreaterThanNumber(ConstraintBase, NormalAtom):
    """
    Class to model the constraint signal @t t > n,
    for a signal, a timestamp t and a numerical constant n.
    """

    def __init__(self, signal_timestamp_expression, constant):
        """
        Store `signal_timestamp_expression` and `constant`.
        """
        self._signal_timestamp_expression = signal_timestamp_expression
        self._constant = constant
        self._binding = None

    def __sizeof__(self):
        return sys.getsizeof(self._signal_timestamp_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._signal_timestamp_expression.get_function_names()

    def get_constant(self):
        return self._constant

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._signal_timestamp_expression == other._signal_timestamp_expression and
                self._constant == other._constant)
    
    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("SignalAtTimestampGreaterThanNumber instance only has one subatom.")
        else:
            return self._signal_timestamp_expression

    def get_expression(self, index):
        return self.get_subatom_at_index(0)
    
    def is_signal_based(self):
        return self._signal_timestamp_expression.is_signal_based()
    
    def set_binding(self, binding):
        self._binding = binding
    
    def get_signal_timestamp_expression(self):
        return self._signal_timestamp_expression
    
    def __repr__(self):
        return f"{self._signal_timestamp_expression} > {self._constant}"


class SignalAtTimestampLessThanNumber(ConstraintBase, NormalAtom):
    """
    Class to model the constraint signal @t t < n,
    for a signal, a timestamp t and a numerical constant n.
    """

    def __init__(self, signal_timestamp_expression, constant):
        """
        Store `signal_timestamp_expression` and `constant`.
        """
        self._signal_timestamp_expression = signal_timestamp_expression
        self._constant = constant
        self._binding = None

    def __sizeof__(self):
        return sys.getsizeof(self._signal_timestamp_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._signal_timestamp_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._signal_timestamp_expression == other._signal_timestamp_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("SignalAtTimestampLessThanNumber instance only has one subatom.")
        else:
            return self._signal_timestamp_expression

    def get_expression(self, index):
        return self.get_subatom_at_index(0)

    def is_signal_based(self):
        return self._signal_timestamp_expression.is_signal_based()

    def set_binding(self, binding):
        self._binding = binding

    def get_signal_timestamp_expression(self):
        return self._signal_timestamp_expression

    def __repr__(self):
        return f"{self._signal_timestamp_expression} < {self._constant}"


class SignalAtTimestampEqualsNumber(ConstraintBase, NormalAtom):
    """
    Class to model the constraint signal @t t = n,
    for a signal, a timestamp t and a numerical constant n.
    """

    def __init__(self, signal_timestamp_expression, constant):
        """
        Store `signal_timestamp_expression` and `constant`.
        """
        self._signal_timestamp_expression = signal_timestamp_expression
        self._constant = constant
        self._binding = None

    def __sizeof__(self):
        return sys.getsizeof(self._signal_timestamp_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._signal_timestamp_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._signal_timestamp_expression == other._signal_timestamp_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("SignalAtTimestampGreaterThanNumber instance only has one subatom.")
        else:
            return self._signal_timestamp_expression

    def get_expression(self, index):
        return self.get_subatom_at_index(0)

    def is_signal_based(self):
        return self._signal_timestamp_expression.is_signal_based()

    def set_binding(self, binding):
        self._binding = binding

    def get_signal_timestamp_expression(self):
        return self._signal_timestamp_expression

    def __repr__(self):
        return f"{self._signal_timestamp_expression}.equals({self._constant})"

class TimeBetweenLessThanConstant(ConstraintBase, MixedAtom):
    """
    Class to model the constraint timeBetween(a, b) < n
    for n a numerical constant.
    """

    def __init__(self, time_between_expression, constant):
        """
        Store `time_between_expression` and `constant`.
        """
        self._time_between_expression = time_between_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._time_between_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._time_between_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._time_between_expression == other._time_between_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant
    
    def get_subatom_at_index(self, index):
        return self.get_expression(index)
    
    def is_signal_based(self):
        return self._time_between_expression.is_signal_based()
    
    def get_time_between_expression(self):
        return self._time_between_expression
    
    def get_expression(self, index):
        # get the time between object
        expressions = self.get_time_between_expression()
        # construct a list of the lhs and rhs of the time between operator
        expressions = [expressions.get_lhs_expression(), expressions.get_rhs_expression()]
        return expressions[index]
    
    def get_lhs_expression(self):
        return self.get_expression(0)
    
    def get_rhs_expression(self):
        return self.get_expression(1)
    
    def __repr__(self):
        return f"{self._time_between_expression} < {self._constant}"


class ValueInConcreteStateLessThanConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x) < n.
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateLessThanConstant instance only has one subatom.")
        else:
            return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def __repr__(self):
        return f"{self._value_expression} < {self._constant}"

class ValueInConcreteStateNotEqualToConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x) != n.
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateNotEqualToConstant instance only has one subatom.")
        else:
            return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def __repr__(self):
        return f"{self._value_expression} != {self._constant}"

class ValueInConcreteStateLessThanEqualToConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x) <= n.
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateLessThanEqualToConstant instance only has one subatom.")
        else:
            return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def __repr__(self):
        return f"{self._value_expression} <= {self._constant}"

class ValueInConcreteStateGreaterThanEqualToConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x) >= n.
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateGreaterThanEqualToConstant instance only has one subatom.")
        else:
            return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def __repr__(self):
        return f"{self._value_expression} >= {self._constant}"

class ValueInConcreteStateGreaterThanConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x) > n.
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateGreaterThanConstant instance only has one subatom.")
        else:
            return self._value_expression

    def is_signal_based(self):
        return self._value_expression.is_signal_based()

    def __repr__(self):
        return f"{self._value_expression} > {self._constant}"

class ValueInConcreteStateEqualToConstant(ConstraintBase, NormalAtom):
    """
    Class to model the constraint q(x).equals(n).
    """

    def __init__(self, value_expression, constant):
        """
        Store `value_expression` and `constant`.
        """
        self._value_expression = value_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._value_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._value_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._value_expression == other._value_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant
    
    def get_value_expression(self):
        return self._value_expression

    def get_expression(self, index):
        return self.get_value_expression()
    
    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("ValueInConcreteStateEqualToConstant instance only has one subatom.")
        else:
            return self._value_expression
    
    def is_signal_based(self):
        return self._value_expression.is_signal_based()
    
    def __repr__(self):
        return f"{self._value_expression}.equals({self._constant})"


class ValueInConcreteStateWithAdditionEqualToValueInConcreteState(ConstraintBase, MixedAtom):
    """
    Class to model the constraint (q1(x) + n).equals(q2(x)).
    """

    def __init__(self, lhs_expression, rhs_expression):
        """
        Store `lhs_expression` and `rhs_expression`.
        """
        self._lhs_expression = lhs_expression
        self._rhs_expression = rhs_expression

    def __sizeof__(self):
        return sys.getsizeof(self._lhs_expression) + sys.getsizeof(self._rhs_expression)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._lhs_expression.get_function_names() + self._rhs_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._lhs_expression == other._rhs_expression and
                self._lhs_expression == other._rhs_expression)

    def get_expression(self, index):
        # construct a list of the lhs and rhs
        expressions = [self._lhs_expression, self._rhs_expression]
        return expressions[index]

    def get_lhs_expression(self):
        return self.get_expression(0)

    def get_rhs_expression(self):
        return self.get_expression(1)

    def get_subatom_at_index(self, index):
        return self.get_expression(index)

    def is_signal_based(self):
        return self._lhs_expression.is_signal_based() or self._rhs_expression.is_signal_based()

    def __repr__(self):
        return f"{self._lhs_expression}.equals({self._rhs_expression})"

class DurationOfTransitionLessThanNumber(ConstraintBase, NormalAtom):
    """
    Class to model the constraint t.duration() < n.
    """

    def __init__(self, duration_expression, constant):
        """
        Store `duration_expression` and `constant`.
        """
        self._duration_expression = duration_expression
        self._constant = constant

    def __sizeof__(self):
        return sys.getsizeof(self._duration_expression) + sys.getsizeof(self._constant)

    def get_atoms(self):
        return [self]

    def get_function_names(self):
        return self._duration_expression.get_function_names()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._duration_expression == other._duration_expression and
                self._constant == other._constant)

    def get_constant(self):
        return self._constant

    def get_duration_expression(self):
        return self._duration_expression

    def get_expression(self, index):
        return self.get_duration_expression()

    def get_subatom_at_index(self, index):
        if index != 0:
            raise Exception("DurationOfTransitionLessThanNumber instance only has one subatom.")
        else:
            return self._duration_expression

    def is_signal_based(self):
        return self._duration_expression.is_signal_based()

    def __repr__(self):
        return f"{self._duration_expression} < {self._constant}"


class BooleanConstant(ConstraintBase, NormalAtom):
    """
    Class to model a constant boolean value.
    """

    def __init__(self, boolean_value):
        """
        Store `boolean_value`.
        """
        self._value = boolean_value

    def __sizeof__(self):
        return sys.getsizeof(self._value)

    def get_atoms(self):
        return [self]

    def __repr__(self):
        return str(self._value)

    def __eq__(self, other):
        return type(self) == type(other) and self._value == other._value

    def get_value(self):
        return self._value

    def get_function_names(self):
        return []


def boolean(value):
    return BooleanConstant(value)