"""
Module containing logic that uses the antlr library to construct an scsl specification based on
a text-based specification written with respect to the grammar in scsl.g4.
"""

from antlr4 import *

from .scslLexer import scslLexer
from .scslParser import scslParser
from .scslVisitor import scslVisitor

# These imports are required for the `eval` statement in `parse_specification`
from .builder import *
from .constraints import *
from .predicates import *


class SpecificationParsingError(Exception):
    pass

class VisitorAsTranslator(scslVisitor):
    """
    Class that uses a visitor to translate a high-level scsl specification to Python code.
    """

    def __init__(self):
        self._quantifier_count = 0
        self._variable_to_id_map = {}

    def visitReal_number(self, ctx:scslParser.Real_numberContext):
        return ctx.getText()

    def visitString(self, ctx:scslParser.StringContext):
        return f"{ctx.getText()}"

    # Visit a parse tree produced by scslParser#arithmetic.
    def visitArithmetic(self, ctx: scslParser.ArithmeticContext):
        return ctx.getText()

    # Visit a parse tree produced by scslParser#quant.
    def visitQuant(self, ctx: scslParser.QuantContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by scslParser#spec.
    def visitSpec(self, ctx: scslParser.SpecContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by scslParser#quantifier_block.
    def visitQuantifier_block(self, ctx: scslParser.Quantifier_blockContext):
        quantifier_id = self._quantifier_count
        binding = "binding" if self._quantifier_count > 0 else "{}"
        variable = ctx.quant_section().variable().getText()
        self._variable_to_id_map[variable] = self._quantifier_count
        self._quantifier_count += 1
        quant_predicate = ctx.quant_section().predicate()
        quant_value = quant_predicate.accept(self)
        quantifier_body_value = ctx.inner().accept(self)
        quantifier_text = "forall" \
            if ctx.quant_section().quant().getText() == "for every" \
            else "exists"
        spec_string = f"{quantifier_text}" \
                      f"(id={quantifier_id}, binding={binding}, " \
                      f"predicate={quant_value}).check(" \
                      f"lambda binding: (" \
                      f"{quantifier_body_value}" \
                      f"))"
        return spec_string

    # Visit a parse tree produced by scslParser#quant_section.
    def visitQuant_section(self, ctx: scslParser.Quant_sectionContext):
        return self.visitChildren(ctx)

    def visitPredicate(self, ctx:scslParser.PredicateContext):
        if ctx.source_code_predicate():
            predicate_string = ctx.source_code_predicate().accept(self)
        elif ctx.timestamp_predicate():
            predicate_string = ctx.timestamp_predicate().accept(self)
        return predicate_string

    def visitTimestamp_predicate(self, ctx:scslParser.Timestamp_predicateContext):
        lhs_ts = ctx.ts(0).accept(self)
        rhs_ts = ctx.ts(1).accept(self)
        return f"inTimeInterval([{lhs_ts}, {rhs_ts}])"

    def visitSource_code_predicate(self, ctx:scslParser.Source_code_predicateContext):
        dsl_predicate_string = ctx.dsl_predicate().accept(self)
        procedure_qualifier_string = ctx.procedure_qualifier().accept(self)
        after_qualitifier_string = f".{ctx.after_qualifier().accept(self)}"\
            if ctx.after_qualifier() else ""
        predicate_string = f"{dsl_predicate_string}.{procedure_qualifier_string}{after_qualitifier_string}"
        return predicate_string

    def visitDsl_predicate(self, ctx:scslParser.Dsl_predicateContext):
        predicate_name = ctx.predicate_name().accept(self)
        predicate_arg_string = ctx.predicate_args().accept(self)
        return f"{predicate_name}({predicate_arg_string})"

    def visitPredicate_name(self, ctx:scslParser.Predicate_nameContext):
        return ctx.getText()

    def visitPredicate_args(self, ctx:scslParser.Predicate_argsContext):
        args = ctx.getChildren()
        arg_string = ",".join(
            map(lambda arg : arg.getText(), args)
        )
        return arg_string

    def visitProcedure_qualifier(self, ctx:scslParser.Procedure_qualifierContext):
        qualifier_string = f"during({ctx.string().getText()})"
        return qualifier_string

    def visitAfter_qualifier(self, ctx:scslParser.After_qualifierContext):
        qualifier_string = f"after({ctx.ts().accept(self)})"
        return qualifier_string

    # Visit a parse tree produced by scslParser#inner.
    def visitInner(self, ctx: scslParser.InnerContext):
        # check for the kind of subformula
        children = list(ctx.getChildren())
        types = list(map(lambda child: type(child), children))
        if scslParser.DisjunctionContext in types:
            # we have a disjunction, so return "lor(...)"
            # construct string for each operand
            child_values = []
            for i in range(len(children)):
                child = ctx.getChild(i)
                if type(child) is scslParser.InnerContext:
                    child_values.append(child.accept(self))
            spec_string = ", ".join(child_values)
            spec_string = f"disjunction(binding, {spec_string})"
        elif scslParser.ConjunctionContext in types:
            # we have a conjunction, so return "land(...)"
            # construct string for each operand
            child_values = []
            for i in range(len(children)):
                child = ctx.getChild(i)
                if type(child) is scslParser.InnerContext:
                    child_values.append(child.accept(self))
            spec_string = ", ".join(child_values)
            spec_string = f"conjunction(binding, {spec_string})"
        elif scslParser.NegationContext in types:
            spec_string = f"negate({ctx.getChild(2).accept(self)})"
        elif scslParser.Quantifier_blockContext in types:
            for child in children:
                if type(child) is scslParser.Quantifier_blockContext:
                    child_value = child.accept(self)
            spec_string = child_value
        elif scslParser.Phi_singleContext in types:
            atomic_constraint = ctx.phi_single()
            spec_string = atomic_constraint.accept(self)
        elif scslParser.Phi_multipleContext in types:
            atomic_constraint = ctx.phi_multiple()
            spec_string = atomic_constraint.accept(self)
        elif scslParser.InnerContext in types:
            spec_string = ctx.getChild(1).accept(self)
            spec_string = f"({spec_string})"
        elif ctx.getText() == "true":
            spec_string = "boolean(True)"
        elif ctx.getText() == "false":
            spec_string = "boolean(False)"

        return spec_string

    # Visit a parse tree produced by scslParser#ts.
    def visitTs(self, ctx: scslParser.TsContext):
        if ctx.variable():
            variable = ctx.getText()
            spec_string = f"binding{[self._variable_to_id_map[variable]]}"
        elif ctx.c():
            spec_string = f"time({ctx.c().accept(self)})"
        elif ctx.tr():
            spec_string = f"time({ctx.tr().accept(self)})"
        elif ctx.ts() and ctx.real_number():
            spec_string = f"{ctx.ts().accept(self)} + {ctx.real_number().accept(self)}"
        elif ctx.real_number():
            spec_string = f"{ctx.real_number().accept(self)}"
        elif ctx.ts():
            spec_string = f"{ctx.ts().accept(self)}"
        else:
            spec_string = ctx.getText()
        return spec_string

    # Visit a parse tree produced by scslParser#tr.
    def visitTr(self, ctx: scslParser.TrContext):
        if ctx.nextOp():
            spec_string = ctx.nextOp().accept(self)
        elif ctx.variable():
            variable = ctx.getText()
            spec_string = f"binding{[self._variable_to_id_map[variable]]}"
        elif ctx.tr():
            spec_string = ctx.tr().accept(self)
        return spec_string

    # Visit a parse tree produced by scslParser#c.
    def visitC(self, ctx: scslParser.CContext):
        if ctx.nextOp():
            spec_string = ctx.nextOp().accept(self)
        elif ctx.variable():
            variable = ctx.getText()
            spec_string = f"binding{[self._variable_to_id_map[variable]]}"
        elif ctx.beforeTr():
            transition = ctx.tr().accept(self)
            spec_string = f"{transition}.before()"
        elif ctx.afterTr():
            transition = ctx.tr().accept(self)
            spec_string = f"{transition}.after()"
        elif ctx.c():
            spec_string = f"({ctx.c().accept(self)})"
        return spec_string

    def visitNextOp(self, ctx: scslParser.NextOpContext):
        base_expr = ctx.expr().accept(self)
        predicate_string = ctx.predicate().accept(self)
        spec_string = f"{base_expr}.next({predicate_string})"
        return spec_string

    # Visit a parse tree produced by scslParser#cmp.
    def visitCmp(self, ctx: scslParser.CmpContext):
        return ctx.getText()

    # Visit a parse tree produced by scslParser#phi_single.
    def visitPhi_single(self, ctx: scslParser.Phi_singleContext):
        child = list(ctx.getChildren())[0]
        value = child.accept(self)
        return value

    def visitPhi_multiple(self, ctx:scslParser.Phi_multipleContext):
        children = list(ctx.getChildren())
        if ctx.timeBetween():
            lhs = children[3].accept(self)
            rhs = children[1].accept(self)
            cmp = children[4].accept(self)
            constant = children[5].accept(self)
            spec_string = f"timeBetween({lhs}, {rhs}) {cmp} {constant}"
        else:
            lhs = children[0].accept(self)
            cmp = children[1].accept(self)
            rhs = children[2].accept(self)
            if cmp == "=":
                spec_string = f"({lhs}).equals({rhs})"
            else:
                spec_string = f"({lhs}) {cmp} ({rhs})"
        return spec_string

    # Visit a parse tree produced by scslParser#phi_ts.
    def visitPhi_ts(self, ctx: scslParser.Phi_tsContext):
        # get v_ts value
        v_ts = ctx.v_ts()
        v_ts_value = v_ts.accept(self)
        cmp = ctx.cmp().getText()
        if cmp == "=":
            return f"{v_ts_value}.equals({ctx.real_number().accept(self)})"
        elif cmp == ">":
            return f"{v_ts_value} > {ctx.real_number().accept(self)}"
        elif cmp == "<":
            return f"{v_ts_value} < {ctx.real_number().accept(self)}"

    # Visit a parse tree produced by scslParser#phi_tr.
    def visitPhi_tr(self, ctx: scslParser.Phi_trContext):
        # get v_tr value
        v_tr = ctx.v_tr()
        v_tr_value = v_tr.accept(self)
        cmp = ctx.cmp().getText()
        if cmp == "<":
            return f"{v_tr_value} < {ctx.real_number().accept(self)}"

    # Visit a parse tree produced by scslParser#phi_c.
    def visitPhi_c(self, ctx: scslParser.Phi_cContext):
        # get v_c value
        v_c = ctx.v_c()
        v_c_value = v_c.accept(self)
        cmp = ctx.cmp().getText()
        if cmp == "=":
            return f"{v_c_value}.equals({ctx.value().accept(self)})"
        else:
            return f"{v_c_value} {cmp} {ctx.value().accept(self)}"

    # Visit a parse tree produced by scslParser#value.
    def visitValue(self, ctx: scslParser.ValueContext):
        return ctx.getText()

    # Visit a parse tree produced by scslParser#v_ts.
    def visitV_ts(self, ctx: scslParser.V_tsContext):
        if ctx.signal_variable():
            variable = ctx.signal_variable().getText()
            ts = ctx.ts()
            ts_value = ts.accept(self)
            spec_string = f"signal(\"{variable}\").at({ts_value})"
        elif ctx.arithmetic():
            signal_value_string = ctx.v_ts().accept(self)
            arithmetic = ctx.arithmetic().accept(self)
            real_number = ctx.real_number().accept(self)
            spec_string = f"{signal_value_string} {arithmetic} {real_number}"
        elif ctx.v_ts():
            spec_string = ctx.v_ts().accept(self)
        return spec_string

    # Visit a parse tree produced by scslParser#v_tr.
    def visitV_tr(self, ctx: scslParser.V_trContext):
        if ctx.tr():
            tr = ctx.tr()
            tr_value = tr.accept(self)
            spec_string = f"{tr_value}.duration()"
        elif ctx.v_tr():
            spec_string = ctx.v_tr().accept(self)

        return spec_string

    # Visit a parse tree produced by scslParser#v_c.
    def visitV_c(self, ctx: scslParser.V_cContext):
        # check for the expression being an access of the value of a program variable in a state
        # or arithmetic on the value of a program variable (already obtained by access performed in another expression)
        if ctx.c():
            c = ctx.c()
            c_value = c.accept(self)
            spec_string = f"{c_value}({ctx.string().getText()})"
        elif ctx.arithmetic():
            v_c_value = ctx.v_c().accept(self)
            number = ctx.real_number().accept(self)
            spec_string = f"{v_c_value} + {number}"
        elif ctx.v_c():
            spec_string = ctx.v_c().accept(self)
        return spec_string


class Translator:
    """
    Class to translate a high-level scsl specification to Python code.
    """

    def __init__(self, filename):
        input_stream = FileStream(filename)
        lexer = scslLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = scslParser(stream)
        tree = parser.spec()
        visitor = VisitorAsTranslator()
        self._python_code = visitor.visit(tree)
        if self._python_code is None:
            raise SpecificationParsingError('An error occurred while parsing the specification.')

    def get_python_code(self):
        return self._python_code


def compile_specification(source_filename, target_filename):
    # TODO: Create Specification class
    print("compiling DSL into Python code")
    python_code = _compile_specification_to_python_code(source_filename)
    _write_specification(python_code, target_filename)


def _compile_specification_to_python_code(source_filename):
    # TODO: Create Specification class
    # Transform the DSL specification into Python code
    return Translator(source_filename).get_python_code()

def _eval_specification_from_python_code(python_code):
    return eval(python_code)


def _write_specification(python_code, target_filename):
    # TODO: Create Specification class
    python_code = \
        f"""from SCSL.Specifications.builder import *
from SCSL.Specifications.constraints import *
from SCSL.Specifications.predicates import *

specifications = [{python_code}]
"""
    # write Python code to file
    with open(target_filename, "w") as h:
        h.write(python_code)


def main(filename):
    input_stream = FileStream(filename)
    lexer = scslLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = scslParser(stream)
    tree = parser.spec()
    visitor = VisitorAsTranslator()
    python_code = visitor.visit(tree)


if __name__ == '__main__':
    main("spec-1.scsl")