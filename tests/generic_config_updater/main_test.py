import io
import json
import os
import subprocess
import sys
import unittest
from argparse import Namespace
from unittest import mock

# Make sure the repo root is on the path
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(os.path.dirname(_TEST_DIR))
sys.path.insert(0, _ROOT_DIR)

from generic_config_updater.generic_updater import ConfigFormat  # noqa: E402
from generic_config_updater.gu_common import GenericConfigUpdaterError  # noqa: E402
import generic_config_updater.main as gcu_main  # noqa: E402


# ---------------------------------------------------------------------------
# validate_patch_format
# ---------------------------------------------------------------------------

class TestValidatePatchFormat(unittest.TestCase):

    def test_valid_patch_returns_true(self):
        patch = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        self.assertTrue(gcu_main.validate_patch_format(patch))

    def test_valid_all_ops(self):
        for op in ("add", "remove", "replace", "move", "copy", "test"):
            patch = [{"op": op, "path": "/X"}]
            self.assertTrue(gcu_main.validate_patch_format(patch))

    def test_empty_list_is_valid(self):
        self.assertTrue(gcu_main.validate_patch_format([]))

    def test_not_a_list_returns_false(self):
        self.assertFalse(gcu_main.validate_patch_format({"op": "add", "path": "/X"}))

    def test_item_not_dict_returns_false(self):
        self.assertFalse(gcu_main.validate_patch_format(["not_a_dict"]))

    def test_missing_op_returns_false(self):
        self.assertFalse(gcu_main.validate_patch_format([{"path": "/X"}]))

    def test_missing_path_returns_false(self):
        self.assertFalse(gcu_main.validate_patch_format([{"op": "add"}]))

    def test_invalid_op_returns_false(self):
        self.assertFalse(
            gcu_main.validate_patch_format([{"op": "invalid_op", "path": "/X"}])
        )

    def test_none_input_returns_false(self):
        self.assertFalse(gcu_main.validate_patch_format(None))

    def test_multiple_valid_changes(self):
        patch = [
            {"op": "add", "path": "/A", "value": {}},
            {"op": "remove", "path": "/B"},
            {"op": "replace", "path": "/C", "value": 1},
        ]
        self.assertTrue(gcu_main.validate_patch_format(patch))

    def test_one_invalid_in_list_returns_false(self):
        patch = [
            {"op": "add", "path": "/A", "value": {}},
            {"op": "BAD", "path": "/B"},
        ]
        self.assertFalse(gcu_main.validate_patch_format(patch))


# ---------------------------------------------------------------------------
# get_all_running_config
# ---------------------------------------------------------------------------

class TestGetAllRunningConfig(unittest.TestCase):

    def _make_popen(self, stdout, returncode):
        proc = mock.Mock()
        proc.communicate.return_value = (stdout, None)
        proc.returncode = returncode
        return proc

    def test_success_returns_config_string(self):
        cfg = '{"PORT": {}}'
        with mock.patch('subprocess.Popen', return_value=self._make_popen(cfg, 0)):
            result = gcu_main.get_all_running_config()
        self.assertEqual(result, cfg)

    def test_nonzero_returncode_raises(self):
        with mock.patch('subprocess.Popen',
                        return_value=self._make_popen('', 1)):
            with self.assertRaises(GenericConfigUpdaterError):
                gcu_main.get_all_running_config()


# ---------------------------------------------------------------------------
# filter_duplicate_patch_operations
# ---------------------------------------------------------------------------

class TestFilterDuplicatePatchOperations(unittest.TestCase):

    def test_no_leaf_list_ops_returned_unchanged(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        config = {}
        result = gcu_main.filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        self.assertEqual(result, patch_ops)

    def test_removes_duplicate_leaf_list_add(self):
        config = {"ACL_TABLE": {"MY_ACL": {"ports": ["Eth0", "Eth1"]}}}
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/MY_ACL/ports/-", "value": "Eth0"},
            {"op": "add", "path": "/ACL_TABLE/MY_ACL/ports/-", "value": "Eth2"},
        ]
        result = gcu_main.filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        paths_values = [(op["path"], op["value"]) for op in result]
        self.assertNotIn(("/ACL_TABLE/MY_ACL/ports/-", "Eth0"), paths_values)
        self.assertIn(("/ACL_TABLE/MY_ACL/ports/-", "Eth2"), paths_values)

    def test_no_duplicates_nothing_removed(self):
        config = {"ACL_TABLE": {"MY_ACL": {"ports": []}}}
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/MY_ACL/ports/-", "value": "Eth0"},
            {"op": "add", "path": "/ACL_TABLE/MY_ACL/ports/-", "value": "Eth1"},
        ]
        result = gcu_main.filter_duplicate_patch_operations(patch_ops, json.dumps(config))
        self.assertEqual(len(result), 2)

    def test_accepts_dict_config(self):
        config = {"ACL_TABLE": {"MY_ACL": {"ports": ["Eth0"]}}}
        patch_ops = [
            {"op": "add", "path": "/ACL_TABLE/MY_ACL/ports/-", "value": "Eth0"},
        ]
        result = gcu_main.filter_duplicate_patch_operations(patch_ops, config)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# append_emptytables_if_required
# ---------------------------------------------------------------------------

class TestAppendEmptyTablesIfRequired(unittest.TestCase):

    def test_no_missing_tables_returned_unchanged(self):
        config = {"TABLE1": {}}
        patch_ops = [{"op": "add", "path": "/TABLE1/key", "value": "v"}]
        result = gcu_main.append_emptytables_if_required(patch_ops, json.dumps(config))
        self.assertEqual(result, patch_ops)

    def test_missing_table_prepended(self):
        config = {}
        patch_ops = [{"op": "add", "path": "/TABLE1/key", "value": "v"}]
        result = gcu_main.append_emptytables_if_required(patch_ops, json.dumps(config))
        self.assertEqual(result[0], {"op": "add", "path": "/TABLE1", "value": {}})
        self.assertEqual(result[1], patch_ops[0])

    def test_multiple_missing_tables(self):
        config = {}
        patch_ops = [
            {"op": "add", "path": "/TABLE1/field", "value": "v1"},
            {"op": "add", "path": "/TABLE2/field", "value": "v2"},
        ]
        result = gcu_main.append_emptytables_if_required(patch_ops, json.dumps(config))
        created_paths = [op["path"] for op in result if op.get("value") == {}]
        self.assertIn("/TABLE1", created_paths)
        self.assertIn("/TABLE2", created_paths)

    def test_accepts_dict_config(self):
        config = {}
        patch_ops = [{"op": "add", "path": "/TABLE1/key", "value": "v"}]
        result = gcu_main.append_emptytables_if_required(patch_ops, config)
        self.assertEqual(result[0]["path"], "/TABLE1")

    def test_op_without_path_skipped(self):
        config = {}
        patch_ops = [{"op": "add", "value": "v"}]
        result = gcu_main.append_emptytables_if_required(patch_ops, config)
        # Should not crash, just return the ops with no empty table inserted
        self.assertEqual(len(result), 1)

    def test_empty_path_parts_skipped(self):
        config = {}
        patch_ops = [{"op": "add", "path": "/", "value": "v"}]
        # Should not raise
        result = gcu_main.append_emptytables_if_required(patch_ops, config)
        self.assertIsInstance(result, list)

    def test_asic_scoped_table_path(self):
        """Paths starting with asic0/TABLE should resolve two-level pointer."""
        config = {"asic0": {}}
        patch_ops = [{"op": "add", "path": "/asic0/NEW_TABLE/key", "value": "v"}]
        result = gcu_main.append_emptytables_if_required(patch_ops, json.dumps(config))
        created_paths = [op["path"] for op in result if op.get("value") == {}]
        self.assertIn("/asic0/NEW_TABLE", created_paths)


# ---------------------------------------------------------------------------
# validate_patch
# ---------------------------------------------------------------------------

class TestValidatePatch(unittest.TestCase):

    def _simple_ops(self):
        return [{"op": "add", "path": "/TABLE/key", "value": "v"}]

    def test_returns_true_when_yang_not_available(self):
        """When sonic_yang_cfg_generator is not importable, validation is skipped."""
        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': None}):
            result = gcu_main.validate_patch([], json.dumps({}))
        self.assertTrue(result)

    def test_returns_true_on_valid_config(self):
        mock_generator = mock.Mock()
        mock_generator.validate_config_db_json.return_value = True
        mock_module = mock.Mock()
        mock_module.SonicYangCfgDbGenerator.return_value = mock_generator

        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': mock_module}):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                result = gcu_main.validate_patch([], json.dumps({}))
        self.assertTrue(result)

    def test_returns_false_when_validation_fails(self):
        mock_generator = mock.Mock()
        mock_generator.validate_config_db_json.return_value = False
        mock_module = mock.Mock()
        mock_module.SonicYangCfgDbGenerator.return_value = mock_generator

        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': mock_module}):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                result = gcu_main.validate_patch([], json.dumps({}))
        self.assertFalse(result)

    def test_raises_on_unexpected_exception(self):
        mock_module = mock.Mock()
        mock_module.SonicYangCfgDbGenerator.side_effect = RuntimeError("boom")

        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': mock_module}):
            with self.assertRaises(GenericConfigUpdaterError):
                gcu_main.validate_patch([], json.dumps({}))

    def test_multiasic_validates_all_asics(self):
        mock_generator = mock.Mock()
        mock_generator.validate_config_db_json.return_value = True
        mock_module = mock.Mock()
        mock_module.SonicYangCfgDbGenerator.return_value = mock_generator

        config = {"localhost": {}, "asic0": {}, "asic1": {}}

        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': mock_module}):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=True):
                with mock.patch('sonic_py_common.multi_asic.get_namespace_list',
                                return_value=['asic0', 'asic1']):
                    result = gcu_main.validate_patch([], json.dumps(config))
        self.assertTrue(result)
        # Called once per host + once per asic
        self.assertEqual(mock_generator.validate_config_db_json.call_count, 3)

    def test_multiasic_returns_false_when_asic_fails(self):
        call_count = [0]

        def side_effect(_cfg):
            call_count[0] += 1
            # Fail on the second call (first asic)
            return call_count[0] != 2

        mock_generator = mock.Mock()
        mock_generator.validate_config_db_json.side_effect = side_effect
        mock_module = mock.Mock()
        mock_module.SonicYangCfgDbGenerator.return_value = mock_generator

        config = {"localhost": {}, "asic0": {}}

        with mock.patch.dict('sys.modules', {'sonic_yang_cfg_generator': mock_module}):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=True):
                with mock.patch('sonic_py_common.multi_asic.get_namespace_list',
                                return_value=['asic0']):
                    result = gcu_main.validate_patch([], json.dumps(config))
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# apply_patch_for_scope
# ---------------------------------------------------------------------------

class TestApplyPatchForScope(unittest.TestCase):

    def test_success_records_success(self):
        mock_updater = mock.Mock()
        results = {}
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            gcu_main.apply_patch_for_scope(
                ("", [{"op": "add", "path": "/T/k", "value": "v"}]),
                results, ConfigFormat.CONFIGDB, False, False, False, ()
            )
        self.assertTrue(results[gcu_main.HOST_NAMESPACE]["success"])

    def test_exception_records_failure(self):
        mock_updater = mock.Mock()
        mock_updater.apply_patch.side_effect = Exception("scope error")
        results = {}
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            gcu_main.apply_patch_for_scope(
                ("", [{"op": "add", "path": "/T/k", "value": "v"}]),
                results, ConfigFormat.CONFIGDB, False, False, False, ()
            )
        key = list(results.keys())[0]
        self.assertFalse(results[key]["success"])
        self.assertIn("scope error", results[key]["message"])

    def test_host_namespace_scope_mapping(self):
        mock_updater = mock.Mock()
        results = {}
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            gcu_main.apply_patch_for_scope(
                (gcu_main.HOST_NAMESPACE, []),
                results, ConfigFormat.CONFIGDB, False, False, False, ()
            )
        # HOST_NAMESPACE scope should map correctly
        self.assertIn(gcu_main.HOST_NAMESPACE, results)


# ---------------------------------------------------------------------------
# apply_patch_from_file
# ---------------------------------------------------------------------------

class TestApplyPatchFromFile(unittest.TestCase):

    def _make_patch_file(self, patch_ops):
        return mock.mock_open(read_data=json.dumps(patch_ops))

    def test_invalid_format_raises(self):
        bad_patch = {"op": "add"}  # not a list
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(bad_patch))):
            with self.assertRaises(GenericConfigUpdaterError):
                gcu_main.apply_patch_from_file(
                    '/fake/patch.json', 'CONFIGDB',
                    False, False, False, False, ()
                )

    def test_success_no_preprocess(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        mock_updater = mock.Mock()
        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('generic_config_updater.main.extract_scope',
                                return_value=('', '/TABLE/key')):
                    gcu_main.apply_patch_from_file(
                        '/fake/patch.json', 'CONFIGDB',
                        False, False, False, False, (), preprocess=False
                    )
        mock_updater.apply_patch.assert_called_once()

    def test_preprocess_path_runs_helpers(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        running_cfg = json.dumps({"TABLE": {}})
        mock_updater = mock.Mock()

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                with mock.patch('generic_config_updater.main.get_all_running_config',
                                return_value=running_cfg):
                    with mock.patch('generic_config_updater.main.append_emptytables_if_required',
                                    return_value=patch_ops) as mock_append:
                        with mock.patch('generic_config_updater.main.filter_duplicate_patch_operations',
                                        return_value=patch_ops) as mock_filter:
                            with mock.patch('generic_config_updater.main.validate_patch',
                                            return_value=True) as mock_validate:
                                with mock.patch('generic_config_updater.main.GenericUpdater',
                                                return_value=mock_updater):
                                    gcu_main.apply_patch_from_file(
                                        '/fake/patch.json', 'CONFIGDB',
                                        False, False, False, False, (), preprocess=True
                                    )
            mock_append.assert_called_once()
            mock_filter.assert_called_once()
            mock_validate.assert_called_once()

    def test_preprocess_validation_failure_raises(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        running_cfg = json.dumps({})

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.get_all_running_config',
                            return_value=running_cfg):
                with mock.patch('generic_config_updater.main.append_emptytables_if_required',
                                return_value=patch_ops):
                    with mock.patch('generic_config_updater.main.filter_duplicate_patch_operations',
                                    return_value=patch_ops):
                        with mock.patch('generic_config_updater.main.validate_patch',
                                        return_value=False):
                            with self.assertRaises(GenericConfigUpdaterError):
                                gcu_main.apply_patch_from_file(
                                    '/fake/patch.json', 'CONFIGDB',
                                    False, False, False, False, (), preprocess=True
                                )

    def test_parallel_dispatches_with_threadpool(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        mock_updater = mock.Mock()

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('generic_config_updater.main.extract_scope',
                                return_value=('', '/TABLE/key')):
                    gcu_main.apply_patch_from_file(
                        '/fake/patch.json', 'CONFIGDB',
                        False, False, True, False, (), preprocess=False
                    )
        mock_updater.apply_patch.assert_called_once()

    def test_scope_failure_raises(self):
        patch_ops = [{"op": "add", "path": "/TABLE/key", "value": "v"}]
        mock_updater = mock.Mock()
        mock_updater.apply_patch.side_effect = Exception("boom")

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('generic_config_updater.main.extract_scope',
                                return_value=('', '/TABLE/key')):
                    with self.assertRaises(GenericConfigUpdaterError) as ctx:
                        gcu_main.apply_patch_from_file(
                            '/fake/patch.json', 'CONFIGDB',
                            False, False, False, False, (), preprocess=False
                        )
        self.assertIn("Failed to apply patch", str(ctx.exception))

    def test_empty_patch_still_validates(self):
        """Empty patch ops triggers per-asic validation loop."""
        patch_ops = []
        mock_updater = mock.Mock()

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                    gcu_main.apply_patch_from_file(
                        '/fake/patch.json', 'CONFIGDB',
                        False, False, False, False, (), preprocess=False
                    )
        mock_updater.apply_patch.assert_called_once()

    def test_empty_patch_multiasic(self):
        """Empty patch in multiasic triggers all asic namespaces."""
        patch_ops = []
        mock_updater = mock.Mock()

        with mock.patch('builtins.open', self._make_patch_file(patch_ops)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=True):
                    with mock.patch('sonic_py_common.multi_asic.get_namespace_list',
                                    return_value=['asic0', 'asic1']):
                        gcu_main.apply_patch_from_file(
                            '/fake/patch.json', 'CONFIGDB',
                            False, False, False, False, (), preprocess=False
                        )
        self.assertEqual(mock_updater.apply_patch.call_count, 3)  # default + asic0 + asic1


# ---------------------------------------------------------------------------
# print_error / print_success
# ---------------------------------------------------------------------------

class TestPrintHelpers(unittest.TestCase):

    def test_print_error_writes_to_stderr(self):
        captured = io.StringIO()
        with mock.patch('sys.stderr', captured):
            gcu_main.print_error("something went wrong")
        self.assertIn("something went wrong", captured.getvalue())

    def test_print_success_writes_to_stdout(self):
        captured = io.StringIO()
        with mock.patch('sys.stdout', captured):
            gcu_main.print_success("all good")
        self.assertIn("all good", captured.getvalue())


# ---------------------------------------------------------------------------
# multiasic_save_to_singlefile
# ---------------------------------------------------------------------------

class TestMultiasicSaveToSinglefile(unittest.TestCase):

    def test_saves_host_and_asic_configs(self):
        host_config = {"PORT": {}}
        asic_config = {"VLAN": {}}

        def fake_run(cmd, **kwargs):
            result = mock.Mock()
            if "-n" in cmd:
                result.stdout = json.dumps(asic_config)
            else:
                result.stdout = json.dumps(host_config)
            return result

        mock_open_obj = mock.mock_open()
        with mock.patch('subprocess.run', side_effect=fake_run):
            with mock.patch('sonic_py_common.multi_asic.get_namespace_list',
                            return_value=['asic0']):
                with mock.patch('builtins.open', mock_open_obj):
                    gcu_main.multiasic_save_to_singlefile('/tmp/all_config.json')

        written = ''.join(
            call.args[0]
            for call in mock_open_obj().write.call_args_list
        )
        saved = json.loads(written)
        self.assertIn('localhost', saved)
        self.assertIn('asic0', saved)


# ---------------------------------------------------------------------------
# Sub-command functions
# ---------------------------------------------------------------------------

class TestCreateCheckpoint(unittest.TestCase):

    def _make_args(self, name='cp1', verbose=False):
        return Namespace(checkpoint_name=name, verbose=verbose)

    def test_success(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                gcu_main.create_checkpoint(self._make_args())
        mock_updater.checkpoint.assert_called_once_with('cp1', False)
        mock_ps.assert_called_once()

    def test_success_verbose(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                with mock.patch('generic_config_updater.main.print_success'):
                    gcu_main.create_checkpoint(self._make_args(verbose=True))
        self.assertIn('cp1', captured.getvalue())

    def test_failure_calls_sys_exit(self):
        mock_updater = mock.Mock()
        mock_updater.checkpoint.side_effect = Exception("fail")
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with self.assertRaises(SystemExit):
                gcu_main.create_checkpoint(self._make_args())


class TestDeleteCheckpoint(unittest.TestCase):

    def _make_args(self, name='cp1', verbose=False):
        return Namespace(checkpoint_name=name, verbose=verbose)

    def test_success(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                gcu_main.delete_checkpoint(self._make_args())
        mock_updater.delete_checkpoint.assert_called_once_with('cp1', False)
        mock_ps.assert_called_once()

    def test_success_verbose(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                with mock.patch('generic_config_updater.main.print_success'):
                    gcu_main.delete_checkpoint(self._make_args(verbose=True))
        self.assertIn('cp1', captured.getvalue())

    def test_failure_calls_sys_exit(self):
        mock_updater = mock.Mock()
        mock_updater.delete_checkpoint.side_effect = Exception("fail")
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with self.assertRaises(SystemExit):
                gcu_main.delete_checkpoint(self._make_args())


class TestListCheckpoints(unittest.TestCase):

    def _make_args(self, time=False, verbose=False):
        return Namespace(time=time, verbose=verbose)

    def test_no_checkpoints(self):
        mock_updater = mock.Mock()
        mock_updater.list_checkpoints.return_value = []
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                gcu_main.list_checkpoints(self._make_args())
        self.assertIn('No checkpoints', captured.getvalue())

    def test_list_without_time(self):
        mock_updater = mock.Mock()
        mock_updater.list_checkpoints.return_value = ['cp1', 'cp2']
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                gcu_main.list_checkpoints(self._make_args())
        output = captured.getvalue()
        self.assertIn('cp1', output)
        self.assertIn('cp2', output)

    def test_list_with_time(self):
        mock_updater = mock.Mock()
        mock_updater.list_checkpoints.return_value = [
            {'name': 'cp1', 'time': '2025-01-01T00:00:00Z'},
        ]
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                gcu_main.list_checkpoints(self._make_args(time=True))
        output = captured.getvalue()
        self.assertIn('cp1', output)
        self.assertIn('2025-01-01', output)

    def test_failure_calls_sys_exit(self):
        mock_updater = mock.Mock()
        mock_updater.list_checkpoints.side_effect = Exception("fail")
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with self.assertRaises(SystemExit):
                gcu_main.list_checkpoints(self._make_args())


class TestApplyPatchSubcommand(unittest.TestCase):

    def _make_args(self, patch_file='/fake/p.json', fmt='CONFIGDB',
                   verbose=False, dry_run=False, parallel=False,
                   ignore_non_yang_tables=False, ignore_path=None,
                   path_trace=None):
        return Namespace(
            patch_file=patch_file,
            format=fmt,
            verbose=verbose,
            dry_run=dry_run,
            parallel=parallel,
            ignore_non_yang_tables=ignore_non_yang_tables,
            ignore_path=ignore_path or [],
            path_trace=path_trace,
        )

    def test_success(self):
        with mock.patch('generic_config_updater.main.apply_patch_from_file') as mock_apf:
            with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                gcu_main.apply_patch(self._make_args())
        mock_apf.assert_called_once()
        mock_ps.assert_called_once()

    def test_verbose_prints_details(self):
        with mock.patch('generic_config_updater.main.apply_patch_from_file'):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                with mock.patch('generic_config_updater.main.print_success'):
                    gcu_main.apply_patch(self._make_args(verbose=True, dry_run=True))
        output = captured.getvalue()
        self.assertIn('/fake/p.json', output)
        self.assertIn('DRY RUN', output)

    def test_failure_calls_sys_exit(self):
        with mock.patch('generic_config_updater.main.apply_patch_from_file',
                        side_effect=Exception("oops")):
            with self.assertRaises(SystemExit):
                gcu_main.apply_patch(self._make_args())


class TestReplaceConfigSubcommand(unittest.TestCase):

    def _make_args(self, config_file='/fake/cfg.json', fmt='CONFIGDB',
                   verbose=False, ignore_non_yang_tables=False,
                   ignore_path=None):
        return Namespace(
            config_file=config_file,
            format=fmt,
            verbose=verbose,
            ignore_non_yang_tables=ignore_non_yang_tables,
            ignore_path=ignore_path or [],
        )

    def test_success(self):
        mock_updater = mock.Mock()
        cfg = json.dumps({"PORT": {}})
        with mock.patch('builtins.open', mock.mock_open(read_data=cfg)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                    gcu_main.replace_config(self._make_args())
        mock_updater.replace.assert_called_once()
        mock_ps.assert_called_once()

    def test_verbose_prints_details(self):
        mock_updater = mock.Mock()
        cfg = json.dumps({})
        with mock.patch('builtins.open', mock.mock_open(read_data=cfg)):
            with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
                captured = io.StringIO()
                with mock.patch('sys.stdout', captured):
                    with mock.patch('generic_config_updater.main.print_success'):
                        gcu_main.replace_config(self._make_args(verbose=True))
        self.assertIn('/fake/cfg.json', captured.getvalue())

    def test_failure_calls_sys_exit(self):
        with mock.patch('builtins.open', side_effect=Exception("no file")):
            with self.assertRaises(SystemExit):
                gcu_main.replace_config(self._make_args())


class TestSaveConfigSubcommand(unittest.TestCase):

    def _make_args(self, filename=None, verbose=False):
        return Namespace(filename=filename, verbose=verbose)

    def test_save_defaults_to_config_db_file(self):
        fake_cfg = json.dumps({"PORT": {}})

        def fake_run(cmd, **kwargs):
            r = mock.Mock()
            r.stdout = fake_cfg
            return r

        mock_open_obj = mock.mock_open()
        with mock.patch('subprocess.run', side_effect=fake_run):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                with mock.patch('builtins.open', mock_open_obj):
                    with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                        gcu_main.save_config(self._make_args())
        mock_ps.assert_called_once()

    def test_save_with_explicit_filename_verbose(self):
        fake_cfg = json.dumps({})

        def fake_run(cmd, **kwargs):
            r = mock.Mock()
            r.stdout = fake_cfg
            return r

        mock_open_obj = mock.mock_open()
        with mock.patch('subprocess.run', side_effect=fake_run):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                with mock.patch('builtins.open', mock_open_obj):
                    captured = io.StringIO()
                    with mock.patch('sys.stdout', captured):
                        with mock.patch('generic_config_updater.main.print_success'):
                            gcu_main.save_config(self._make_args(filename='/tmp/out.json', verbose=True))
        self.assertIn('/tmp/out.json', captured.getvalue())

    def test_save_multiasic(self):
        with mock.patch('generic_config_updater.main.multiasic_save_to_singlefile') as mock_save:
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=True):
                with mock.patch('generic_config_updater.main.print_success'):
                    gcu_main.save_config(self._make_args(filename='/tmp/out.json'))
        mock_save.assert_called_once_with('/tmp/out.json')

    def test_subprocess_error_exits(self):
        with mock.patch('subprocess.run',
                        side_effect=subprocess.CalledProcessError(1, 'cmd')):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                with self.assertRaises(SystemExit):
                    gcu_main.save_config(self._make_args())

    def test_generic_exception_exits(self):
        with mock.patch('subprocess.run', side_effect=RuntimeError("oops")):
            with mock.patch('sonic_py_common.multi_asic.is_multi_asic', return_value=False):
                with self.assertRaises(SystemExit):
                    gcu_main.save_config(self._make_args())


class TestRollbackConfigSubcommand(unittest.TestCase):

    def _make_args(self, name='cp1', verbose=False,
                   ignore_non_yang_tables=False, ignore_path=None):
        return Namespace(
            checkpoint_name=name,
            verbose=verbose,
            ignore_non_yang_tables=ignore_non_yang_tables,
            ignore_path=ignore_path or [],
        )

    def test_success(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with mock.patch('generic_config_updater.main.print_success') as mock_ps:
                gcu_main.rollback_config(self._make_args())
        mock_updater.rollback.assert_called_once()
        mock_ps.assert_called_once()

    def test_verbose_prints_details(self):
        mock_updater = mock.Mock()
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            captured = io.StringIO()
            with mock.patch('sys.stdout', captured):
                with mock.patch('generic_config_updater.main.print_success'):
                    gcu_main.rollback_config(self._make_args(verbose=True))
        self.assertIn('cp1', captured.getvalue())

    def test_failure_calls_sys_exit(self):
        mock_updater = mock.Mock()
        mock_updater.rollback.side_effect = Exception("fail")
        with mock.patch('generic_config_updater.main.GenericUpdater', return_value=mock_updater):
            with self.assertRaises(SystemExit):
                gcu_main.rollback_config(self._make_args())


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------

class TestBuildParser(unittest.TestCase):

    def setUp(self):
        self.parser = gcu_main.build_parser()

    def test_parser_returns_argparse_parser(self):
        import argparse
        self.assertIsNotNone(self.parser)
        self.assertIsInstance(self.parser, argparse.ArgumentParser)

    def test_create_checkpoint_command(self):
        args = self.parser.parse_args(['create-checkpoint', 'mycp'])
        self.assertEqual(args.command, 'create-checkpoint')
        self.assertEqual(args.checkpoint_name, 'mycp')
        self.assertFalse(args.verbose)

    def test_create_checkpoint_verbose(self):
        args = self.parser.parse_args(['create-checkpoint', 'mycp', '--verbose'])
        self.assertTrue(args.verbose)

    def test_delete_checkpoint_command(self):
        args = self.parser.parse_args(['delete-checkpoint', 'mycp'])
        self.assertEqual(args.command, 'delete-checkpoint')
        self.assertEqual(args.checkpoint_name, 'mycp')

    def test_list_checkpoints_command(self):
        args = self.parser.parse_args(['list-checkpoints'])
        self.assertEqual(args.command, 'list-checkpoints')
        self.assertFalse(args.time)

    def test_list_checkpoints_with_time(self):
        args = self.parser.parse_args(['list-checkpoints', '--time'])
        self.assertTrue(args.time)

    def test_apply_patch_command_defaults(self):
        args = self.parser.parse_args(['apply-patch', 'my.json'])
        self.assertEqual(args.command, 'apply-patch')
        self.assertEqual(args.patch_file, 'my.json')
        self.assertEqual(args.format, 'CONFIGDB')
        self.assertFalse(args.dry_run)
        self.assertFalse(args.parallel)
        self.assertFalse(args.ignore_non_yang_tables)
        self.assertEqual(args.ignore_path, [])

    def test_apply_patch_all_flags(self):
        args = self.parser.parse_args([
            'apply-patch', 'my.json',
            '--format', 'SONICYANG',
            '--dry-run',
            '--parallel',
            '--ignore-non-yang-tables',
            '--ignore-path', '/T1',
            '--ignore-path', '/T2',
            '--verbose',
        ])
        self.assertEqual(args.format, 'SONICYANG')
        self.assertTrue(args.dry_run)
        self.assertTrue(args.parallel)
        self.assertTrue(args.ignore_non_yang_tables)
        self.assertEqual(args.ignore_path, ['/T1', '/T2'])
        self.assertTrue(args.verbose)

    def test_replace_command_defaults(self):
        args = self.parser.parse_args(['replace', 'cfg.json'])
        self.assertEqual(args.command, 'replace')
        self.assertEqual(args.config_file, 'cfg.json')
        self.assertEqual(args.format, 'CONFIGDB')

    def test_save_command_default_filename(self):
        args = self.parser.parse_args(['save'])
        self.assertEqual(args.command, 'save')
        self.assertIsNone(args.filename)

    def test_save_command_explicit_filename(self):
        args = self.parser.parse_args(['save', '/tmp/out.json'])
        self.assertEqual(args.filename, '/tmp/out.json')

    def test_rollback_command(self):
        args = self.parser.parse_args(['rollback', 'cp1'])
        self.assertEqual(args.command, 'rollback')
        self.assertEqual(args.checkpoint_name, 'cp1')


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def _run_main(self, argv):
        with mock.patch('sys.argv', ['gcu-standalone'] + argv):
            try:
                gcu_main.main()
            except SystemExit:
                pass

    def test_no_command_prints_help(self):
        captured = io.StringIO()
        with mock.patch('sys.argv', ['gcu-standalone']):
            with mock.patch('sys.stdout', captured):
                gcu_main.main()
        # argparse prints usage/help on no subcommand
        # main() calls parser.print_help() and returns

    def test_create_checkpoint_dispatched(self):
        with mock.patch('generic_config_updater.main.create_checkpoint') as mock_fn:
            with mock.patch('sys.argv', ['gcu', 'create-checkpoint', 'mycp']):
                gcu_main.main()
        mock_fn.assert_called_once()

    def test_delete_checkpoint_dispatched(self):
        with mock.patch('generic_config_updater.main.delete_checkpoint') as mock_fn:
            with mock.patch('sys.argv', ['gcu', 'delete-checkpoint', 'mycp']):
                gcu_main.main()
        mock_fn.assert_called_once()

    def test_list_checkpoints_dispatched(self):
        with mock.patch('generic_config_updater.main.list_checkpoints') as mock_fn:
            with mock.patch('sys.argv', ['gcu', 'list-checkpoints']):
                gcu_main.main()
        mock_fn.assert_called_once()

    def test_save_dispatched(self):
        with mock.patch('generic_config_updater.main.save_config') as mock_fn:
            with mock.patch('sys.argv', ['gcu', 'save']):
                gcu_main.main()
        mock_fn.assert_called_once()

    def test_rollback_dispatched(self):
        with mock.patch('generic_config_updater.main.rollback_config') as mock_fn:
            with mock.patch('sys.argv', ['gcu', 'rollback', 'cp1']):
                gcu_main.main()
        mock_fn.assert_called_once()

    def test_apply_patch_missing_file_exits(self):
        with mock.patch('sys.argv', ['gcu', 'apply-patch', '/nonexistent/file.json']):
            with self.assertRaises(SystemExit):
                gcu_main.main()

    def test_replace_missing_file_exits(self):
        with mock.patch('sys.argv', ['gcu', 'replace', '/nonexistent/cfg.json']):
            with self.assertRaises(SystemExit):
                gcu_main.main()

    def test_apply_patch_existing_file_dispatched(self, ):
        with mock.patch('generic_config_updater.main.apply_patch') as mock_fn:
            with mock.patch('os.path.exists', return_value=True):
                with mock.patch('sys.argv', ['gcu', 'apply-patch', '/fake/patch.json']):
                    gcu_main.main()
        mock_fn.assert_called_once()

    def test_replace_existing_file_dispatched(self):
        with mock.patch('generic_config_updater.main.replace_config') as mock_fn:
            with mock.patch('os.path.exists', return_value=True):
                with mock.patch('sys.argv', ['gcu', 'replace', '/fake/cfg.json']):
                    gcu_main.main()
        mock_fn.assert_called_once()


if __name__ == '__main__':
    unittest.main()
