from unittest import mock

from .utils import load_source


centralize_database = load_source(
    'centralize_database', 'scripts/centralize_database'
)


def test_copy_database_preserves_absolute_expiry_and_persistent_keys():
    source = mock.Mock()
    source.scan.return_value = (0, [b'expiring', b'persistent', b'gone'])
    source_pipeline = source.pipeline.return_value
    source_pipeline.execute.return_value = [
        b'expiring-value', 5000, [b'100', b'250000'],
        b'persistent-value', -1, [b'100', b'260000'],
        None, -2, [b'100', b'270000'],
    ]

    target = mock.Mock()
    target_pipeline = target.pipeline.return_value

    centralize_database.copy_database(source, target)

    assert source_pipeline.mock_calls == [
        mock.call.dump(b'expiring'),
        mock.call.pttl(b'expiring'),
        mock.call.execute_command('TIME'),
        mock.call.dump(b'persistent'),
        mock.call.pttl(b'persistent'),
        mock.call.execute_command('TIME'),
        mock.call.dump(b'gone'),
        mock.call.pttl(b'gone'),
        mock.call.execute_command('TIME'),
        mock.call.execute(),
    ]
    assert target_pipeline.mock_calls == [
        mock.call.execute_command(
            'RESTORE', b'expiring', 105250, b'expiring-value',
            'REPLACE', 'ABSTTL'
        ),
        mock.call.execute_command(
            'RESTORE', b'persistent', 0, b'persistent-value', 'REPLACE'
        ),
        mock.call.execute(),
    ]


def test_copy_database_scans_until_cursor_is_zero():
    source = mock.Mock()
    source.scan.side_effect = [(7, []), (0, [])]
    target = mock.Mock()

    centralize_database.copy_database(source, target)

    assert source.scan.mock_calls == [
        mock.call(cursor=0, count=centralize_database.SCAN_BATCH_SIZE),
        mock.call(cursor=7, count=centralize_database.SCAN_BATCH_SIZE),
    ]
    source.pipeline.assert_not_called()
    target.pipeline.assert_not_called()
