"""
Module containing logic for building a symbolic control-flow graph given a Python 3 program.
"""

import ast
import inspect
import logging
import pathlib
import typing

from SCFG import SCFG, SymbolicState, Expression
from . import statement_types
from .prepare import find_function_definition


def scfg_from_source(function_name: str,
                     module_path: typing.Union[str, pathlib.Path],
                     ignore_literals: bool = True) -> SCFG:
    path = pathlib.Path(module_path)
    module_name = path.stem  # The stem is the name of the file without the file extension

    with path.open() as source:
        tree = ast.parse(source.read())

    func_def = find_function_definition(tree, function_name)
    if func_def is None:
        raise ValueError(f'Function {function_name} could not be found in {module_path}!')

    return scfg_from_ast(func_def, ignore_literals)


def scfg_from_qualified_name(qualified_name: str,
                             root_directory: typing.Union[str, pathlib.Path],
                             ignore_literals: bool = True) -> SCFG:
    """
    Constructs an SCFG given the "qualified name" of a function, e.g. src/some_module.py:SomeClass.some_method

    :param qualified_name: A name of the format path:[class.]*function
    :param root_directory: The directory in which relative_path is contained
    :param ignore_literals: Do not consider literals as mentioned symbols (default)
    """
    rel_path, _, func_name = qualified_name.partition(':')
    path = pathlib.Path(root_directory,  rel_path)
    return scfg_from_source(func_name, path, ignore_literals)


def scfg_from_ast(function_ast: ast.FunctionDef, ignore_literals: bool = True) -> SCFG:
    """
    Constructs an SCFG from the abstract syntax tree (AST) of a Python function
    :param function_ast: The definition of a Python function
    :param ignore_literals: Do not consider literals as mentioned symbols (default)
    :return: The resulting SCFG object
    """
    # initialise an empty SCFG
    scfg = SCFG()
    scfg.procedure_name=function_ast.name
    # store asts
    scfg._program_asts = function_ast.body
    # store function arguments and mark them as 'written' at EnterProcedure
    scfg.procedure_parameters = [arg.arg for arg in function_ast.args.args]
    scfg.entry_point.expressions.append(Expression(read=set(), written=set(scfg.procedure_parameters), called=set()))
    # build the SCFG recursively
    final_state = _subprogram_to_scfg(scfg, scfg._program_asts, scfg.entry_point, ignore_literals=ignore_literals)
    # Connect the final symbolic state to the exit point
    final_state.add_child(scfg.exit_point)

    return scfg


def scfg_from_string(source_code: str, ignore_literals: bool = True) -> SCFG:
    _ast = ast.parse(source_code)
    if not hasattr(_ast, 'body') or not _ast.body or not isinstance(_ast.body[0], ast.FunctionDef):
        raise ValueError(f'"{source_code}" does not start with a function definition!')

    return scfg_from_ast(_ast.body[0], ignore_literals=ignore_literals)

def scfg_from_function_object(function: typing.Callable, ignore_literals: bool = True) -> SCFG:
    if not inspect.isroutine(function):
        if hasattr(function, '__name__'):
            name = f'"{function.__name__}"'
        else:
            name = 'argument'
        raise TypeError(name + ' is not a function or a method!')
    elif function.__name__ == '<lambda>':
        raise TypeError('lambda functions are not supported!')

    return scfg_from_ast(ast.parse(inspect.getsource(function)).body[0], ignore_literals)


def _subprogram_to_scfg(scfg: SCFG,
                        subprogram: list,
                        parent_symbolic_state: SymbolicState,
                        loop_entry_point: typing.Optional[SymbolicState] = None,
                        loop_exit_point: typing.Optional[SymbolicState] = None,
                        ignore_literals: bool = True) -> SymbolicState:
    """
    Given a list of asts and a symbolic state from which the first symbolic state
    that we generate should be reachable via an edge, process each one in order to recursively
    construct a symbolic control-flow graph.
    """
    # set the previous symbolic state
    previous_symbolic_state = parent_symbolic_state

    # iterate through the current subprogram
    for subprogram_ast in subprogram:
        logging.info(f"Processing AST {subprogram_ast}")

        # check for the type of the current ast
        if type(subprogram_ast) in [ast.Assign, ast.Expr, ast.AugAssign]:
            logging.info(f"AST {subprogram_ast} is {type(subprogram_ast)} instance")

            # instantiate the symbolic state
            new_symbolic_state: SymbolicState = process_expression_ast(subprogram_ast, subprogram, ignore_literals=ignore_literals)

            # add it to the list of vertices
            scfg.symbolic_states.append(new_symbolic_state)

            logging.info(
                f"Instantiated new_symbolic_state = {new_symbolic_state} and added to self._symbolic_states with self = {scfg}")
            # set it as the child of the previous
            if not previous_symbolic_state.statement_type.diverts_flow:
                logging.info(
                    f"Calling previous_symbolic_state.add_child with previous_symbolic_state = {previous_symbolic_state} and new_symbolic_state = {new_symbolic_state}")
                previous_symbolic_state.add_child(new_symbolic_state)
            logging.info(f"Setting previous_symbolic_state = {new_symbolic_state}")
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) is ast.If:
            logging.info(f"Type of sub_program_ast = {subprogram_ast} is ast.If")

            # deal with the main body of the conditional

            # instantiate symbolic states for entry and exit
            logging.info(f"Setting up conditional entry and exit symbolic states")
            entry_symbolic_state = SymbolicState(statement_type=statement_types.If,
                                                 expressions=[process_fragment_ast(subprogram_ast.test, ignore_literals=ignore_literals)],
                                                 line_number=subprogram_ast.lineno,
                                                 column_offset=subprogram_ast.col_offset,
                                                 end_line_number=subprogram_ast.end_lineno,
                                                 end_column_offset=subprogram_ast.end_col_offset)
            exit_symbolic_state = SymbolicState(statement_type=statement_types.EndIf)
            scfg.symbolic_states += [entry_symbolic_state, exit_symbolic_state]
            logging.info(
                f"Entry state is {entry_symbolic_state} and exit state is {exit_symbolic_state}")
            # set the entry symbolic state as a child of the previous
            if not previous_symbolic_state.statement_type.diverts_flow:
                logging.info(
                    f"Adding {entry_symbolic_state} as a child of {previous_symbolic_state}")
                previous_symbolic_state.add_child(entry_symbolic_state)
            entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)
            # recursive on the conditional body
            logging.info(
                f"Recursing on body of conditional with _subprogram_to_scfg, linking to parent entry_symbolic_state = {entry_symbolic_state}")
            final_body_symbolic_state = _subprogram_to_scfg(
                scfg,
                subprogram=subprogram_ast.body,
                parent_symbolic_state=entry_symbolic_state,
                loop_entry_point=loop_entry_point,
                loop_exit_point=loop_exit_point,
                ignore_literals=ignore_literals
            )
            # set the exit symbolic state as a child of the final one from the body
            logging.info(
                f"Setting {exit_symbolic_state} as child of final_body_symbolic_state = {final_body_symbolic_state}")
            if not final_body_symbolic_state.statement_type.diverts_flow:
                final_body_symbolic_state.add_child(exit_symbolic_state)

            # check for orelse block
            # if there is none, set the conditional exit vertex as a child of the entry vertex
            # if there is, process it as a separate block
            logging.info(f"Checking for length of subprogram_ast.orelse")
            if len(subprogram_ast.orelse) != 0:
                logging.info(f"An orelse block was found - recursing with parent {entry_symbolic_state}")
                # there is an orelse block - process it
                final_orelse_symbolic_state = _subprogram_to_scfg(
                    scfg,
                    subprogram=subprogram_ast.orelse,
                    parent_symbolic_state=entry_symbolic_state,
                    loop_entry_point=loop_entry_point,
                    loop_exit_point=loop_exit_point,
                    ignore_literals=ignore_literals)
                # link final state with exit state
                if not final_orelse_symbolic_state.statement_type.diverts_flow:
                    final_orelse_symbolic_state.add_child(exit_symbolic_state)
            else:
                logging.info(
                    f"No orelse block was found - adding {exit_symbolic_state} as child of {entry_symbolic_state}")
                # there is no orelse block
                entry_symbolic_state.add_child(exit_symbolic_state)
                entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)

            # update the previous symbolic state for the next iteration
            previous_symbolic_state = exit_symbolic_state

        elif type(subprogram_ast) is ast.Try:
            logging.info(f"Type of sub_program_ast = {subprogram_ast} is ast.Try")

            # deal with the main body and the handlers

            # instantiate symbolic states for entry and exist
            logging.info(f"Setting up try-except entry and exit symbolic states")
            entry_symbolic_state = SymbolicState(statement_type=statement_types.Try,
                                                 line_number=subprogram_ast.lineno,
                                                 column_offset=subprogram_ast.col_offset,
                                                 end_line_number=subprogram_ast.end_lineno,
                                                 end_column_offset=subprogram_ast.end_col_offset
                                                 )
            exit_symbolic_state = SymbolicState(statement_type=statement_types.EndTry)
            scfg.symbolic_states += [entry_symbolic_state, exit_symbolic_state]
            logging.info(
                f"Entry state is entry_symbolic_state = {entry_symbolic_state} and exit state is exit_symbolic_state = {exit_symbolic_state}")
            # set the entry symbolic state as a child of the previous
            if not previous_symbolic_state.statement_type.diverts_flow:
                logging.info(
                    f"Adding entry_symbolic_state = {entry_symbolic_state} as a child of {previous_symbolic_state}")
                previous_symbolic_state.add_child(entry_symbolic_state)
            entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)

            # recurse on the main body
            logging.info(
                f"Recursing on body of try-except with _subprogram_to_scfg, linking to parent entry_symbolic_state = {entry_symbolic_state}")
            final_body_symbolic_state = _subprogram_to_scfg(
                scfg,
                subprogram=subprogram_ast.body,
                parent_symbolic_state=entry_symbolic_state,
                loop_entry_point=loop_entry_point,
                loop_exit_point=loop_exit_point,
                ignore_literals=ignore_literals)
            # set the exit symbolic state as a child of the final one from the body
            logging.info(
                f"Setting {exit_symbolic_state} as child of final_body_symbolic_state = {final_body_symbolic_state}")
            if not final_body_symbolic_state.statement_type.diverts_flow:
                final_body_symbolic_state.add_child(exit_symbolic_state)

            # recurse on each handler
            for handler in subprogram_ast.handlers:
                logging.info(
                    f"Recursing on handler of try-except with _subprogram_to_scfg, linking to parent entry_symbolic_state = {entry_symbolic_state}")
                final_body_symbolic_state = _subprogram_to_scfg(
                    scfg,
                    subprogram=handler.body,
                    parent_symbolic_state=entry_symbolic_state,
                    loop_entry_point=loop_entry_point,
                    loop_exit_point=loop_exit_point,
                    ignore_literals=ignore_literals)
                # set the exist symbolic state as a child of the final one from the body
                logging.info(
                    f"Setting {exit_symbolic_state} as child of final_body_symbolic_state = {final_body_symbolic_state}")
                if not final_body_symbolic_state.statement_type.diverts_flow:
                    final_body_symbolic_state.add_child(exit_symbolic_state)

            # update the previous symbolic state for the next iteration
            previous_symbolic_state = exit_symbolic_state

        elif type(subprogram_ast) in [ast.For, ast.AsyncFor]:
            logging.info(f"Type of subprogram_ast = {subprogram_ast} is ast.For")

            # deal with the body of the for loop

            # instantiate symbolic states for entry and exit
            logging.info(f"Setting up for-loop entry and exit symbolic states")

            entry_symbolic_state = SymbolicState(statement_type=statement_types.For,
                                                 expressions=[
                                                     process_fragment_ast(subprogram_ast.target, dest='written', ignore_literals=ignore_literals),
                                                     process_fragment_ast(subprogram_ast.iter, ignore_literals=ignore_literals)
                                                 ],
                                                 line_number=subprogram_ast.lineno,
                                                 column_offset=subprogram_ast.col_offset,
                                                 end_line_number=subprogram_ast.end_lineno,
                                                 end_column_offset=subprogram_ast.end_col_offset)
            exit_symbolic_state = SymbolicState(statement_type=statement_types.EndFor)
            scfg.symbolic_states += [entry_symbolic_state, exit_symbolic_state]
            logging.info(
                f"Entry state is {entry_symbolic_state} and exit state is exit_symbolic_state = {exit_symbolic_state}")
            # set the entry symbolic state as a child of the previous
            if not previous_symbolic_state.statement_type.diverts_flow:
                logging.info(
                    f"Adding {entry_symbolic_state} as a child of {previous_symbolic_state}")
                previous_symbolic_state.add_child(entry_symbolic_state)

            entry_symbolic_state.add_child(exit_symbolic_state)
            entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)
            # recursive on the loop body
            logging.info(f"Recursing on body of loop, linking to parent {entry_symbolic_state}")
            final_body_symbolic_state = _subprogram_to_scfg(
                scfg,
                subprogram=subprogram_ast.body,
                parent_symbolic_state=entry_symbolic_state,
                loop_entry_point=entry_symbolic_state,
                loop_exit_point=exit_symbolic_state,
                ignore_literals=ignore_literals)
            # set for loop entry symbolic state as child of final state in body
            logging.info(
                f"Setting entry symbolic state {entry_symbolic_state} as child of final state {final_body_symbolic_state}")
            final_body_symbolic_state.add_child(entry_symbolic_state)

            # update the previous symbolic state for the next iteration
            previous_symbolic_state = exit_symbolic_state

        elif type(subprogram_ast) is ast.While:
            logging.info(f"Type of subprogram_ast = {subprogram_ast} is ast.While")

            # deal with the body of the while loop

            # instantiate symbolic states while entry and exit
            logging.info(f"Setting up while-loop entry and exit symbolic states")
            # instantiate states
            entry_symbolic_state = SymbolicState(statement_type=statement_types.While,
                                                 expressions=[process_fragment_ast(subprogram_ast.test, ignore_literals=ignore_literals)])
            exit_symbolic_state = SymbolicState(statement_type=statement_types.EndWhile)
            scfg.symbolic_states += [entry_symbolic_state, exit_symbolic_state]
            logging.info(
                f"Entry state is entry_symbolic_state = {entry_symbolic_state} and exit state is exit_symbolic_state = {exit_symbolic_state}")
            # set the entry symbolic state as a child of the previous
            if not previous_symbolic_state.statement_type.diverts_flow:
                logging.info(
                    f"Adding entry_symbolic_state = {entry_symbolic_state} as a child of previous_symbolic_state = {previous_symbolic_state}")
                previous_symbolic_state.add_child(entry_symbolic_state)
            entry_symbolic_state.add_child(exit_symbolic_state)
            entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)
            # recursive on the loop body
            logging.info(f"Recursing on body of loop, linking to parent {entry_symbolic_state}")
            final_body_symbolic_state = _subprogram_to_scfg(
                scfg,
                subprogram=subprogram_ast.body,
                parent_symbolic_state=entry_symbolic_state,
                loop_entry_point=entry_symbolic_state,
                loop_exit_point=exit_symbolic_state,
                ignore_literals=ignore_literals)
            # set for loop entry symbolic state as child of final state in body
            logging.info(
                f"Setting entry symbolic state {entry_symbolic_state} as child of final state final_body_symbolic_state = {final_body_symbolic_state}")
            final_body_symbolic_state.add_child(entry_symbolic_state)

            # update the previous symbolic state for the next iteration
            previous_symbolic_state = exit_symbolic_state

        elif type(subprogram_ast) is ast.Return:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Return,
                expressions=[] if subprogram_ast.value is None else [process_fragment_ast(subprogram_ast.value, ignore_literals=ignore_literals)],
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            new_symbolic_state.add_child(scfg.exit_point)
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) is ast.Delete:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Del,
                expressions=[process_fragment_ast(subprogram_ast.targets,'written', ignore_literals=ignore_literals)],
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            new_symbolic_state.add_child(scfg.exit_point)
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) is ast.Raise:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Raise,
                expressions=[] if subprogram_ast.exc is None else [process_fragment_ast(subprogram_ast.exc, ignore_literals=ignore_literals)],
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            new_symbolic_state.add_child(scfg.exit_point)
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) is ast.Pass:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Pass,
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) in [ast.With, ast.AsyncWith]:
            entry_symbolic_state = SymbolicState(
                statement_type=statement_types.With,
                expressions=[
                    process_fragment_ast(item.context_expr, ignore_literals=ignore_literals) |
                    process_fragment_ast(item.optional_vars, 'written', ignore_literals=ignore_literals) if item.optional_vars is not None
                        else Expression(set(), set(), set())
                    for item in subprogram_ast.items],
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            exit_symbolic_state = SymbolicState(statement_types.EndWith)
            entry_symbolic_state.add_child(exit_symbolic_state, exit_state=True)

            scfg.symbolic_states += [entry_symbolic_state, exit_symbolic_state]
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(entry_symbolic_state)
            final_body_symbolic_state = _subprogram_to_scfg(
                scfg,
                subprogram=subprogram_ast.body,
                parent_symbolic_state=entry_symbolic_state,
                loop_entry_point=loop_entry_point,
                loop_exit_point=loop_exit_point,
                ignore_literals=ignore_literals)
            if not final_body_symbolic_state.statement_type.diverts_flow:
                final_body_symbolic_state.add_child(exit_symbolic_state)
            previous_symbolic_state = exit_symbolic_state

        elif type(subprogram_ast) is ast.Continue:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Continue,
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            if loop_entry_point is not None:
                new_symbolic_state.add_child(loop_entry_point)
            previous_symbolic_state = new_symbolic_state

        elif type(subprogram_ast) is ast.Break:
            new_symbolic_state = SymbolicState(
                statement_type=statement_types.Break,
                line_number=subprogram_ast.lineno,
                column_offset=subprogram_ast.col_offset,
                end_line_number=subprogram_ast.end_lineno,
                end_column_offset=subprogram_ast.end_col_offset
            )

            scfg.symbolic_states.append(new_symbolic_state)
            if not previous_symbolic_state.statement_type.diverts_flow:
                previous_symbolic_state.add_child(new_symbolic_state)
            if loop_exit_point is not None:
                new_symbolic_state.add_child(loop_exit_point)
            previous_symbolic_state = new_symbolic_state

        logging.info(f"Moving to next iteration with previous_symbolic_state = {previous_symbolic_state}")

    # return the final symbolic state from this subprogram
    return previous_symbolic_state


def process_expression_ast(stmt_ast: typing.Union[ast.Expr, ast.Assign],
                           stmt_ast_parent_block,
                           ignore_literals: bool = True):
    """
    Instantiate a new SymbolicState instance based on this expression statement.
    """
    # first, add a reference from stmt_ast to its parent block
    stmt_ast.parent_block = stmt_ast_parent_block
    logging.info(f"Instantiating a symbolic state for AST instance stmt_ast = {stmt_ast}")

    if type(stmt_ast) is ast.Expr:
        # If the expression contains a yield, show it as YieldExp instead of Exp
        if any(isinstance(node, ast.Yield) for node in ast.walk(stmt_ast)):
            expression_type = statement_types.YieldExp
        else:
            expression_type = statement_types.Exp

        s = SymbolicState(
            statement_type=expression_type,
            expressions=[process_fragment_ast(stmt_ast, ignore_literals=ignore_literals)],
            line_number=stmt_ast.lineno,
            column_offset=stmt_ast.col_offset,
            end_line_number=stmt_ast.end_lineno,
            end_column_offset=stmt_ast.end_col_offset
        )
    elif type(stmt_ast) in [ast.Assign, ast.AugAssign]:
        # If the assignment contains a yield, show it as YieldAssign instead of Exp
        if any(type(node) is ast.Yield for node in ast.walk(stmt_ast)):
            expression_type = statement_types.YieldAssign
        else:
            expression_type = statement_types.Assign

        # If the assignment is an augmented assignment (e.g. a+= 1),
        # 1) it has a field called `target` rather than `targets`
        # 2) show `a` in both `read` and `written`, equivalently to `a = a + 1`.
        if type(stmt_ast) is ast.AugAssign:
            expressions = [
                process_fragment_ast(stmt_ast.target, dest='written', ignore_literals=ignore_literals),
                process_fragment_ast(stmt_ast.value, ignore_literals=ignore_literals)
            ]
            expressions[1].read.update(expressions[0].written)
        else:
            expressions = [
                process_fragment_ast(stmt_ast.targets, dest='written', ignore_literals=ignore_literals),
                process_fragment_ast(stmt_ast.value, ignore_literals=ignore_literals)
            ]

        s = SymbolicState(
            statement_type=expression_type,
            expressions=expressions,
            line_number=stmt_ast.lineno,
            column_offset=stmt_ast.col_offset,
            end_line_number=stmt_ast.end_lineno,
            end_column_offset=stmt_ast.end_col_offset
        )
    else:
        raise TypeError

    return s


def process_fragment_ast(ast_fragment,
                         dest: typing.Literal['read', 'written', 'called'] = 'read',
                         ignore_literals: bool = True) -> Expression:
    """
    Process all of the names appearing in a portion of an AST

    This function

    :param ast_fragment: An AST node representing an expresion, or a list of such nodes
    :param dest: The field where symbols at the root level of the node(s) belong
    :param ignore_literals: Do not consider literals as mentioned symbols (default)

    """
    # initialise expression
    e: Expression = Expression(read=set(), written=set(), called=set())

    # initialize consumed symbols (which will be ignored later in
    # the walk to avoid double counting) to an empty list
    consumed_symbols: typing.List[ast.expr] = []

    if isinstance(ast_fragment, list):
        nodes = ast_fragment
    else:
        nodes = [ast_fragment]

    mentioned = set()

    # walk the ast to find the symbols used
    for node in nodes:
        for symbol in ast.walk(node):
            if symbol in consumed_symbols:
                # This symbol was part of an attribute which we already added to used
                continue
            # extract information according to type
            if type(symbol) is ast.Name:
                mentioned.add(symbol.id)
            elif type(symbol) is ast.Constant and not ignore_literals:
                if isinstance(symbol.value, str):
                    mentioned.add("'" + str(symbol.value) + "'")
                else:
                    mentioned.add(str(symbol.value))
            elif type(symbol) is ast.Attribute:
                result = resolve_attribute(symbol, consumed_symbols)
                if result is not None:
                    mentioned.add(result)
            elif type(symbol) is ast.Call:
                e |= process_fragment_ast(symbol.func, 'called', ignore_literals=ignore_literals)
                consumed_symbols.append(symbol.func)
            elif type(symbol) is ast.NamedExpr:
                e |=  process_fragment_ast(symbol.target, 'written', ignore_literals=ignore_literals)
                consumed_symbols.append(symbol.target)

        if dest == 'read':
            e.read |= mentioned
        elif dest == 'written':
            e.written |= mentioned
        elif dest == 'called':
            e.called |= mentioned
        else:
            raise ValueError(f'process_fragment_ast: uncrecognized dest "{dest}"')

        return e


def resolve_attribute(attr: ast.Attribute, consumed_symbols: typing.List[ast.expr]) -> typing.Optional[str]:
    """
    Recursively walk up a chain of attributes so as to convert it to a string

    If given an uninterrupted sequence of attributes, this helper function will give its string
    representation. For instance, when given the Attribute object for `a.b.c.d`, this function
    will return the string 'a.b.c.d'. The objects for a, b, and c will then be added to
    consumed_symbols. This allows walking an AST tree using ast.walk, passing every encountered
    attribute to this helper function, and then ignoring symbols in consumed_symbols. In the
    example above, d will be encountered first, deriving 'a.b.c.d', and then ignoring the
    symbols in consumed_symbols will ensure that 'a', 'b', and 'c' are only encountered once.

    However, if attr is not the representation of an uninterrupted sequence of attributes, this
    function will return None. Nothing will then be added to consumed_symbols, so that any
    symbols appearing in the expression can then be processed during the walk. This will happen
    for Attribute objects containing, for example, the following:

    - subscripts: `a[0].b`
    - arithmetic operations (e.g. BinOp): (2 + 3).bit_length()
    - etc.

    :param attr: The attribute object representing the rightmost attribute (d in `a.b.c.d`)
    :param consumed_symbols: A list to which consumed symbols will be appended
    :return: String representation of attr, or None
    """
    # If the parent is a Name, just concatenate, consume, and return
    if type(attr.value) is ast.Name:
        consumed_symbols.append(attr.value)
        return attr.value.id + '.' + attr.attr

    # If the parent is an Attribute, recurse
    elif type(attr.value) is ast.Attribute:
        parent = resolve_attribute(attr.value, consumed_symbols)
        if parent is None:
            return None
        else:
            consumed_symbols.append(attr.value)
            return parent + '.' + attr.attr
    else:
        # Parent is of a type we cannot resolve (BinOp, Subscript, etc.)
        # This means that the actual object being referenced probably cannot be resolved
        # statically. Give up.
        return None
