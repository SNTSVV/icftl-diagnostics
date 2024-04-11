import argparse
import pathlib
import platform
import subprocess

from . import scfg_from_qualified_name

def main():
    parser = argparse.ArgumentParser(
        'generate-scfg',
        description='Draws the symbolic-control flow graph (SCFG) of a given Python function',
        epilog='The files <function_name>.dot and <functon_name>.dot.pdf will be created.'
    )
    parser.add_argument(
        'function_name',
        metavar='MODULE_PATH:[CLASS.]*FUNCTION',
        help='Qualified name of a Python function (e.g. "src/some_module.py:SomeClass.some_method")')

    args = parser.parse_args()

    # Generate and write out the SCFG
    scfg = scfg_from_qualified_name(args.function_name, '.')
    filename_stem = args.function_name.partition(':')[2]
    scfg.write_to_file(f'{filename_stem}.dot')

    # Try to open the resulting pdf file with the default application
    open_command = None
    if platform.system() == 'Darwin':
        open_command = 'open'
    elif platform.system() == 'Windows':
        open_command = 'start'
    elif platform.system() == 'Linux':
        open_command = 'xdg-open'

    if open_command is not None:
        subprocess.run([open_command, f'{filename_stem}.dot.pdf'])
