"""
Module to hold a class that generates instrumentation code for a specific type of measurement.
"""
import ast
import copy
import typing

from . import GeneratorBase, InstrumentationLine

class CallWrapper(ast.NodeTransformer):
    def __init__(self, wrapper_function: str, arguments_to_prepend: typing.List[typing.Union[int, float, str, bool]]):
        """
        Wraps all function calls with a wrapper function.

        Example:
        ```
        original_tree = ast.parse('f() + g("Arg!")')
        wrapper = CallWrapper('wrap', [0, True])
        modified = wrapper.wrap(original_tree)
        assert(ast.unparse(modified) == "wrap(f, 0, True) + wrap(g, 0, True, 'Arg!')")
        ```

        :param wrapper_function: Wrapper function
        :param arguments_to_prepend: Arguments which should be passed to the wrapper function before any arguments
            of the wrapped call
        """
        self.wrapper_function = wrapper_function
        self.arguments_to_prepend = []
        for value in arguments_to_prepend:
            if isinstance(value, (int, float, str, bool)):
                self.arguments_to_prepend.append(ast.Constant(value))
            else:
                raise TypeError(f'Unsupported type: {type(value)} (supported: int, float, str, bool)')

    def visit_Call(self, call: ast.Call) -> ast.Call:
        modified_call = ast.Call(
            ast.Name(self.wrapper_function, ast.Load()),
            [call.func] + self.arguments_to_prepend + call.args,
            call.keywords
        )
        # noinspection PyTypeChecker
        return self.generic_visit(modified_call)

    def wrap(self, AST: ast.AST) -> ast.AST:
        modified_tree = self.visit(AST)
        ast.fix_missing_locations(modified_tree)
        return modified_tree


class Generator(GeneratorBase):
    def generate_code_line_list(self) -> list[InstrumentationLine]:
        arguments_to_prepend = [
            self._spec_id,
            self._atom_index,
            self._subatom_index,
            self._module_name,
            self._line_index + 1
        ]
        call_wrapper = CallWrapper('SCSL.Monitoring.monitoring._wrap_function', arguments_to_prepend)

        # Find the node (i.e., sub-tree) containing the call(s) that need to be instrumented
        node_to_instrument: ast.AST = None
        for node in ast.walk(self._module_ast):
            if isinstance(node, (ast.stmt, ast.expr)) \
                and node.lineno == self._line_index + 1:
                if node_to_instrument is None or (
                        (node.lineno, node.col_offset) < (node_to_instrument.lineno, node_to_instrument.col_offset)
                        and (node.end_lineno, node.col_offset) > (node_to_instrument.end_lineno, node_to_instrument.end_col_offset)
                ):
                    node_to_instrument = node

        lines_to_delete = range(node_to_instrument.lineno, node_to_instrument.end_lineno + 1)
        modified_line_ast = call_wrapper.wrap(node_to_instrument)

        instrumented_line = self._indentation + ast.unparse(modified_line_ast).replace('\n', '\n' + self._indentation)
        code_line_list = [
            InstrumentationLine(self._module_name, self._line_index, instrumented_line, "measurement", lines_to_delete)
        ]
        return code_line_list
