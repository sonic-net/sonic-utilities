"""CPO exclusion for sfputil; the chassis owns port technology selection."""
import click


def is_cpo_port(physical_port, chassis):
    """Return whether the chassis exposes a CPO object for this port."""
    try:
        return chassis.get_cpo(physical_port) is not None
    except (NotImplementedError, AttributeError, IndexError):
        return False


def filter_cpo_ports(logical_ports, physical_port_lookup, chassis):
    """Exclude CPO ports from an existing list without querying module hardware."""
    return [
        port for port in logical_ports
        if not any(is_cpo_port(index, chassis) for index in physical_port_lookup(port))
    ]


def reject_cpo_ports(port_name, physical_ports, chassis):
    """Reject an explicit CPO selection before calling SFP APIs."""
    if any(is_cpo_port(index, chassis) for index in physical_ports):
        raise click.ClickException(
            "Port '{}' is a CPO port; please use cpoutil instead".format(port_name)
        )
