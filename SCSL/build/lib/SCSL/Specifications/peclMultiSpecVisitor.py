# Generated from peclMultiSpec.g4 by ANTLR 4.13.0
from antlr4 import *
if "." in __name__:
    from .peclMultiSpecParser import peclMultiSpecParser
else:
    from peclMultiSpecParser import peclMultiSpecParser

# This class defines a complete generic visitor for a parse tree produced by peclMultiSpecParser.

class peclMultiSpecVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by peclMultiSpecParser#cmp.
    def visitCmp(self, ctx:peclMultiSpecParser.CmpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#number.
    def visitNumber(self, ctx:peclMultiSpecParser.NumberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#constant.
    def visitConstant(self, ctx:peclMultiSpecParser.ConstantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#string.
    def visitString(self, ctx:peclMultiSpecParser.StringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#python_symbol.
    def visitPython_symbol(self, ctx:peclMultiSpecParser.Python_symbolContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#peclMultiSpec.
    def visitPeclMultiSpec(self, ctx:peclMultiSpecParser.PeclMultiSpecContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#block.
    def visitBlock(self, ctx:peclMultiSpecParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#duration.
    def visitDuration(self, ctx:peclMultiSpecParser.DurationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#timeBetween.
    def visitTimeBetween(self, ctx:peclMultiSpecParser.TimeBetweenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#whenever.
    def visitWhenever(self, ctx:peclMultiSpecParser.WheneverContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#predicate.
    def visitPredicate(self, ctx:peclMultiSpecParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#predicate_name.
    def visitPredicate_name(self, ctx:peclMultiSpecParser.Predicate_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#dsl_predicate.
    def visitDsl_predicate(self, ctx:peclMultiSpecParser.Dsl_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#predicate_args.
    def visitPredicate_args(self, ctx:peclMultiSpecParser.Predicate_argsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#procedure_qualifier.
    def visitProcedure_qualifier(self, ctx:peclMultiSpecParser.Procedure_qualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#guard.
    def visitGuard(self, ctx:peclMultiSpecParser.GuardContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#expectation.
    def visitExpectation(self, ctx:peclMultiSpecParser.ExpectationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#constraint.
    def visitConstraint(self, ctx:peclMultiSpecParser.ConstraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#function_constraint.
    def visitFunction_constraint(self, ctx:peclMultiSpecParser.Function_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#function_measurement.
    def visitFunction_measurement(self, ctx:peclMultiSpecParser.Function_measurementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#state_constraint.
    def visitState_constraint(self, ctx:peclMultiSpecParser.State_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclMultiSpecParser#state_measurement.
    def visitState_measurement(self, ctx:peclMultiSpecParser.State_measurementContext):
        return self.visitChildren(ctx)



del peclMultiSpecParser