"""CONFIG_DB policy for software bridge-port protection."""

import re

import click
import sonic_yang
from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector

import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util


TABLE = "BRIDGE_PORT_PROTECTION"
YANG_DIR = "/usr/local/yang-models"
DEFAULTS = {
    "protection_mode": "SOFTWARE",
    "admin_mode": "AUTO",
    "revertive": "false",
    "wait_to_restore_time_ms": "0",
}
KEYS = click.Choice([*DEFAULTS, "delete"])


def interface_name(value):
    match = re.fullmatch(r"portchannel([0-9]{1,4})", value, re.IGNORECASE)
    return "PortChannel" + match.group(1) if match else None


def normalize_value(ctx, key, value):
    if value is None:
        ctx.fail("A value is required for {}.".format(key))
    if key == "protection_mode":
        if value.upper() != "SOFTWARE":
            ctx.fail("Only SOFTWARE protection mode is supported.")
        return "SOFTWARE"
    if key == "admin_mode":
        if value.upper() not in ("AUTO", "PRIMARY", "PROTECTION"):
            ctx.fail("admin_mode must be auto, primary, or protection.")
        return value.upper()
    if key == "revertive":
        if value.lower() not in ("true", "false"):
            ctx.fail("revertive must be true or false.")
        return value.lower()
    if not re.fullmatch(r"[0-9]+", value) or len(value) > 10 or int(value) > 0xFFFFFFFF:
        ctx.fail("wait_to_restore_time_ms must be an integer in 0..4294967295.")
    return str(int(value))


def apply_policy(ctx, config_db, interface, key, value):
    name = interface_name(interface)
    if name is None:
        ctx.fail("Protection requires a PortChannel name (PortChannel0..PortChannel9999).")
    try:
        if key == "delete":
            if value is not None:
                ctx.fail("delete does not take a value.")
            config_db.set_entry(TABLE, name, None)
            return

        portchannel = config_db.get_entry("PORTCHANNEL", name)
        if not portchannel:
            ctx.fail("{} does not exist in PORTCHANNEL.".format(name))
        normalized = normalize_value(ctx, key, value)
        entry = dict(DEFAULTS)
        entry.update(config_db.get_entry(TABLE, name))
        entry[key] = normalized

        # Validate this policy and its leafref target even when global YANG
        # validation is disabled. No hardware policy is inferred or written.
        validator = sonic_yang.SonicYang(YANG_DIR, print_log_enabled=False)
        validator.loadYangModel()
        validator.loadData(configdbJson={
            "PORTCHANNEL": {name: portchannel}, TABLE: {name: entry}
        })
        if TABLE in validator.tablesWithOutYang:
            ctx.fail("Install the bridge-port protection YANG model before configuring protection.")
        validator.validate_data_tree()
        config_db.set_entry(TABLE, name, entry)
    except (sonic_yang.SonicYangException, ValueError, RuntimeError, OSError) as error:
        ctx.fail("Failed to configure bridge-port protection: {}".format(error))


@click.command(name="protection")
@click.argument("interface", metavar="<PortChannel>")
@click.argument("key", type=KEYS)
@click.argument("value", required=False)
@click.pass_context
def protection(ctx, interface, key, value):
    """Set software protection policy, or delete its configuration."""
    apply_policy(ctx, ctx.obj["db"], interface, key, value)


def interface_group(name):
    @click.group(name=name)
    @click.option("-n", "--namespace", default=None,
                  type=multi_asic_util.LazyChoice(multi_asic_util.multi_asic_ns_choices),
                  help="ASIC namespace (required on multi-ASIC systems).")
    @click.pass_context
    def group(ctx, namespace):
        """Configure protection on this PortChannel."""
        if multi_asic.is_multi_asic() and namespace is None:
            ctx.fail("Specify --namespace on a multi-ASIC system.")
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace or "")
        config_db.connect()
        ctx.obj = {"db": config_db}

    @group.command(name="protection")
    @click.argument("key", type=KEYS)
    @click.argument("value", required=False)
    @click.pass_context
    def configure(ctx, key, value):
        """Set software policy: protection_mode, admin_mode, revertive, or WTR."""
        apply_policy(ctx, ctx.obj["db"], name, key, value)

    return group


class BridgePortProtectionGroup(clicommon.AbbreviationGroup):
    """Preserve normal commands and resolve config portchannelN protection."""

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        if interface_name(cmd_name) is not None:
            return interface_group(cmd_name)
        return None
