grammar pecl;

STR:    '"' [a-zA-Z_.:/\-]+  '"';
REAL: '-'? [0-9]+ ('.' [0-9]+)?;
INT :   [0-9]+ ;         // match integers
NEWLINE : '\n' -> skip ; // skip new lines
WS  :   [ \t]+ -> skip ; // toss out whitespace

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

ID  :   [a-zA-Z1-9_]+ ;      // match identifiers

pecl: duration | timeBetween | whenever;

string: STR;

predicate: dsl_predicate procedure_qualifier;
predicate_name: ID;
dsl_predicate: predicate_name LB predicate_args RB;
predicate_args: string | COMMA string | string predicate_args |;
procedure_qualifier: DURING LB string RB;

cmp: '<' | '>' | '<=' | '>=' | '=';
number: INT | REAL;

constant: number | string;

duration: DURATION LB predicate RB cmp number;

timeBetween: TIMEBETWEEN predicate COMMA predicate cmp number;

whenever: WHENEVER guard EVENTUALLY expectation;
guard: predicate | constraint;
expectation: predicate | constraint;

constraint: function_constraint | state_constraint;
function_constraint: function_measurement cmp number | LB function_constraint RB;
function_measurement: DURATION predicate | LB function_measurement RB;
state_constraint: state_measurement cmp constant | LB state_constraint RB;
state_measurement: VALUEKWS string IN predicate | LB state_measurement RB;