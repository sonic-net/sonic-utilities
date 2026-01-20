#!/usr/bin/env python3

import argparse
from importlib import import_module
import importlib.metadata
from click import BaseCommand
from click.shell_completion import get_completion_class
import os.path


def generate_completions(output_dir):
    entry_points = importlib.metadata.distribution("sonic_utilities").entry_points
    for entry_point in entry_points:
        prog = entry_point.name
        path = entry_point.value
        module_path, _, function_name = path.rpartition(":")
        try:
            module = import_module(module_path)
            function = vars(module).get(function_name)
            if isinstance(function, BaseCommand):
                comp_cls = get_completion_class("bash")
                content = (
                        comp_cls(  # type: ignore
                                 function, {}, prog, f"_{prog.upper()}_COMPLETE"
                                 )
                        .source()
                        .replace("\r\n", "\n")
                        )
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
