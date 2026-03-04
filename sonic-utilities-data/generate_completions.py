#!/usr/bin/env python3

import argparse
from importlib import import_module
import importlib.metadata
from click import BaseCommand
import os.path

# Click 8 outputs completions as "type,value" per line. Use bash_complete and
# parse to extract only the value; redirect stderr so help text is not used.
BASH_COMPLETION_TEMPLATE = """_%(func)s() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \\
                   COMP_CWORD=$COMP_CWORD \\
                   %(complete_var)s=bash_complete $1 2>/dev/null | \\
                   while IFS= read -r line; do
                     [[ "$line" == *,* ]] && echo "${line##*,}"
                   done ) )
    return 0
}

complete -F _%(func)s -o default %(prog)s;
"""


def generate_completions(output_dir):
    entry_points = importlib.metadata.distribution("sonic_utilities").entry_points
    for entry_point in entry_points:
        prog = entry_point.name
        path = entry_point.value
        module_path, _, function_name = path.rpartition(":")
        try:
            # The below line is to import each of the CLI modules from the
            # sonic_utilities package. This is happening only in a build-time
            # environment with the intention of generating bash completions.
            module = import_module(module_path)  # nosem
            function = vars(module).get(function_name)
            if isinstance(function, BaseCommand):
                complete_var = "_{}_COMPLETE".format(prog.upper().replace("-", "_"))
                func = prog.replace("-", "_") + "_completion"
                content = BASH_COMPLETION_TEMPLATE % {
                    "func": func,
                    "complete_var": complete_var,
                    "prog": prog,
                }
                with open(os.path.join(output_dir, prog), "w", newline="") as f:
                    f.write(content)
        except Exception:
            print(f"Cannot generate completion for {path}!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output-dir", default=".",
                        help="The output directory of the generated completions")
    args = parser.parse_args()

    generate_completions(args.output_dir)
