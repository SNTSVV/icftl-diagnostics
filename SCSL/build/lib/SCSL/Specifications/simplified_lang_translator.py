from antlr4 import *

from .peclMultiSpecLexer import peclMultiSpecLexer
from .peclMultiSpecParser import peclMultiSpecParser
from .peclMultiSpecVisitor import peclMultiSpecVisitor

# These imports are required for the `eval` statement in `parse_specification`
from .builder import *
from .constraints import *
from .predicates import *


class SpecificationParsingError(Exception):
    pass


class DSLListVisitor(peclMultiSpecVisitor):

    def visitPeclMultiSpec(self, ctx:peclMultiSpecParser.PeclMultiSpecContext):
        # generate code for children
        type_text_pair_list = list(
            map(lambda child : child.accept(self), ctx.getChildren())
        )
        # remove None occurrences
        type_text_pair_list = list(filter(lambda item : item is not None and item != "", type_text_pair_list))
        return type_text_pair_list

    def visitBlock(self, ctx:peclMultiSpecParser.BlockContext):
        if ctx.duration():
            spec_type = "SpecDuration"
            predicate_text = ctx.duration().predicate().getText()
            cmp_text = ctx.duration().cmp().getText()
            number_text = ctx.duration().number().getText()
            dsl_text = f"duration({predicate_text}) {cmp_text} {number_text}"
        elif ctx.timeBetween():
            spec_type = "SpecTimeBetween"
            lhs_text = ctx.timeBetween().predicate(0).getText()
            rhs_text = ctx.timeBetween().predicate(1).getText()
            cmp_text = ctx.timeBetween().cmp().getText()
            number_text = ctx.timeBetween().number().getText()
            dsl_text = f"timeBetween {lhs_text}, {rhs_text} {cmp_text} {number_text}"
        elif ctx.whenever():
            spec_type = "SpecWhenever"
            guard_text = guard_or_expectation_to_text(ctx.whenever().guard())
            expectation_text = guard_or_expectation_to_text(ctx.whenever().expectation())
            dsl_text = f"whenever {guard_text} eventually {expectation_text}"
        return spec_type, dsl_text

def guard_or_expectation_to_text(ctx):
    if ctx.predicate():
        return ctx.predicate().getText()
    else:
        return constraint_to_text(ctx.constraint())

def constraint_to_text(ctx):
    if ctx.function_constraint():
        function_constraint = ctx.function_constraint()
        if function_constraint.function_constraint():
            function_constraint = function_constraint.function_constraint()
        guard_predicate = function_constraint.function_measurement().predicate().getText()
        cmp = function_constraint.cmp().getText()
        number = function_constraint.number().getText()
        dsl_text = f"duration {guard_predicate} {cmp} {number}"
    elif ctx.state_constraint():
        state_constraint = ctx.state_constraint()
        if state_constraint.state_constraint():
            state_constraint = state_constraint.state_constraint()
        guard_predicate = state_constraint.state_measurement().predicate().getText()
        variable_name = state_constraint.state_measurement().string().getText()
        cmp = state_constraint.cmp().getText()
        constant = state_constraint.constant().getText()
        dsl_text = f"value {variable_name} in {guard_predicate} {cmp} {constant}"
    return dsl_text


class VisitorAsTranslator(peclMultiSpecVisitor):

    def visitPeclMultiSpec(self, ctx:peclMultiSpecParser.PeclMultiSpecContext):
        # generate code for children
        code_list = list(
            map(lambda child : child.accept(self), ctx.getChildren())
        )
        # remove None occurrences
        code_list = list(filter(lambda item : item is not None, code_list))
        # turn code list into a Python list
        comma_separated = ",".join(code_list)
        python_code = f"[{comma_separated}]"
        return python_code

    # Visit a parse tree produced by peclMultiSpecParser#pecl.
    def visitBlock(self, ctx:peclMultiSpecParser.BlockContext):

        python_code = ""

        if ctx.duration():
            predicate = self.predicate_to_code(ctx.duration().predicate())
            cmp = ctx.duration().cmp().accept(self)
            number = ctx.duration().number().accept(self)
            if cmp == "=":
                python_code = f"forall(id=0, binding={{}}, predicate={predicate})." \
                              f"check(lambda binding: binding[0].duration().equals({number}))"
            else:
                python_code = f"forall(id=0, binding={{}}, predicate={predicate})." \
                              f"check(lambda binding: binding[0].duration() {cmp} {number})"
        elif ctx.timeBetween():
            predicate1_code = self.predicate_to_code(ctx.timeBetween().predicate(0))
            predicate1_name = ctx.timeBetween().predicate(0).dsl_predicate().predicate_name().getText()
            predicate2_code = self.predicate_to_code(ctx.timeBetween().predicate(1))
            predicate2_name = ctx.timeBetween().predicate(1).dsl_predicate().predicate_name().getText()
            cmp = ctx.timeBetween().cmp().accept(self)
            number = ctx.timeBetween().number().accept(self)
            timeBetween_lhs = "binding[0]" \
                if predicate1_name != "calls" \
                else "binding[0].before()"
            timeBetween_rhs = f"binding[0].next({predicate2_code})" \
                if predicate2_name != "calls" \
                else f"binding[0].next({predicate2_code}).after()"
            if cmp == "=":
                python_code = f"forall(id=0, binding={{}}, predicate={predicate1_code})." \
                              f"check(lambda binding: timeBetween({timeBetween_lhs}, {timeBetween_rhs})." \
                              f"equals({number}))"
            else:
                python_code = f"forall(id=0, binding={{}}, predicate={predicate1_code})." \
                              f"check(lambda binding: timeBetween({timeBetween_lhs}, {timeBetween_rhs}) {cmp} {number})"
        elif ctx.whenever():
            python_code = self.whenever_to_code(ctx.whenever())

        return python_code

    def predicate_to_code(self, ctx):
        # get predicate name
        predicate_name = ctx.dsl_predicate().predicate_name().getText()
        args = ctx.dsl_predicate().predicate_args().getChildren()
        predicate_arg_string = ",".join(
            map(lambda arg: arg.getText(), args)
        )
        procedure_qualifier_name = ctx.procedure_qualifier().string().getText()
        code = f"{predicate_name}({predicate_arg_string}).during({procedure_qualifier_name})"
        return code

    def visitPredicate(self, ctx: peclMultiSpecParser.PredicateContext):
        dsl_predicate_string = ctx.dsl_predicate().accept(self)
        procedure_qualifier_string = ctx.procedure_qualifier().accept(self)
        predicate_string = f"{dsl_predicate_string}.{procedure_qualifier_string}"
        return predicate_string

    def visitDsl_predicate(self, ctx: peclMultiSpecParser.Dsl_predicateContext):
        predicate_name = ctx.predicate_name().accept(self)
        predicate_arg_string = ctx.predicate_args().accept(self)
        return f"{predicate_name}({predicate_arg_string})"

    def visitPredicate_name(self, ctx: peclMultiSpecParser.Predicate_nameContext):
        return ctx.getText()

    def visitPredicate_args(self, ctx: peclMultiSpecParser.Predicate_argsContext):
        args = ctx.getChildren()
        arg_string = ",".join(
            map(lambda arg: arg.getText(), args)
        )
        return arg_string

    def visitProcedure_qualifier(self, ctx: peclMultiSpecParser.Procedure_qualifierContext):
        qualifier_string = f"during({ctx.string().getText()})"
        return qualifier_string

    def whenever_to_code(self, ctx):
        guard = ctx.guard()
        expectation = ctx.expectation()
        expectation_code = self.whenever_expectation_to_code(expectation)
        if guard.predicate():
            guard_predicate = guard.predicate().accept(self)
            code = f"forall(id=0, binding={{}}, predicate={guard_predicate})." \
                               f"check(lambda binding: {expectation_code})"
        elif guard.constraint():
            if guard.constraint().function_constraint():
                function_constraint = guard.constraint().function_constraint()
                if function_constraint.function_constraint():
                    function_constraint = function_constraint.function_constraint()
                guard_predicate = function_constraint.function_measurement().predicate().accept(self)
                cmp = function_constraint.cmp().accept(self)
                number = function_constraint.number().accept(self)
                if cmp == "=":
                    guard_constraint = f"binding[0].duration().equals({number})"
                else:
                    guard_constraint = f"binding[0].duration() {cmp} {number}"
            elif guard.constraint().state_constraint():
                state_constraint = guard.constraint().state_constraint()
                if state_constraint.state_constraint():
                    state_constraint = state_constraint.state_constraint()
                guard_predicate = state_constraint.state_measurement().predicate().accept(self)
                variable_name = state_constraint.state_measurement().string().accept(self)
                cmp = state_constraint.cmp().accept(self)
                constant = state_constraint.constant().accept(self)
                if cmp == "=":
                    guard_constraint = f"binding[0]({variable_name}).equals({constant})"
                elif cmp == "!=":
                    guard_constraint = f"binding[0]({variable_name}).notEqual({constant})"
                else:
                    guard_constraint = f"binding[0]({variable_name}) {cmp} {constant}"
            code = f"forall(id=0, binding={{}}, predicate={guard_predicate})." \
                               f"check(lambda binding: disjunction(binding, negate({guard_constraint}), {expectation_code}))"
        return code

    def whenever_expectation_to_code(self, ctx):
        if ctx.predicate():
            expectation_predicate = ctx.predicate().accept(self)
            code = f"exists(id=1, binding=binding, predicate={expectation_predicate})." \
                               f"check(lambda binding: boolean(True))"
        elif ctx.constraint():
            if ctx.constraint().function_constraint():
                function_constraint = ctx.constraint().function_constraint()
                if function_constraint.function_constraint():
                    function_constraint = function_constraint.function_constraint()
                expectation_predicate = function_constraint.function_measurement().predicate().accept(self)
                cmp = function_constraint.cmp().accept(self)
                number = function_constraint.number().accept(self)
                if cmp == "=":
                    expectation_constraint = f"binding[1].duration().equals({number})"
                else:
                    expectation_constraint = f"binding[1].duration() {cmp} {number}"
            elif ctx.constraint().state_constraint():
                state_constraint = ctx.constraint().state_constraint()
                if state_constraint.state_constraint():
                    state_constraint = state_constraint.state_constraint()
                expectation_predicate = state_constraint.state_measurement().predicate().accept(self)
                variable_name = state_constraint.state_measurement().string().accept(self)
                cmp = state_constraint.cmp().accept(self)
                constant = state_constraint.constant().accept(self)
                if cmp == "=":
                    expectation_constraint = f"binding[1]({variable_name}).equals({constant})"
                elif cmp == "!=":
                    expectation_constraint = f"binding[1]({variable_name}).notEqual({constant})"
                else:
                    expectation_constraint = f"binding[1]({variable_name}) {cmp} {constant}"
            code = f"exists(id=1, binding=binding, predicate={expectation_predicate})." \
                               f"check(lambda binding: {expectation_constraint})"
        return code

    def visitNumber(self, ctx:peclMultiSpecParser.NumberContext):
        return ctx.getText()

    def visitCmp(self, ctx:peclMultiSpecParser.CmpContext):
        return ctx.getText()

    def visitString(self, ctx:peclMultiSpecParser.StringContext):
        return ctx.getText()

    def visitConstant(self, ctx:peclMultiSpecParser.ConstantContext):
        return ctx.getText()


class TranslatorFromText:
    """
    Class to translate a high-level specification (given as text in memory) to Python code.
    """

    def __init__(self, dsl_text):
        input_stream = InputStream(dsl_text)
        lexer = peclMultiSpecLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = peclMultiSpecParser(stream)
        self.tree = parser.peclMultiSpec()

        # translate the DSL text to Python code
        translator = VisitorAsTranslator()
        self._python_code = translator.visit(self.tree)

        if self._python_code is None:
            raise SpecificationParsingError('An error occurred while parsing the specification.')

        # translate the DSL text to a list of DSL specifications
        visitor = DSLListVisitor()
        self._dsl_specs_list = visitor.visit(self.tree)

        if self._dsl_specs_list is None:
            raise SpecificationParsingError('An error occurred while parsing the specification.')

    def get_python_code(self):
        return self._python_code

    def get_dsl_list(self):
        return self._dsl_specs_list


class SpecDuration(TranslatorFromText):
    """
    Class providing logic for extracting expressions from duration specifications.
    """

    def get_expression(self, atom_index, expression_index):
        """
        Get the expression in the specification at the given atom index and expression index.

        For duration, we only care about a single expression,
        so don't need to use the atom and expression indices given.
        """
        expression = f"duration {self.tree.block(0).duration().predicate().getText()}"
        return expression


class SpecTimeBetween(TranslatorFromText):
    """
    Class providing logic for extracting expressions from time between specifications.
    """

    def get_expression(self, atom_index, expression_index):
        """
        Get the expression in the specification at the given atom index and expression index.
        """
        expression = self.tree.block(0).timeBetween().predicate(expression_index).getText()
        return expression

class SpecWhenever(TranslatorFromText):
    """
    Class providing logic for extracting expressions from whenever-eventually specifications.
    """

    def get_expression(self, atom_index, expression_index):
        """
        Get the expression in the specification at the given atom index and expression index.
        """
        if atom_index == 0:
            guard = self.tree.block(0).whenever().guard()
            expectation = self.tree.block(0).whenever().expectation()
            if guard.predicate():
                # if the guard is a predicate, then we have a specification like this:
                # forall q in guard : expectation
                # so the only atomic constraint is actually the expectation, so atom_index=0 corresponds to
                # the expectation
                expression = self.get_expression(1, 0)
            else:
                expression = constraint_to_measurement_text(guard.constraint())
        else:
            expectation = self.tree.block(0).whenever().expectation()
            if expectation.predicate():
                expression = expectation.predicate().getText()
            else:
                expression = constraint_to_measurement_text(expectation.constraint())
        return expression

def constraint_to_measurement_text(ctx):
    """
    Given a measurement, such as duration ..., generate its DSL text.
    """
    if ctx.function_constraint():
        predicate = ctx.function_constraint().function_measurement().predicate().getText()
        dsl_text = f"duration {predicate}"
    elif ctx.state_constraint():
        predicate = ctx.state_constraint().state_measurement().predicate().getText()
        variable_name = ctx.state_constraint().state_measurement().string().getText()
        dsl_text = f"value {variable_name} in {predicate}"
    return dsl_text


class Translator:
    """
    Class to translate a high-level specification to Python code.
    """

    def __init__(self, filename):
        input_stream = FileStream(filename)
        lexer = peclMultiSpecLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = peclMultiSpecParser(stream)
        tree = parser.peclMultiSpec()

        # translate the DSL text to Python code
        translator = VisitorAsTranslator()
        self._python_code = translator.visit(tree)

        if self._python_code is None:
            raise SpecificationParsingError('An error occurred while parsing the specification.')

        # translate the DSL text to a list of DSL specifications
        visitor = DSLListVisitor()
        self._dsl_specs_list = visitor.visit(tree)

        if self._dsl_specs_list is None:
            raise SpecificationParsingError('An error occurred while parsing the specification.')

    def get_python_code(self):
        return self._python_code

    def get_dsl_list(self):
        return self._dsl_specs_list


def compile_specification(source_filename, target_filename):
    # TODO: Create Specification class
    print("compiling DSL into Python code")
    python_code = _compile_specification_to_python_code(source_filename)
    _write_specification(python_code, target_filename)


def _compile_specification_to_python_code(source_filename):
    # TODO: Create Specification class
    # Transform the DSL specification into Python code
    return Translator(source_filename).get_python_code()

def _compile_specification_to_dsl_list(source_filename):
    # Transform the contents of the specification file into a list of DSL specifications
    return Translator(source_filename).get_dsl_list()

def _eval_specification_from_python_code(python_code):
    return eval(python_code)


def _write_specification(python_code, target_filename):
    # TODO: Create Specification class
    python_code = \
        f"""from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *
from SCSL.Specifications.predicates import *

specifications = {python_code}
"""
    # write Python code to file
    with open(target_filename, "w") as h:
        h.write(python_code)


if __name__ == '__main__':
    translator = Translator("simplified-specs/spec1.pecl")
    python_code = translator.get_python_code()
    print(python_code)

    translator = Translator("simplified-specs/spec2.pecl")
    python_code = translator.get_python_code()
    print(python_code)

    translator = Translator("simplified-specs/spec3.pecl")
    python_code = translator.get_python_code()
    print(python_code)

    translator = Translator("simplified-specs/spec4.pecl")
    python_code = translator.get_python_code()
    print(python_code)

    translator = Translator("simplified-specs/spec5.pecl")
    python_code = translator.get_python_code()
    print(python_code)

    translator = Translator("simplified-specs/spec6.pecl")
    python_code = translator.get_python_code()
    print(python_code)