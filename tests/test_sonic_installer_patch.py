import hashlib
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from sonic_installer.patch_manager import (
    PatchError,
    PatchManager,
    load_patch_plugin,
    md5sum,
    safe_extract,
    version_matches,
)


class PatchManagerHelperTest(unittest.TestCase):
    def test_version_matches_supported_operators(self):
        cases = [
            ("202605.1", "202605.1", True),
            ("202605.1", "=202605.1", True),
            ("202605.2", ">=202605.1", True),
            ("202605.1", ">202605.1", False),
            ("202605.1", "<=202605.1", True),
            ("202605.1", "<202605.2", True),
            ("202605.1", ">=202606", False),
        ]
        for current, expected, result in cases:
            with self.subTest(current=current, expected=expected):
                self.assertEqual(version_matches(current, expected), result)

    def test_md5sum_reads_file_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload"
            path.write_bytes(b"hotpatch payload")
            self.assertEqual(
                md5sum(path),
                hashlib.md5(b"hotpatch payload").hexdigest(),
            )

    def test_safe_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                entry = tarfile.TarInfo("../../escape")
                content = b"bad"
                entry.size = len(content)
                package.addfile(entry, io.BytesIO(content))

            with self.assertRaises(PatchError):
                safe_extract(archive, Path(directory) / "output")

    def test_safe_extract_rejects_special_files(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fifo.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                entry = tarfile.TarInfo("sub-Hotfix1/fifo")
                entry.type = tarfile.FIFOTYPE
                package.addfile(entry)

            with self.assertRaises(PatchError):
                safe_extract(archive, Path(directory) / "output")

    def test_safe_extract_extracts_regular_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            archive = directory / "good.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                entry = tarfile.TarInfo("sub-Hotfix1/payload")
                content = b"ok"
                entry.size = len(content)
                package.addfile(entry, io.BytesIO(content))

            output = directory / "output"
            safe_extract(archive, output)
            self.assertEqual(
                (output / "sub-Hotfix1" / "payload").read_bytes(), b"ok")

    def test_load_patch_plugin_requires_mandatory_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "install.py").write_text(
                "SUCCESS = 0\nFAIL = 1\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(PatchError, "get_patch_name"):
                load_patch_plugin(directory)

    def test_load_patch_plugin_requires_callable_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "install.py").write_text(
                "SUCCESS = 0\n"
                "FAIL = 1\n"
                "get_patch_name = 'not callable'\n"
                "def get_patch_desc(): return 'sample'\n"
                "def do_patch_install(): return SUCCESS, ''\n"
                "def do_patch_uninstall(): return SUCCESS, ''\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PatchError, "must be callable"):
                load_patch_plugin(directory)

    def test_load_patch_plugin_uses_patch_directory_as_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "patch_info.yml").write_text(
                "name: sample\n", encoding="utf-8")
            (directory / "install.py").write_text(
                "from pathlib import Path\n"
                "SUCCESS = 0\n"
                "FAIL = 1\n"
                "PATCH_INFO = Path('patch_info.yml').read_text().strip()\n"
                "def get_patch_name(): return 'sample'\n"
                "def get_patch_desc(): return PATCH_INFO\n"
                "def do_patch_install(): return SUCCESS, ''\n"
                "def do_patch_uninstall(): return SUCCESS, ''\n",
                encoding="utf-8",
            )
            old_cwd = os.getcwd()
            plugin = load_patch_plugin(directory)
            self.assertEqual(plugin.get_patch_desc(), "name: sample")
            self.assertEqual(os.getcwd(), old_cwd)


class PatchManagerInstallTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.version_file = self.root / "sonic_version.yml"
        self.version_file.write_text(
            "build_version: SONiC.test\n", encoding="utf-8")
        self.patch_root = self.root / "patches"
        self.hotpatch_root = self.root / "hotpatches"
        self.operation_log = self.root / "patch_operation.rec"
        self.lock_file = self.root / "patch.lock"
        self.manager = PatchManager(
            version_file=self.version_file,
            patch_root=self.patch_root,
            hotpatch_root=self.hotpatch_root,
            operation_log=self.operation_log,
            lock_file=self.lock_file,
            user="tester",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _create_subpatch(
            self,
            number,
            patch_type="hotpatch",
            install_status=0):
        name = "sub-Hotfix{}.tar.gz".format(number)
        source = self.root / "source-{}".format(number)
        patch_directory = source / "sub-Hotfix{}".format(number)
        patch_directory.mkdir(parents=True)
        marker = self.root / "marker-{}".format(number)
        plugin = """SUCCESS = 0
FAIL = 1
from pathlib import Path
MARKER = Path({marker!r})
def get_patch_name(): return {name!r}
def get_patch_desc(): return "test patch {number}"
def get_patch_type(): return {patch_type!r}
def do_patch_install():
    MARKER.write_text("installed")
    return {install_status}, "install output"
def do_patch_uninstall():
    if MARKER.exists(): MARKER.unlink()
    return SUCCESS, "uninstall output"
""".format(
            marker=str(marker),
            name=name,
            number=number,
            patch_type=patch_type,
            install_status=install_status,
        )
        (patch_directory / "install.py").write_text(plugin, encoding="utf-8")
        (patch_directory / "patch_info.yml").write_text(
            "Patch name: {}\nPatch type: {}\nPackages: []\n".format(
                name, patch_type),
            encoding="utf-8",
        )
        archive = self.root / name
        with tarfile.open(archive, "w:gz") as package:
            package.add(patch_directory, arcname=patch_directory.name)
        return archive, marker

    def _create_hotfix(self, archives, os_version="SONiC.test"):
        source = self.root / "hotfix-source"
        source.mkdir(exist_ok=True)
        patches = []
        for archive in archives:
            destination = source / archive.name
            destination.write_bytes(archive.read_bytes())
            patches.append(
                {"name": archive.name, "md5sum": md5sum(destination)})
        import yaml
        (source / "summary.yml").write_text(
            yaml.safe_dump({"os_version": os_version,
                           "patches": patches}, sort_keys=False),
            encoding="utf-8",
        )
        hotfix = self.root / "Hotfix1-SONiC.test.tar.gz"
        with tarfile.open(hotfix, "w:gz") as package:
            for path in source.iterdir():
                package.add(path, arcname=path.name)
        return hotfix

    def test_precheck_rejects_os_version_mismatch(self):
        archive, _ = self._create_subpatch(1)
        hotfix = self._create_hotfix([archive], os_version="SONiC.other")
        with self.assertRaisesRegex(PatchError, "targets SONiC.other"):
            self.manager.precheck(hotfix)

    def test_install_persists_state_plugin_and_hotpatch_archive(self):
        archive, marker = self._create_subpatch(1)
        hotfix = self._create_hotfix([archive])

        installed = self.manager.install(hotfix)

        self.assertEqual(installed, [archive.name])
        self.assertTrue(marker.exists())
        self.assertTrue(
            (self.patch_root / archive.name / "install.py").is_file())
        self.assertEqual(
            (self.hotpatch_root / archive.name).read_bytes(),
            archive.read_bytes())
        import yaml
        state = yaml.safe_load(self.version_file.read_text())
        self.assertEqual([item["name"]
                         for item in state["patches"]], [archive.name])
        metadata = yaml.safe_load(
            (self.patch_root / archive.name / "metadata.yml").read_text()
        )
        self.assertEqual(metadata["patch_type"], "hotpatch")
        self.assertEqual(metadata["installed_by_user"], "tester")

    def test_install_rolls_back_prior_subpatch_when_later_one_fails(self):
        first, first_marker = self._create_subpatch(1)
        second, second_marker = self._create_subpatch(2, install_status=1)
        hotfix = self._create_hotfix([first, second])

        with self.assertRaisesRegex(PatchError, "Failed to install"):
            self.manager.install(hotfix)

        self.assertFalse(first_marker.exists())
        self.assertFalse(second_marker.exists())
        import yaml
        state = yaml.safe_load(self.version_file.read_text())
        self.assertEqual(state.get("patches", []), [])
        self.assertFalse((self.patch_root / first.name).exists())
        self.assertFalse((self.hotpatch_root / first.name).exists())

    def test_install_rejects_unsafe_plugin_patch_name(self):
        archive, _ = self._create_subpatch(1)
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(self.root / "unsafe-subpatch")
        install_path = (
            self.root / "unsafe-subpatch" / "sub-Hotfix1" / "install.py")
        install_path.write_text(
            install_path.read_text().replace(
                "return 'sub-Hotfix1.tar.gz'", "return '..'"),
            encoding="utf-8",
        )
        unsafe_archive = self.root / "unsafe.tar.gz"
        with tarfile.open(unsafe_archive, "w:gz") as package:
            package.add(
                self.root / "unsafe-subpatch" / "sub-Hotfix1",
                arcname="sub-Hotfix1",
            )
        hotfix = self._create_hotfix([unsafe_archive])
        with self.assertRaisesRegex(PatchError, "Invalid patch name"):
            self.manager.install(hotfix)

    def test_precheck_rejects_checksum_mismatch(self):
        archive, _ = self._create_subpatch(1)
        hotfix = self._create_hotfix([archive])
        with tarfile.open(hotfix, "r:gz") as package:
            package.extractall(self.root / "tampered-hotfix")
        (self.root / "tampered-hotfix" / archive.name).write_bytes(b"tampered")
        tampered = self.root / "Hotfix-tampered.tar.gz"
        with tarfile.open(tampered, "w:gz") as package:
            for path in (self.root / "tampered-hotfix").iterdir():
                package.add(path, arcname=path.name)
        with self.assertRaisesRegex(PatchError, "checksum mismatch"):
            self.manager.precheck(tampered)

    def test_uninstall_removes_latest_patch_state_and_files(self):
        archive, marker = self._create_subpatch(1)
        self.manager.install(self._create_hotfix([archive]))

        self.manager.uninstall(archive.name, single=True)

        self.assertFalse(marker.exists())
        self.assertFalse((self.patch_root / archive.name).exists())
        self.assertFalse((self.hotpatch_root / archive.name).exists())
        import yaml
        state = yaml.safe_load(self.version_file.read_text())
        self.assertEqual(state.get("patches", []), [])

    def test_uninstall_rejects_non_latest_single_patch(self):
        first, _ = self._create_subpatch(1)
        second, _ = self._create_subpatch(2)
        self.manager.install(self._create_hotfix([first, second]))

        with self.assertRaisesRegex(PatchError, "not the latest"):
            self.manager.uninstall(first.name, single=True)

    def test_list_patches_includes_metadata(self):
        archive, _ = self._create_subpatch(1)
        self.manager.install(self._create_hotfix([archive]))

        patches = self.manager.list_patches()

        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["name"], archive.name)
        self.assertEqual(patches[0]["metadata"]["patch_type"], "hotpatch")

    def test_reapply_rejects_non_hotpatch(self):
        archive, _ = self._create_subpatch(1, patch_type="normal")
        self.manager.install(self._create_hotfix([archive]))
        with self.assertRaisesRegex(PatchError, "not a function hotpatch"):
            self.manager.reapply_hotpatch(archive)

    def test_state_update_preserves_version_file_mode(self):
        self.version_file.chmod(0o644)
        archive, _ = self._create_subpatch(1)
        self.manager.install(self._create_hotfix([archive]))
        self.assertEqual(self.version_file.stat().st_mode & 0o777, 0o644)

    def test_install_copies_summary_into_patch_storage(self):
        archive, _ = self._create_subpatch(1)
        self.manager.install(self._create_hotfix([archive]))
        self.assertTrue(
            (self.patch_root / archive.name / "summary.yml").is_file()
        )

    def test_default_uninstall_removes_patches_from_one_hotfix(self):
        first, first_marker = self._create_subpatch(1)
        second, second_marker = self._create_subpatch(2)
        hotfix = self._create_hotfix([first, second])
        self.manager.install(hotfix)

        removed = self.manager.uninstall(hotfix.name)

        self.assertEqual(removed, [second.name, first.name])
        self.assertFalse(first_marker.exists())
        self.assertFalse(second_marker.exists())

    def test_status_reports_active_function_hotpatch(self):
        archive, _ = self._create_subpatch(1)
        self.manager.install(self._create_hotfix([archive]))
        import yaml
        patch_info_path = self.patch_root / archive.name / "patch_info.yml"
        patch_info = yaml.safe_load(patch_info_path.read_text())
        patch_info["Packages"] = [{
            "Package": "sample.kpatch",
            "Type": "func_hotpatch",
            "ProcessName": "sampled",
            "PatchId": 7,
        }]
        patch_info_path.write_text(
            yaml.safe_dump(patch_info), encoding="utf-8")

        class Result:
            def __init__(self, returncode, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def runner(command, **kwargs):
            if command == ["pidof", "sampled"]:
                return Result(0, "123\n")
            if command == ["libcare-ctl", "info", "-p", "123"]:
                return Result(0, "Patch id: 0007\n")
            raise AssertionError(command)

        self.manager.runner = runner
        status = self.manager.status()

        self.assertEqual(status["live"][0]["process"], "sampled")
        self.assertEqual(status["live"][0]["patch_id"], "0007")
        self.assertTrue(status["live"][0]["active"])
        self.assertTrue(status["operation"])

    def test_reapply_hotpatch_does_not_duplicate_install_state(self):
        archive, marker = self._create_subpatch(1)
        hotfix = self._create_hotfix([archive])
        self.manager.install(hotfix)
        marker.unlink()

        self.manager.reapply_hotpatch(self.hotpatch_root / archive.name)

        self.assertTrue(marker.exists())
        import yaml
        state = yaml.safe_load(self.version_file.read_text())
        self.assertEqual([item["name"]
                         for item in state["patches"]], [archive.name])


if __name__ == "__main__":
    unittest.main()
