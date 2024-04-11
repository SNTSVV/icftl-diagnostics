"""
Module containing definitions of predicates to be used in LHS specifications.

Each predicate is a class.
"""

class inTimeInterval():
    """
    Models a predicate asking whether a timestamp falls within a given interval.
    """

    def __init__(self, interval):
        """
        We assume that `interval` is either a list [n, m] for m > n,
        or a tuple (n, m) for m > n.
        A list models a closed set and a tuple models an open set.
        """

        if type(interval) not in [list, tuple]:
            raise Exception("Argument given to inTimeInterval must be a list or a tuple.")

        self._interval = interval

    def get_function_names(self):
        return []

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._interval == other._interval)

    def set_sub_expression_value(self, value, sub_expression_index):
        # tuples are immutable, so we convert to a list
        # and then convert back to the original type once we've added the new value
        original_interval_type = type(self._interval)
        self._interval = list(self._interval)
        if sub_expression_index == 0 and hasattr(self._interval[0], "derive_arithmetic_sequence"):
            # first, derive the sequence of operations to apply to the timestamp
            function_sequence = reversed(self._interval[0].derive_arithmetic_sequence())
            # apply the sequence
            final_value = value
            for f in function_sequence:
                final_value = f(final_value)
            # replace the final value in the predicate
            self._interval[0] = final_value
        elif sub_expression_index == 1 and hasattr(self._interval[1], "derive_arithmetic_sequence"):
            # first, derive the sequence of operations to apply to the timestamp
            function_sequence = reversed(self._interval[1].derive_arithmetic_sequence())
            # apply the sequence
            final_value = value
            for f in function_sequence:
                final_value = f(final_value)
            # replace the final value in the predicate
            self._interval[1] = final_value
        # convert the interval back to the original type
        self._interval = original_interval_type(self._interval)
        # print("subexpression set - ", self._interval)

    def get_left_expression(self):
        # print(type(self._interval[0]))
        return self._interval[0]

    def get_right_expression(self):
        # print(type(self._interval[1]))
        return self._interval[1]

    def check_satisfaction(self, timestamp):
        # if one of the values in the interval is not yet a number, we can't evaluate it
        # so just return False
        if type(self._interval[0]) not in [int, float] or type(self._interval[1]) not in [int, float]:
            return False
        else:
            if type(self._interval) is tuple:
                return self._interval[0] < timestamp < self._interval[1]
            elif type(self._interval) is list:
                return self._interval[0] <= timestamp <= self._interval[1]
    
    def __repr__(self):
        return str(self._interval)

class changes():
    """
    Models a predicate asking whether a program variable has been changed.
    """

    def __init__(self, program_variable):
        """
        We assume that `program_variable` is a string representing a variable
        found in source code.
        """

        if type(program_variable) is not str:
            raise Exception("Argument given to changes() must be an instance of `str`.")

        self._program_variable = program_variable
        self._during_function = None
        self._after_timestamp = None

    def get_function_names(self):
        return [self._during_function]

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._program_variable == other._program_variable and
                self._during_function == other._during_function and
                self._after_timestamp == other._after_timestamp)
    
    def get_program_variable(self):
        return self._program_variable
    
    def get_during_function(self):
        return self._during_function
    
    def get_after_timestamp(self):
        return self._after_timestamp

    def set_after_timestamp(self, value):
        if type(self._after_timestamp) is not float:
            self._after_timestamp = value

    def check_satisfaction(self, timestamp):
        return timestamp > self._after_timestamp
    
    def __repr__(self):
        if self._after_timestamp:
            return f"changes({self._program_variable}).during({self._during_function}).after({self._after_timestamp})"
        else:
            return f"changes({self._program_variable}).during({self._during_function})"
    
    def during(self, function_name):
        """
        We assume that `function_name` is a string representing a procedure
        found in source code
        """

        if type(function_name) is not str:
            raise Exception("Argument given to changes(...).during() must be an instance of `str`.")

        self._during_function = function_name

        return self
    
    def after(self, timestamp):
        """
        Given `timestamp`, we set the time component of the predicate.
        """

        self._after_timestamp = timestamp

        return self

class calls():
    """
    Models a predicate asking whether a program function has been called.
    """

    def __init__(self, program_function):
        """
        We assume that `program_function` is a string representing a function called in source code.
        """

        if type(program_function) is not str:
            raise Exception("Argument given to calls() must be an instance of `str`.")

        self._program_function = program_function
        self._during_function = None
        self._after_timestamp = None

    def get_function_names(self):
        return [self._during_function]

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._program_function == other._program_function and
                self._during_function == other._during_function and
                self._after_timestamp == other._after_timestamp)
    
    def get_function_name(self):
        return self._program_function
    
    def get_during_function(self):
        return self._during_function
    
    def get_after_timestamp(self):
        return self._after_timestamp

    def set_after_timestamp(self, value):
        if type(self._after_timestamp) is not float:
            self._after_timestamp = value

    def check_satisfaction(self, timestamp):
        return timestamp > self._after_timestamp

    def __repr__(self):
        if self._after_timestamp:
            return f"calls({self._program_function}).during({self._during_function}).after({self._after_timestamp})"
        else:
            return f"calls({self._program_function}).during({self._during_function})"
    
    def during(self, function_name):
        """
        We assume that `function_name` is a string representing a procedure
        found in source code
        """

        if type(function_name) is not str:
            raise Exception("Argument given to changes(...).during() must be an instance of `str`.")

        self._during_function = function_name

        return self
    
    def after(self, timestamp):
        """
        Given `timestamp`, we set the time component of the predicate.
        """

        self._after_timestamp = timestamp

        return self