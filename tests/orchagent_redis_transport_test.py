"""Check explicit local sockets and namespace initialization in task queries."""

from unittest import mock

import pytest

from clear import orchagent as clear_orchagent
from show import orchagent as show_orchagent


def native_mock(namespace, initialized):
    state = {'initialized': initialized}
    native = mock.MagicMock()
    native.Select.OBJECT = 0
    native.Select.TIMEOUT = 1
    native.Select.return_value.select.return_value = (native.Select.OBJECT, None)
    native.NotificationConsumer.return_value.pop.return_value = ('ok', '', [])
    native.FieldValuePairs.side_effect = lambda value: value
    native.SonicDBConfig.isGlobalInit.side_effect = lambda: state['initialized']
    native.SonicDBConfig.initializeGlobalConfig.side_effect = lambda: state.update(initialized=True)
    native.SonicDBConfig.getDbPort.side_effect = RuntimeError('transport must be explicit')

    def connect(*arguments):
        assert not namespace or state['initialized'], 'namespace used before initialization'
        return mock.Mock()

    native.DBConnector.side_effect = connect
    return native


@pytest.mark.parametrize('namespace', ['', 'asic0', 'asic3'])
@pytest.mark.parametrize('initialized', [False, True])
def test_clear_initializes_namespace_before_connection(namespace, initialized):
    native = native_mock(namespace, initialized)
    with mock.patch.object(clear_orchagent, 'swsscommon', native):
        clear_orchagent._send_clear(namespace)
        clear_orchagent._send_clear(namespace)

    assert native.DBConnector.call_args_list == [
        mock.call('APPL_DB', clear_orchagent.REDIS_TIMEOUT_MSECS, False, namespace, True)
    ] * 2
    assert native.SonicDBConfig.initializeGlobalConfig.call_count == int(bool(namespace) and not initialized)
    native.SonicDBConfig.getDbPort.assert_not_called()
    assert native.NotificationProducer.return_value.send.call_args_list == [mock.call('clear', '', [])] * 2


@pytest.mark.parametrize('namespace', ['', 'asic0', 'asic3'])
def test_show_uses_the_selected_local_namespace(namespace):
    native = native_mock(namespace, True)
    with mock.patch.object(show_orchagent, 'swsscommon', native):
        assert show_orchagent._query_orchagent('show', namespace) == ('ok', '', [])

    native.DBConnector.assert_called_once_with(
        'APPL_DB', show_orchagent.REDIS_TIMEOUT_MSECS, False, namespace, True)
    native.SonicDBConfig.getDbPort.assert_not_called()
    native.NotificationProducer.return_value.send.assert_called_once_with('show', '', [])


@pytest.mark.parametrize('module', [show_orchagent, clear_orchagent], ids=['show', 'clear'])
def test_socket_failure_propagates_without_tcp_fallback(module):
    native = native_mock('asic0', True)
    native.DBConnector.side_effect = RuntimeError('local socket unavailable')
    with mock.patch.object(module, 'swsscommon', native):
        with pytest.raises(RuntimeError, match='local socket unavailable'):
            if module is show_orchagent:
                module._query_orchagent('show', 'asic0')
            else:
                module._send_clear('asic0')

    native.DBConnector.assert_called_once_with('APPL_DB', module.REDIS_TIMEOUT_MSECS, False, 'asic0', True)
    native.SonicDBConfig.getDbPort.assert_not_called()
