"""
Module containing SCFG factories.
"""

import ast


def find_function_definition(module_ast: ast.Module, function_name: str) -> ast.FunctionDef:
    """
    Given a fully-qualified function name, its module and asts of its module, find the relevant ast in module_ast
    
    :param module_ast: The AST of the module
    :param function_name: The name of the function within the scope of the module (e.g. "SomeClass.some_method")
    """

    # from the module, find the appropriate function ast
    # initialise a list of pairs (path to ast, ast)
    # stack = list(map(lambda item : ("", item), module_asts.body))
    stack = [("", item) for item in module_ast.body]
    while len(stack) > 0:
        prefix, ast_obj = stack.pop()
        if type(ast_obj) is ast.FunctionDef:
            # if we have a function definition, check the path
            fully_qualified_function_name = ("" if prefix == "" else prefix + ".") + ast_obj.name
            if fully_qualified_function_name == function_name:
                return ast_obj
        elif hasattr(ast_obj, "body"):
            # if we don't have a function definition, but we have a "body" attribute
            # then we could have a conditional or a class definition
            # (we assume no loops at top-level of a module)
            if type(ast_obj) in [ast.If, ast.Try, ast.ExceptHandler]:
                stack += [(prefix, item) for item in ast_obj.body]
            elif type(ast_obj) is ast.ClassDef:
                stack += [(("" if prefix == "" else prefix + ".") + ast_obj.name, item) for item in ast_obj.body]

