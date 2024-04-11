from SCFG import StatementType

Exp = StatementType('Exp')
Assign = StatementType('Assign')
Del = StatementType('Del')

# From an intraprocedural point of view, a yield statement neither exits the
# procedure nor diverts flow within the procedure like an exception would
# because, unless the program exits prematurely (because of an error, a call
# to python sys.exit, etc.), control will return to the statement following
# the yield statement. Therefore, from an intraprocedural point of view, a
# yield statement is similar to a function call in that it temporarily yields
# control to another procedure which eventually returns it to the caller,
# where the following statement is then executed.
YieldExp = StatementType('YieldExp')
YieldAssign = StatementType('YieldAssign')


If = StatementType('If')
Else = StatementType('Else')
EndIf = StatementType('EndIf')

Raise = StatementType('Raise', diverts_flow=True)
Try = StatementType('Try')
EndTry = StatementType('EndTry')

For = StatementType('For', is_loop=True)
EndFor = StatementType('EndFor')

While = StatementType('While', is_loop=True)
EndWhile = StatementType('EndWhile')

Return = StatementType('Return', diverts_flow=True, exits_procedure=True)

With = StatementType('With')
EndWith = StatementType('EndWith')

Continue = StatementType('Continue', diverts_flow=True)
Break = StatementType('Break', diverts_flow=True)
Pass = StatementType('Pass')
