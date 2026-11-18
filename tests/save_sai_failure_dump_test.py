"""
Pytest wrapper for the save_sai_failure_dump() bash unit test.

The actual assertions live in the self-contained bash script
``save_sai_failure_dump_test.sh`` (it extracts the save_sai_failure_dump
function out of scripts/generate_dump and exercises it with mocked
collaborators).  This wrapper simply runs that script under pytest so the
existing CI (which collects ``*_test.py`` via pytest) picks it up, mirroring
how ``sign_and_verify_test.py`` drives ``verify_image_sign_test.sh``.
"""

import os
import subprocess


def test_save_sai_failure_dump():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(test_dir, "save_sai_failure_dump_test.sh")

    result = subprocess.run(
        ["bash", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    # Surface the bash script output so a failure is easy to diagnose in CI.
    print(result.stdout)
    assert result.returncode == 0, f"save_sai_failure_dump_test.sh failed:\n{result.stdout}"
