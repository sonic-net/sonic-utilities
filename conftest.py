"""Root-level conftest for pytest-xdist parallelization.

All test files run in parallel using loadfile distribution.
"""

# These are standalone Bazel command-line programs with positional artifact
# arguments. Product pytest discovery remains unchanged.
collect_ignore = [
    "bazel/runtime/contract_test.py",
    "bazel/wheel_contract_test.py",
    "bazel/wheel_installed_test.py",
]
