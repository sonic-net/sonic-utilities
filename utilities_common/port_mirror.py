"""Shared configuration checks for sampled port mirroring."""
from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector


SAMPLE_TABLE = 'PORT_MIRROR_SAMPLE'
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
