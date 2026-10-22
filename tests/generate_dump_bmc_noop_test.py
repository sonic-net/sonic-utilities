"""
Pytest wrapper for the generate_dump BMC noop bash unit test.

The assertions live in ``generate_dump_bmc_noop_test.sh``, which extracts the
BMC debug log dump steps out of scripts/generate_dump and exercises them with
mocked collaborators.  This wrapper runs that script under pytest so CI picks
it up, the same way ``save_sai_failure_dump_test.py`` does.
"""

import os
import subprocess


def test_generate_dump_bmc_noop():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(test_dir, "generate_dump_bmc_noop_test.sh")

    result = subprocess.run(
        ["bash", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    print(result.stdout)
    assert result.returncode == 0, f"generate_dump_bmc_noop_test.sh failed:\n{result.stdout}"
