"""Reserved topology and port-selection helpers for CPO display commands.

No platform initialization or topology parsing is performed by this draft.
"""


def load_cpo_mapping(port_config):
    """Return an existing CpoMapping built from get_cpo_data() and port_config.

    Reuse cpoutil.mapping instead of introducing another parser. This helper
    must not call cpoutil.main or construct platform/hardware objects.
    """
    raise NotImplementedError("CPO topology loading is not implemented yet")


def is_cpo_port(pport, chassis):
    """Reserve the shared chassis.get_cpo(pport) classification predicate.

    Reuse the existing sfputil.port predicate when integrating callers; do
    not duplicate its behavior or change existing SFP filtering in this draft.
    """
    raise NotImplementedError("Shared CPO classification is not implemented yet")


def split_cpo_ports(ports, physical_lookup, chassis):
    """Return CPO and SFP logical-port groups using the caller's one chassis.

    physical_lookup resolves logical ports to physical indices. Classification
    must not read transceiver measurements or reinitialize the chassis per port.
    """
    raise NotImplementedError("CPO/SFP port grouping is not implemented yet")
