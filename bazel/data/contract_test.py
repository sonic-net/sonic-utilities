"""Validate data installation against the original Debian install manifest."""
import gzip
from pathlib import Path
import sys
import tarfile

from click.shell_completion import BashComplete

archive, recipe = map(Path, sys.argv[1:])
source = recipe.parent.parent
with tarfile.open(archive) as tar:
    members = {m.name.lstrip("./"): m for m in tar.getmembers() if m.isfile()}
    expected_templates = {}
    for line in recipe.read_text().splitlines():
        pattern, destination = line.split()
        if pattern.startswith("templates/"):
            for file in source.glob(pattern):
                expected_templates[destination.strip("/") + "/" + file.name] = file
    actual_templates = {n for n in members if n.startswith("usr/share/sonic/templates/")}
    assert actual_templates == expected_templates.keys()
    for name, file in expected_templates.items():
        assert tar.extractfile(members[name]).read() == file.read_bytes(), name
    # connect is an actual upstream Click CLI whose dependencies fit this
    # bounded toolchain. Full SONiC imports are checked by the image consumer.
    expected = BashComplete(None, {}, "connect", "_CONNECT_COMPLETE").source()
    assert tar.extractfile(members["etc/bash_completion.d/connect"]).read().decode() == expected
    doc = "usr/share/doc/sonic-utilities-data/"
    assert tar.extractfile(members[doc + "copyright"]).read() == (source / "debian/copyright").read_bytes()
    assert gzip.decompress(tar.extractfile(members[doc + "changelog.Debian.gz"]).read()) == (source / "debian/changelog").read_bytes()
    for name, member in members.items():
        # Debian dh_fixperms installs ordinary package data as root-owned 0644.
        assert (member.uid, member.gid, member.mode) == (0, 0, 0o644), name
print("Debian template inventory, real Click completion, documentation and installation modes: PASS")
