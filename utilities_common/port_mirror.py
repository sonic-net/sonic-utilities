"""Shared configuration checks for sampled port mirroring."""
from contextlib import contextmanager
import os
import re
import tempfile

from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector
from utilities_common.flock import acquire_flock, release_flock


SAMPLE_TABLE = 'PORT_MIRROR_SAMPLE'
SFLOW_TABLE = 'SFLOW'
SFLOW_GLOBAL = 'global'
if os.environ.get('UTILITIES_UNIT_TESTING', '0') in ('1', '2'):
    _temp_sampling_lockfile = tempfile.NamedTemporaryFile()
    SAMPLING_CONFIG_LOCK = _temp_sampling_lockfile.name
else:
    SAMPLING_CONFIG_LOCK = '/etc/sonic/sampling.lock'
EXCLUSION_ERROR = (
    'SFLOW global configuration and PORT_MIRROR_SAMPLE entries cannot coexist. '
    'Remove the conflicting configuration first; disabling it is not sufficient.'
)


def config_databases(host_db=None, connector_factory=None):
    """Return host and front-end ASIC databases for system-wide checks."""
    connector_factory = connector_factory or ConfigDBConnector
    if host_db is None:
        host_db = connector_factory()
        host_db.connect()
    databases = {'': host_db}
    for namespace in multi_asic.get_all_namespaces()['front_ns']:
        database = connector_factory(use_unix_socket_path=True, namespace=namespace)
        database.connect()
        databases[namespace] = database
    return databases


def reject_sflow_global_with_sample_bindings(ctx, host_db):
    """Reject a global sFlow write if any sampled binding is configured."""
    for database in config_databases(host_db).values():
        if database.get_keys(SAMPLE_TABLE):
            ctx.fail(EXCLUSION_ERROR)


def reject_sample_bindings_with_sflow_global(ctx, databases):
    """Reject a sampled binding write if global sFlow is configured."""
    for database in databases.values():
        if SFLOW_GLOBAL in database.get_keys(SFLOW_TABLE):
            ctx.fail(EXCLUSION_ERROR)


def validate_sampling_config(config):
    """Validate chassis-wide sampling-mode ownership in a final config."""
    if not isinstance(config, dict):
        raise ValueError('Sampling configuration must be a JSON object.')

    scoped_configs = [
        value for scope, value in config.items()
        if scope == 'localhost' or re.fullmatch(r'asic\d+', scope)
    ]
    configs = scoped_configs or [config]
    has_sflow = any(
        SFLOW_GLOBAL in scope_config.get(SFLOW_TABLE, {})
        for scope_config in configs
    )
    has_sample_bindings = any(
        bool(scope_config.get(SAMPLE_TABLE))
        for scope_config in configs
    )
    if has_sflow and has_sample_bindings:
        raise ValueError(EXCLUSION_ERROR)


@contextmanager
def sampling_config_lock(lock_file=SAMPLING_CONFIG_LOCK):
    """Serialize sampling validation and configuration writes."""
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
    if not acquire_flock(fd, timeout=0):
        os.close(fd)
        raise RuntimeError(f'Failed to acquire lock on {lock_file}')
    try:
        os.truncate(fd, 0)
        os.write(fd, f'sampling configuration, pid {os.getpid()}\n'.encode())
        yield
    finally:
        release_flock(fd)
        os.truncate(fd, 0)
        os.close(fd)


def validate_export_removal(ctx, databases, session_name):
    """Check every namespace before deleting any copy of an export session."""
    for database in databases.values():
        for entry in database.get_table(SAMPLE_TABLE).values():
            if entry.get('mirror_session') == session_name:
                ctx.fail(f"Mirror session {session_name} is referenced by a sampled binding. "
                         'Remove its sampled bindings first.')
        for entry in database.get_table('ACL_RULE').values():
            if any(entry.get(field) == session_name for field in
                   ('MIRROR_ACTION', 'MIRROR_INGRESS_ACTION', 'MIRROR_EGRESS_ACTION')):
                ctx.fail(f'Mirror session {session_name} is referenced by an ACL rule.')


def binding_key(key):
    """Normalize ConfigDB composite keys for display and overlap checks."""
    return key if isinstance(key, tuple) else tuple(key.split('|'))
