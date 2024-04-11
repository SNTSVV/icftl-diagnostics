grammar scsl;

STR:    '"' [a-zA-Z_.:/\-]+  '"';
REAL: '-'? [0-9]+ ('.' [0-9]+)?;
INT :   [0-9]+ ;         // match integers
NEWLINE : '\n' -> skip ; // skip new lines
WS  :   [ \t]+ -> skip ; // toss out whitespace

LB: '(';
RB: ')';
LP: '{';
RP: '}';
LSB: '[';
RSB: ']';
COMMA: ',';
PLUS: '+';
MINUS: '-';

FORALL: 'for every';
EXISTS: 'there is a';
SATISFYING: 'satisfying';
BEFORE: 'before';
AFTER: 'after';
NEXTOPKWS: 'next after';
VALUEKWS: 'value variable';
SIGNALVALUEKWS: 'value signal';
DURATION: 'duration';
TIME: 'timestamp';
TIMEBETWEEN: 'time to';
OR: 'or';
AND: 'and';
NOT: 'not';
TRUE: 'true';
FALSE: 'false';
ATTIME: 'at time';
IN: 'in';
DURING: '.during';
FROM: 'from';

ID  :   [a-zA-Z1-9_]+ ;      // match identifiers

real_number: REAL;
quant: FORALL | EXISTS;
disjunction: OR;
conjunction: AND;
negation: NOT;
value: real_number | string | ID;
variable: ID;
string: STR;
signal_variable: ID;
predicate_name: ID;
beforeTr: BEFORE;
afterTr: AFTER;

/** The start rule; begin parsing here. */
spec: quantifier_block;
quantifier_block: quant_section LP inner RP;
quant_section: quant variable SATISFYING predicate;
inner: quantifier_block | inner disjunction inner | inner conjunction inner | negation LB inner RB |
        TRUE | FALSE | phi_single | phi_multiple | LB inner RB;

predicate: source_code_predicate | timestamp_predicate;

source_code_predicate: dsl_predicate procedure_qualifier |
                        dsl_predicate procedure_qualifier after_qualifier;
dsl_predicate: predicate_name LB predicate_args RB;
predicate_args: string | COMMA string | string predicate_args |;
procedure_qualifier: DURING LB string RB;
after_qualifier: AFTER ts | ;

timestamp_predicate: LSB ts COMMA ts RSB;

expr: ts | tr | c;

ts: variable | real_number | LB TIME c RB | LB TIME tr RB | ts PLUS real_number | LB ts RB;
tr: variable | nextOp | LB tr RB;
c : variable | nextOp | beforeTr tr | afterTr tr | LB c RB;

nextOp: NEXTOPKWS expr SATISFYING predicate;

cmp: '<' | '>' | '=';
arithmetic: PLUS | MINUS;

phi_single: phi_ts | phi_tr | phi_c;
phi_ts: v_ts cmp real_number;
phi_tr: v_tr cmp real_number;
phi_c: v_c cmp value;

phi_multiple: v_c cmp v_c |
                v_ts cmp v_ts |
                timeBetween c FROM c cmp real_number;
timeBetween: TIMEBETWEEN;

v_ts: SIGNALVALUEKWS signal_variable ATTIME ts | LB v_ts RB arithmetic real_number | LB v_ts RB;
v_tr: DURATION tr | LB v_tr RB;
v_c: VALUEKWS string IN c | LB v_c RB arithmetic real_number | LB v_c RB;