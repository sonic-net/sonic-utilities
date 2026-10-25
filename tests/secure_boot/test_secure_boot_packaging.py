"""Packaging/wiring tests for the Secure Boot backend entry points.

Proves the wrappers shipped by ``sonic-utilities-data`` delegate to the
``secure_boot`` modules from the ``sonic-utilities`` wheel, and that
``debian/install`` maps them to the exact HLD runtime locations.
"""

import importlib
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_SCRIPTS = os.path.join(REPO_ROOT, "sonic-utilities-data", "scripts")
INSTALL_FILE = os.path.join(REPO_ROOT, "sonic-utilities-data", "debian", "install")

# wrapper name -> (target module, debian/install destination directory)
WRAPPERS = {
    "secure-boot-backend": ("secure_boot.secure_boot_backend", "/usr/sbin/"),
    "generic-uefi-backend": ("secure_boot.generic_uefi_backend", "/usr/lib/sonic/secure-boot/"),
}


class TestSecureBootPackaging(unittest.TestCase):
    def test_wrappers_and_modules(self):
        for name, (module, _dest) in WRAPPERS.items():
            path = os.path.join(DATA_SCRIPTS, name)
            self.assertTrue(os.access(path, os.X_OK), "wrapper not executable: {}".format(path))
            with open(path) as fp:
                content = fp.read()
            self.assertTrue(content.startswith("#!/usr/bin/env python3\n"))
            self.assertIn("from {} import main".format(module), content)
            self.assertIn("sys.exit(main())", content)
            self.assertTrue(callable(importlib.import_module(module).main))

    def test_install_maps_exact_paths(self):
        with open(INSTALL_FILE) as fp:
            entries = dict(line.split() for line in fp if len(line.split()) == 2)
        for name, (_module, dest) in WRAPPERS.items():
            self.assertEqual(entries.get("scripts/" + name), dest)


if __name__ == "__main__":
    unittest.main()
