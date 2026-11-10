"""FRR-backed operational IS-IS commands with explicit scope validation."""
import json
import click
from sonic_py_common import multi_asic
from sonic_isis import identifier
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from utilities_common import bgp_util


def run_vtysh_command(vtysh_cmd, namespace=multi_asic.DEFAULT_NAMESPACE):
    return bgp_util.run_bgp_command(vtysh_cmd, namespace, bgp_util.get_vtysh_shell_cmd())


def _name(ctx, param, value):
    if value is not None:
        try:
            identifier(value)
        except ValueError as error:
            raise click.BadParameter(str(error))
    return value


@click.group(name='isis', cls=clicommon.AliasedGroup)
def isis():
    """Show native IS-IS routing state."""


def _filter_instance(data, command, instance):
    def select(areas):
        if not isinstance(areas, list):
            raise ValueError('Native output does not contain scoped areas')
        result = []
        for area in areas:
            if not isinstance(area, dict):
                raise ValueError('Invalid native area object')
            name = area.get('area')
            if command == 'database' and isinstance(name, dict):
                name = name.get('name')
            if not isinstance(name, str):
                raise ValueError('Native area identity is missing')
            if name == instance:
                result.append(area)
        return result

    if not isinstance(data, dict):
        raise ValueError('Native output is not an object')
    if command == 'summary':
        if not isinstance(data.get('vrfs'), list):
            raise ValueError('Native summary does not contain scoped VRFs')
        for vrf in data['vrfs']:
            if not isinstance(vrf, dict):
                raise ValueError('Invalid native VRF object')
            vrf['areas'] = select(vrf.get('areas'))
            vrf['number-areas'] = len(vrf['areas'])
        return data
    data['areas'] = select(data.get('areas'))
    return data


def _register(command, supports_json=True, supports_instance=False):
    params = [click.Option(['--namespace', '-n'], default=multi_asic.DEFAULT_NAMESPACE,
                           callback=multi_asic_util.multi_asic_namespace_validation_callback)]
    if command != 'vrf':
        params.append(click.Option(['--vrf'], default='default', callback=_name))
    if supports_json:
        params.append(click.Option(['--json', '-j', 'json_format'], is_flag=True))
    if supports_instance:
        params.append(click.Option(['--instance'], callback=_name))
    if command == 'database':
        params.append(click.Argument(['detail'], required=False, type=click.Choice(['detail'])))
    if command in ('route', 'topology'):
        params.append(click.Option(['--level'], type=click.Choice(['level-1', 'level-2'])))

    @click.pass_context
    def callback(ctx, namespace, vrf='default', json_format=False, instance=None, detail=None, level=None):
        native_command = 'summary' if command == 'vrf' else command
        selected = 'all' if command == 'vrf' else vrf
        if instance and (not json_format or selected == 'all'):
            ctx.fail('--instance requires --json and one VRF')
        # These native JSON writers replace the area array for each VRF.
        # Summary is the exception: it exposes a proper vrfs array.
        if json_format and selected == 'all' and native_command != 'summary':
            ctx.fail('Use a single --vrf for JSON; native all-VRF output loses area scope')
        prefix = 'show isis' + ((' vrf ' + selected) if selected != 'default' else '')
        if json_format and command in ('route', 'topology'):
            try:
                summary = json.loads(run_vtysh_command(prefix + ' summary json', namespace))
                vrfs = summary['vrfs']
                if any(len(item['areas']) > 1 for item in vrfs):
                    ctx.fail('Native route/topology JSON loses multiple areas; use text output')
            except (ValueError, KeyError, TypeError) as error:
                ctx.fail('Cannot establish native JSON scope: {}'.format(error))
        cmd = prefix + ' ' + native_command
        if detail:
            cmd += ' detail'
        if level:
            cmd += ' ' + level
        if json_format:
            cmd += ' json'
        output = run_vtysh_command(cmd, namespace)
        if json_format:
            try:
                data = json.loads(output)
                if instance:
                    data = _filter_instance(data, native_command, instance)
                output = json.dumps(data, indent=2)
            except (ValueError, KeyError, TypeError) as error:
                ctx.fail('Cannot read scoped native JSON: {}'.format(error))
        click.echo(output.rstrip('\n'))
    isis.add_command(click.Command(command, params=params, callback=callback))


for _command in ('summary', 'neighbor', 'database', 'interface'):
    _register(_command, supports_instance=True)
for _command in ('route', 'topology', 'vrf'):
    _register(_command)
_register('hostname', supports_json=False)
