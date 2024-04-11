grammar peclMultiSpec;

STR:    '"' [a-zA-Z0-9_.:/\-]+  '"';
REAL: '-'? [0-9]+ ('.' [0-9]+)?;
INT :   [0-9]+ ;         // match integers
NEWLINE : '\n' ;
WS  :   [ \t]+ -> skip ; // toss out whitespace
LINE_COMMENT : '#' ~[\r\n]* -> skip; // ignore comments

LB: '(';
RB: ')';
COMMA: ',';
DURATION: 'duration';
TIMEBETWEEN: 'timeBetween';
WHENEVER: 'whenever';
EVENTUALLY: 'eventually';
DURING: '.during';
VALUEKWS: 'value';
IN: 'in';
PYTHONNONE: 'None';
PYTHONTRUE: 'True';
PYTHONFALSE: 'False';

ID  :   [a-zA-Z1-9_.]+ ;      // match identifiers

// utility symbols
cmp: '<' | '>' | '<=' | '>=' | '=' | '!=';
number: INT | REAL;
constant: number | string | python_symbol;
string: STR;
python_symbol: PYTHONNONE | PYTHONTRUE | PYTHONFALSE;

// starting rule
peclMultiSpec: (block | NEWLINE)*;

block: duration | timeBetween | whenever;

// line types
duration: DURATION LB predicate RB NEWLINE* cmp NEWLINE* number NEWLINE*;
timeBetween: TIMEBETWEEN NEWLINE* predicate NEWLINE* COMMA NEWLINE* predicate NEWLINE* cmp NEWLINE* number NEWLINE*;
whenever: WHENEVER NEWLINE* guard NEWLINE* EVENTUALLY NEWLINE* expectation NEWLINE*;

// predicates
predicate: dsl_predicate NEWLINE* procedure_qualifier;
predicate_name: ID;
dsl_predicate: predicate_name LB predicate_args RB;
predicate_args: string | COMMA string | string predicate_args |;
procedure_qualifier: DURING LB string RB;

// rules for 'whenever' line
guard: predicate | constraint;
expectation: predicate | constraint;
constraint: function_constraint | state_constraint;
function_constraint: function_measurement cmp number | LB function_constraint RB;
function_measurement: DURATION predicate | LB function_measurement RB;
state_constraint: state_measurement cmp constant | LB state_constraint RB;
state_measurement: VALUEKWS string IN predicate | LB state_measurement RB;