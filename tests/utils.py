
""" Common test utilities """

import importlib.util
import importlib.machinery
import subprocess
import sys


def load_source(modname, filename, cache_module=False):
    loader = importlib.machinery.SourceFileLoader(modname, filename)
    spec = importlib.util.spec_from_file_location(modname, filename,
                                                  loader=loader)
    module = importlib.util.module_from_spec(spec)
    if cache_module:
        sys.modules[module.__name__] = module
    loader.exec_module(module)
    return module


def get_result_and_return_code(cmd):
    return_code = 0
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        return_code = e.returncode
        # store only the error, no need for the traceback
        output = e.output.strip().split("\n")[-1]

    print(output)
    return (return_code, output)
