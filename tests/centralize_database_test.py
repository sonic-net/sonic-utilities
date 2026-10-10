from unittest import mock

import pytest

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


def test_centralize_to_target_db_copies_remote_socket_and_saves():
    key = mock.sentinel.key
    source = mock.Mock()
    copy_target = mock.Mock()
    save_target = mock.Mock()

    with mock.patch.object(
        centralize_database.multi_asic, 'is_multi_asic', return_value=True
    ), mock.patch.object(
        centralize_database.SonicDBConfig, 'initializeGlobalConfig'
    ) as initialize_global, mock.patch.object(
        centralize_database, 'SonicDBKey', return_value=key
    ), mock.patch.object(
        centralize_database.SonicDBConfig,
        'getDbSock',
        side_effect=lambda dbname, _: {
            'APPL_DB': '/var/run/redis/redis.sock',
            'STATE_DB': '/var/run/redis-state/redis.sock',
        }[dbname],
    ), mock.patch.object(
        centralize_database.SonicDBConfig,
        'getDbList',
        return_value=['APPL_DB', 'STATE_DB'],
    ), mock.patch.object(
        centralize_database.SonicDBConfig, 'getDbId', return_value=6
    ), mock.patch.object(
        centralize_database.redis,
        'Redis',
        side_effect=[source, copy_target, save_target],
    ) as redis_client, mock.patch.object(
        centralize_database, 'copy_database'
    ) as copy_database:
        centralize_database.centralize_to_target_db('APPL_DB', 'asic0')

    initialize_global.assert_called_once_with()
    assert redis_client.call_args_list == [
        mock.call(
            unix_socket_path='/var/run/redis-state/redis.sock', db=6
        ),
        mock.call(unix_socket_path='/var/run/redis/redis.sock', db=6),
        mock.call(unix_socket_path='/var/run/redis/redis.sock'),
    ]
    copy_database.assert_called_once_with(source, copy_target)
    save_target.save.assert_called_once_with()


def test_centralize_to_target_db_rejects_missing_target_socket():
    with mock.patch.object(
        centralize_database.multi_asic, 'is_multi_asic', return_value=False
    ), mock.patch.object(
        centralize_database.SonicDBConfig,
        'getDbSock',
        return_value='',
    ):
        with mock.patch.object(
            centralize_database.SonicDBConfig, 'getDbList'
        ) as get_db_list, mock.patch.object(
            centralize_database.redis, 'Redis'
        ) as redis_client:
            with mock.patch.object(
                centralize_database,
                'SonicDBKey',
                return_value=mock.sentinel.key,
            ):
                with pytest.raises(
                    RuntimeError,
                    match='No Unix socket configured for APPL_DB',
                ):
                    centralize_database.centralize_to_target_db(
                        'APPL_DB', ''
                    )

    get_db_list.assert_not_called()
    redis_client.assert_not_called()


def test_centralize_to_target_db_rejects_missing_source_socket():
    with mock.patch.object(
        centralize_database.multi_asic, 'is_multi_asic', return_value=False
    ), mock.patch.object(
        centralize_database, 'SonicDBKey', return_value=mock.sentinel.key
    ), mock.patch.object(
        centralize_database.SonicDBConfig,
        'getDbSock',
        side_effect=['/var/run/redis/redis.sock', None],
    ), mock.patch.object(
        centralize_database.SonicDBConfig,
        'getDbList',
        return_value=['STATE_DB'],
    ), mock.patch.object(
        centralize_database.redis, 'Redis'
    ) as redis_client:
        with pytest.raises(
            RuntimeError,
            match='No Unix socket configured for STATE_DB',
        ):
            centralize_database.centralize_to_target_db('APPL_DB', '')

    redis_client.assert_not_called()
