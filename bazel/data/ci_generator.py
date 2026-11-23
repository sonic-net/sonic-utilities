"""Exercise the upstream generator with real Utilities and Click installations.

This bounded CI environment covers commands needing only Click. Image owners
supply the complete SONiC execution toolchain for config/show and native imports.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

import click

parser = argparse.ArgumentParser()
parser.add_argument("--archive", required=True)
parser.add_argument("--generator", required=True)
parser.add_argument("output")
args = parser.parse_args()
output = Path(args.output).absolute()
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    with tarfile.open(args.archive) as archive:
        archive.extractall(directory, filter="data")
    site = Path(directory) / "usr/local/lib/python3.13/dist-packages"
    program = (
        "import sys,runpy; sys.path[:0]=sys.argv[1:3]; "
        "sys.argv=sys.argv[3:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    )
    subprocess.run([
        sys.executable, "-I", "-B", "-c", program,
        str(site), str(Path(click.__file__).resolve().parent.parent),
        str(Path(args.generator).absolute()), "-o", str(output),
    ], check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
