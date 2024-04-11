# Generated from scsl.g4 by ANTLR 4.11.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .scslParser import scslParser
else:
    from scslParser import scslParser

# This class defines a complete generic visitor for a parse tree produced by scslParser.

class scslVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by scslParser#real_number.
    def visitReal_number(self, ctx:scslParser.Real_numberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#quant.
    def visitQuant(self, ctx:scslParser.QuantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#disjunction.
    def visitDisjunction(self, ctx:scslParser.DisjunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#conjunction.
    def visitConjunction(self, ctx:scslParser.ConjunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#negation.
    def visitNegation(self, ctx:scslParser.NegationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#value.
    def visitValue(self, ctx:scslParser.ValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#variable.
    def visitVariable(self, ctx:scslParser.VariableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#string.
    def visitString(self, ctx:scslParser.StringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#signal_variable.
    def visitSignal_variable(self, ctx:scslParser.Signal_variableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#predicate_name.
    def visitPredicate_name(self, ctx:scslParser.Predicate_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#beforeTr.
    def visitBeforeTr(self, ctx:scslParser.BeforeTrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#afterTr.
    def visitAfterTr(self, ctx:scslParser.AfterTrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#spec.
    def visitSpec(self, ctx:scslParser.SpecContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#quantifier_block.
    def visitQuantifier_block(self, ctx:scslParser.Quantifier_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#quant_section.
    def visitQuant_section(self, ctx:scslParser.Quant_sectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#inner.
    def visitInner(self, ctx:scslParser.InnerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#predicate.
    def visitPredicate(self, ctx:scslParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#source_code_predicate.
    def visitSource_code_predicate(self, ctx:scslParser.Source_code_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#dsl_predicate.
    def visitDsl_predicate(self, ctx:scslParser.Dsl_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#predicate_args.
    def visitPredicate_args(self, ctx:scslParser.Predicate_argsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#procedure_qualifier.
    def visitProcedure_qualifier(self, ctx:scslParser.Procedure_qualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#after_qualifier.
    def visitAfter_qualifier(self, ctx:scslParser.After_qualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#timestamp_predicate.
    def visitTimestamp_predicate(self, ctx:scslParser.Timestamp_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#expr.
    def visitExpr(self, ctx:scslParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#ts.
    def visitTs(self, ctx:scslParser.TsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#tr.
    def visitTr(self, ctx:scslParser.TrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#c.
    def visitC(self, ctx:scslParser.CContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#nextOp.
    def visitNextOp(self, ctx:scslParser.NextOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#cmp.
    def visitCmp(self, ctx:scslParser.CmpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#arithmetic.
    def visitArithmetic(self, ctx:scslParser.ArithmeticContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#phi_single.
    def visitPhi_single(self, ctx:scslParser.Phi_singleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#phi_ts.
    def visitPhi_ts(self, ctx:scslParser.Phi_tsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#phi_tr.
    def visitPhi_tr(self, ctx:scslParser.Phi_trContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#phi_c.
    def visitPhi_c(self, ctx:scslParser.Phi_cContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#phi_multiple.
    def visitPhi_multiple(self, ctx:scslParser.Phi_multipleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#timeBetween.
    def visitTimeBetween(self, ctx:scslParser.TimeBetweenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#v_ts.
    def visitV_ts(self, ctx:scslParser.V_tsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#v_tr.
    def visitV_tr(self, ctx:scslParser.V_trContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by scslParser#v_c.
    def visitV_c(self, ctx:scslParser.V_cContext):
        return self.visitChildren(ctx)



del scslParser