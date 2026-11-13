"""Shared wire and configuration metadata for DLDD utilities."""


DLDD_PRODUCER = "dldd"

DLDD_CONFIG_TABLE = "DLDD_CONFIG"
DLDD_CONFIG_KEY = "global"
DLDD_STATUS_KEY = "DLDD_STATUS|process_state"

UINT32_MAX = (1 << 32) - 1

# Description, CONFIG_DB field, and minimum accepted value. The daemon and
# YANG model remain independent validation boundaries; this descriptor keeps
# the config and show CLIs aligned with one another.
DLDD_CONFIG_FIELDS = (
    ("Individual max failure threshold", "individual_max_failure_threshold", 0),
    ("Broken rules max threshold", "broken_rules_max_threshold", 0),
    ("Redis monitor polling interval", "redis_monitor_polling_interval", 1),
    ("File monitor polling interval", "file_monitor_polling_interval", 1),
    ("Common monitor polling interval", "common_monitor_polling_interval", 1),
    ("Source unavailable grace period", "source_unavailable_grace_period", 0),
    ("Source recovery samples", "source_recovery_samples", 1),
    ("Inactive fault retention period", "inactive_fault_retention_period", 0),
    ("Fault evidence ack timeout", "fault_evidence_ack_timeout", 1),
    ("Active fault recheck interval", "active_fault_recheck_interval", 1),
    ("Rules inbox settle time", "rules_inbox_settle_time", 1),
)

DLDD_CONFIG_FIELD_MINIMUMS = {
    field: minimum
    for unused_description, field, minimum in DLDD_CONFIG_FIELDS
}


def is_dldd_fault(fault):
    """Return whether a shared FAULT_INFO row declares DLDD ownership."""
    producer = fault.get("producer")
    if producer is None:
        producer = fault.get(b"producer")
    if isinstance(producer, bytes):
        producer = producer.decode("utf-8", "replace")
    return producer == DLDD_PRODUCER
