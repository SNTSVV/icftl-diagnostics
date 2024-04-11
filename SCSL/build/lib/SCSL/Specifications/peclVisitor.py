# Generated from pecl.g4 by ANTLR 4.11.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .peclParser import peclParser
else:
    from peclParser import peclParser

# This class defines a complete generic visitor for a parse tree produced by peclParser.

class peclVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by peclParser#pecl.
    def visitPecl(self, ctx:peclParser.PeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#string.
    def visitString(self, ctx:peclParser.StringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#predicate.
    def visitPredicate(self, ctx:peclParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#predicate_name.
    def visitPredicate_name(self, ctx:peclParser.Predicate_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#dsl_predicate.
    def visitDsl_predicate(self, ctx:peclParser.Dsl_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#predicate_args.
    def visitPredicate_args(self, ctx:peclParser.Predicate_argsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#procedure_qualifier.
    def visitProcedure_qualifier(self, ctx:peclParser.Procedure_qualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#cmp.
    def visitCmp(self, ctx:peclParser.CmpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#number.
    def visitNumber(self, ctx:peclParser.NumberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#constant.
    def visitConstant(self, ctx:peclParser.ConstantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#duration.
    def visitDuration(self, ctx:peclParser.DurationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#timeBetween.
    def visitTimeBetween(self, ctx:peclParser.TimeBetweenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#whenever.
    def visitWhenever(self, ctx:peclParser.WheneverContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#guard.
    def visitGuard(self, ctx:peclParser.GuardContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#expectation.
    def visitExpectation(self, ctx:peclParser.ExpectationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#constraint.
    def visitConstraint(self, ctx:peclParser.ConstraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#function_constraint.
    def visitFunction_constraint(self, ctx:peclParser.Function_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#function_measurement.
    def visitFunction_measurement(self, ctx:peclParser.Function_measurementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#state_constraint.
    def visitState_constraint(self, ctx:peclParser.State_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by peclParser#state_measurement.
    def visitState_measurement(self, ctx:peclParser.State_measurementContext):
        return self.visitChildren(ctx)



del peclParser