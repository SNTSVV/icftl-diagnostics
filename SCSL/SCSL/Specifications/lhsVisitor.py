# Generated from lhs.g4 by ANTLR 4.9.2
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .lhsParser import lhsParser
else:
    from lhsParser import lhsParser

# This class defines a complete generic visitor for a parse tree produced by lhsParser.

class lhsVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by lhsParser#variable.
    def visitVariable(self, ctx:lhsParser.VariableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#signal_variable.
    def visitSignal_variable(self, ctx:lhsParser.Signal_variableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#quantifier_variable.
    def visitQuantifier_variable(self, ctx:lhsParser.Quantifier_variableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#string.
    def visitString(self, ctx:lhsParser.StringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#number.
    def visitNumber(self, ctx:lhsParser.NumberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#cmp_number.
    def visitCmp_number(self, ctx:lhsParser.Cmp_numberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#cmp_variable.
    def visitCmp_variable(self, ctx:lhsParser.Cmp_variableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#disjunction.
    def visitDisjunction(self, ctx:lhsParser.DisjunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#negation.
    def visitNegation(self, ctx:lhsParser.NegationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#satisfies.
    def visitSatisfies(self, ctx:lhsParser.SatisfiesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#quant.
    def visitQuant(self, ctx:lhsParser.QuantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#bool_true.
    def visitBool_true(self, ctx:lhsParser.Bool_trueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#nextfn.
    def visitNextfn(self, ctx:lhsParser.NextfnContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#timefn.
    def visitTimefn(self, ctx:lhsParser.TimefnContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#calls.
    def visitCalls(self, ctx:lhsParser.CallsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#changes.
    def visitChanges(self, ctx:lhsParser.ChangesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#during.
    def visitDuring(self, ctx:lhsParser.DuringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#after.
    def visitAfter(self, ctx:lhsParser.AfterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#duration.
    def visitDuration(self, ctx:lhsParser.DurationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#lb.
    def visitLb(self, ctx:lhsParser.LbContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#rb.
    def visitRb(self, ctx:lhsParser.RbContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#lsb.
    def visitLsb(self, ctx:lhsParser.LsbContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#rsb.
    def visitRsb(self, ctx:lhsParser.RsbContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#dot.
    def visitDot(self, ctx:lhsParser.DotContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#comma.
    def visitComma(self, ctx:lhsParser.CommaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#spec.
    def visitSpec(self, ctx:lhsParser.SpecContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#quantifier_block.
    def visitQuantifier_block(self, ctx:lhsParser.Quantifier_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#quant_section.
    def visitQuant_section(self, ctx:lhsParser.Quant_sectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#quant_predicate.
    def visitQuant_predicate(self, ctx:lhsParser.Quant_predicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#inner.
    def visitInner(self, ctx:lhsParser.InnerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_qts.
    def visitGamma_qts(self, ctx:lhsParser.Gamma_qtsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_ts.
    def visitGamma_ts(self, ctx:lhsParser.Gamma_tsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_qtr.
    def visitGamma_qtr(self, ctx:lhsParser.Gamma_qtrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_tr_extension.
    def visitGamma_tr_extension(self, ctx:lhsParser.Gamma_tr_extensionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_tr.
    def visitGamma_tr(self, ctx:lhsParser.Gamma_trContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_qc.
    def visitGamma_qc(self, ctx:lhsParser.Gamma_qcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_c_extension.
    def visitGamma_c_extension(self, ctx:lhsParser.Gamma_c_extensionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#gamma_c.
    def visitGamma_c(self, ctx:lhsParser.Gamma_cContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#ts.
    def visitTs(self, ctx:lhsParser.TsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#tr.
    def visitTr(self, ctx:lhsParser.TrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#c.
    def visitC(self, ctx:lhsParser.CContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#cmp.
    def visitCmp(self, ctx:lhsParser.CmpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#phi_single.
    def visitPhi_single(self, ctx:lhsParser.Phi_singleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#phi_ts.
    def visitPhi_ts(self, ctx:lhsParser.Phi_tsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#phi_tr.
    def visitPhi_tr(self, ctx:lhsParser.Phi_trContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#phi_c.
    def visitPhi_c(self, ctx:lhsParser.Phi_cContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#v_ts.
    def visitV_ts(self, ctx:lhsParser.V_tsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#v_tr.
    def visitV_tr(self, ctx:lhsParser.V_trContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by lhsParser#v_c.
    def visitV_c(self, ctx:lhsParser.V_cContext):
        return self.visitChildren(ctx)



del lhsParser