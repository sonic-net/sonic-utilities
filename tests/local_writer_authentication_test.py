import io
import os
import sys
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from utilities_common.general import load_module_from_source


WRITERS = [
    pytest.param('pfc', ['config', 'asymmetric', 'on', 'Ethernet0'], 'pfc', id='pfc-asymmetric'),
    pytest.param('pfc', ['config', 'priority', 'on', 'Ethernet0', '3'], 'pfc', id='pfc-priority'),
    pytest.param('ecn', ['-p', 'PROFILE', '-gmin', '100'], 'ecnconfig', id='ecn-threshold'),
    pytest.param('ecn', ['-q', '3', 'on'], 'ecnconfig', id='ecn-queue-on'),
    pytest.param('ecn', ['-q', '3', 'off'], 'ecnconfig', id='ecn-queue-off'),
    pytest.param('mmu', ['-p', 'PROFILE', '-a', '0'], 'mmuconfig', id='mmu-alpha-zero'),
    pytest.param('mmu', ['-p', 'PROFILE', '-s', '0'], 'mmuconfig', id='mmu-static-zero'),
    pytest.param('mmu', ['-p', 'PROFILE', '-t', 'off'], 'mmuconfig', id='mmu-trim-off'),
    *[pytest.param('drop', ['-c', command], 'dropconfig', id='drop-' + command)
      for command in ['install', 'uninstall', 'add', 'remove',
                      'enable_drop_monitor', 'disable_drop_monitor']],
]
READERS = [
    pytest.param('pfc', ['show', 'asymmetric'], 'pfc', id='pfc-asymmetric'),
    pytest.param('pfc', ['show', 'priority'], 'pfc', id='pfc-priority'),
    pytest.param('ecn', ['-l'], 'ecnconfig', id='ecn-list'),
    pytest.param('ecn', ['-q', '3'], 'ecnconfig', id='ecn-queue'),
    pytest.param('mmu', ['-l'], 'mmuconfig', id='mmu-list'),
    pytest.param('mmu', ['-l'], 'buffershow', id='buffershow-list'),
    *[pytest.param('drop', ['-c', command], 'dropconfig', id='drop-' + command)
      for command in ['show_config', 'show_capabilities', 'show_drop_monitor_persistent_drops']],
]
HELPS = [
    pytest.param('pfc', ['config', 'asymmetric', '--help'], 'pfc', id='pfc-asymmetric'),
    pytest.param('pfc', ['config', 'priority', '--help'], 'pfc', id='pfc-priority'),
    pytest.param('ecn', ['--help'], 'ecnconfig', id='ecn'),
    pytest.param('mmu', ['--help'], 'mmuconfig', id='mmu'),
    pytest.param('mmu', ['--help'], 'buffershow', id='buffershow'),
    pytest.param('drop', ['--help'], 'dropconfig', id='drop'),
]
NON_WRITES = [
    pytest.param('ecn', ['-p', 'PROFILE'], 'ecnconfig', 1, id='ecn-no-set-option'),
    pytest.param('ecn', ['-l', '-gmin', '100'], 'ecnconfig', 1, id='ecn-invalid-list-set'),
    pytest.param('mmu', ['-p', 'PROFILE'], 'mmuconfig', 0, id='mmu-no-set-option'),
    pytest.param('mmu', ['-p', 'PROFILE', '-a', '0'], 'buffershow', 1, id='buffershow-no-writes'),
    pytest.param('drop', ['-c', 'unknown'], 'dropconfig', 0, id='drop-unknown'),
]


@pytest.fixture(scope='module')
def local_modules():
    import pfc.main as pfc
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    return {'pfc': pfc,
            'ecn': load_module_from_source('local_auth_ecnconfig', str(scripts / 'ecnconfig')),
            'mmu': load_module_from_source('local_auth_mmuconfig', str(scripts / 'mmuconfig')),
            'drop': load_module_from_source('local_auth_dropconfig', str(scripts / 'dropconfig'))}


def invoke_local(module, component, arguments, program, uid=0):
    token = object()
    classes = {'pfc': ['Pfc'], 'ecn': ['EcnConfig', 'EcnQ'],
               'mmu': ['MmuConfig'], 'drop': ['DropConfigWrapper']}[component]
    output = io.StringIO()
    with ExitStack() as stack:
        factory = stack.enter_context(patch.object(module, 'Db', return_value=token))
        stack.enter_context(patch.object(module.os, 'geteuid', return_value=uid))
        stack.enter_context(patch.object(sys, 'argv', [program] + arguments))
        if hasattr(module, 'load_db_config'):
            stack.enter_context(patch.object(module, 'load_db_config'))
        handlers = {name: stack.enter_context(patch.object(module, name)) for name in classes}
        if component == 'ecn':
            handlers['EcnConfig'].return_value.get_profile_data.return_value = {}
            handlers['EcnConfig'].return_value.validate_profile_data.return_value = True
            handlers['EcnConfig'].return_value.updated_profile_tables = {}
            directory = stack.enter_context(TemporaryDirectory(prefix='ecn-authentication-test-'))
            stack.enter_context(patch.dict(os.environ, {
                'ECNCONFIG_FILE': str(Path(directory) / 'profiles.json')}))
        if component == 'drop':
            with redirect_stdout(output), redirect_stderr(output):
                try:
                    module.main()
                    exit_code = 0
                except SystemExit as error:
                    exit_code = error.code
            result = SimpleNamespace(exit_code=exit_code, output=output.getvalue())
        else:
            result = CliRunner().invoke(module.cli if component == 'pfc' else module.main, arguments)
    return result, factory, handlers, token


class TestLocalWriterAuthentication:
    @pytest.mark.parametrize('component,arguments,program', WRITERS)
    def test_writer_requests_authentication(self, local_modules, component, arguments, program):
        result, factory, handlers, token = invoke_local(local_modules[component], component, arguments, program)
        assert result.exit_code == 0, result.output
        factory.assert_called_once_with(authenticate=True)
        used = [handler for handler in handlers.values() if handler.called]
        assert len(used) == 1
        assert used[0].call_args.kwargs['db'] is token

    @pytest.mark.parametrize('component,arguments,program', READERS)
    def test_reader_keeps_default_connection(self, local_modules, component, arguments, program):
        result, factory, handlers, _ = invoke_local(local_modules[component], component, arguments, program, uid=65534)
        assert result.exit_code == 0, result.output
        factory.assert_not_called()
        assert all(handler.call_args.kwargs.get('db') is None for handler in handlers.values() if handler.called)

    @pytest.mark.parametrize('component,arguments,program', HELPS)
    def test_help_opens_no_database(self, local_modules, component, arguments, program):
        result, factory, handlers, _ = invoke_local(local_modules[component], component, arguments, program)
        assert result.exit_code == 0, result.output
        factory.assert_not_called()
        assert all(not handler.called for handler in handlers.values())

    @pytest.mark.parametrize('component,arguments,program,expected_exit', NON_WRITES)
    def test_invalid_and_nonwriting_requests_do_not_authenticate(self, local_modules, component, arguments, program,
                                                                 expected_exit):
        result, factory, _, _ = invoke_local(local_modules[component], component, arguments, program)
        assert result.exit_code == expected_exit, result.output
        factory.assert_not_called()

    @pytest.mark.parametrize('component,class_name,arguments', [
        pytest.param('pfc', 'Pfc', [], id='pfc'),
        pytest.param('ecn', 'EcnConfig', [None, False], id='ecn-profile'),
        pytest.param('ecn', 'EcnQ', ['3', None, False], id='ecn-queue'),
        pytest.param('mmu', 'MmuConfig', [False, True, None], id='mmu'),
        pytest.param('drop', 'DropConfigWrapper', [], id='drop'),
    ])
    @pytest.mark.parametrize('supplied', [False, True], ids=['default', 'explicit'])
    def test_constructor_preserves_namespace_and_supplied_DB(self, local_modules, component, class_name, arguments,
                                                             supplied):
        module = local_modules[component]
        db = object() if supplied else None
        with patch.object(module.multi_asic_util, 'MultiAsic') as wrapper, \
                patch.object(module.multi_asic, 'get_namespace_list', return_value=['asic0']), \
                patch.object(module, 'Db') as factory:
            getattr(module, class_name)(*arguments, 'asic0', db=db)
        assert wrapper.call_args.kwargs['namespace_option'] == 'asic0'
        assert wrapper.call_args.kwargs['db'] is db
        factory.assert_not_called()
