import pytest
from unittest import mock

from config import dpb

PLATFORM_FILE = '/usr/share/sonic/platform/platform.json'

# Two flat parents of four lanes each, plus one HPN parent.
PLATFORM_INTERFACES = {
    'Ethernet0': {
        'index': '1,1,1,1',
        'lanes': '0,1,2,3',
        'breakout_modes': {'1x100G': ['Ethernet0'],
                           '2x50G': ['Ethernet0', 'Ethernet2'],
                           '4x25G': ['Ethernet0', 'Ethernet1',
                                     'Ethernet2', 'Ethernet3']},
    },
    'Ethernet4': {
        'index': '2,2,2,2',
        'lanes': '4,5,6,7',
        'breakout_modes': {'1x100G': ['Ethernet4'],
                           '4x25G': ['Ethernet4', 'Ethernet5',
                                     'Ethernet6', 'Ethernet7']},
    },
    'Ethernet1_31': {
        'index': '31,31',
        'lanes': '120,121',
        'breakout_modes': {'1x400G': ['Ethernet1_31'],
                           '2x100G': ['Ethernet1_31_1', 'Ethernet1_31_2']},
    },
}

# Generated child layout per (parent, mode).
CHILD_PORTS = {
    ('Ethernet0', '1x100G'): {'Ethernet0': {'lanes': '0,1,2,3', 'speed': '100000'}},
    ('Ethernet0', '2x50G'): {'Ethernet0': {'lanes': '0,1', 'speed': '50000'},
                             'Ethernet2': {'lanes': '2,3', 'speed': '50000'}},
    ('Ethernet0', '4x25G'): {'Ethernet0': {'lanes': '0', 'speed': '25000'},
                             'Ethernet1': {'lanes': '1', 'speed': '25000'},
                             'Ethernet2': {'lanes': '2', 'speed': '25000'},
                             'Ethernet3': {'lanes': '3', 'speed': '25000'}},
    ('Ethernet4', '1x100G'): {'Ethernet4': {'lanes': '4,5,6,7', 'speed': '100000'}},
    ('Ethernet4', '4x25G'): {'Ethernet4': {'lanes': '4', 'speed': '25000'},
                             'Ethernet5': {'lanes': '5', 'speed': '25000'},
                             'Ethernet6': {'lanes': '6', 'speed': '25000'},
                             'Ethernet7': {'lanes': '7', 'speed': '25000'}},
    ('Ethernet1_31', '1x400G'): {'Ethernet1_31': {'lanes': '120,121',
                                                  'speed': '400000'}},
    ('Ethernet1_31', '2x100G'): {'Ethernet1_31_1': {'lanes': '120',
                                                    'speed': '100000'},
                                 'Ethernet1_31_2': {'lanes': '121',
                                                    'speed': '100000'}},
}


def fake_get_child_ports(interface, mode, platformFile):
    try:
        return dict(CHILD_PORTS[(interface, mode)])
    except KeyError:
        raise ValueError('unsupported mode {} for {}'.format(mode, interface))


@pytest.fixture(autouse=True)
def patch_child_ports():
    with mock.patch.object(dpb, 'get_child_ports', fake_get_child_ports):
        yield


def brkout_cfg(**modes):
    return {name: {'brkout_mode': mode} for name, mode in modes.items()}


def port_table(*specs):
    """specs are (name, lanes) pairs describing the live PORT table."""
    return {name: {'lanes': lanes, 'alias': name} for name, lanes in specs}


def preflight(name, targetMode, brkoutCfg=None, portTable=None,
              platformInterfaces=None, oidPorts=None):
    return dpb.preflightParent(
        name,
        platformInterfaces if platformInterfaces is not None
        else PLATFORM_INTERFACES,
        PLATFORM_FILE,
        brkoutCfg if brkoutCfg is not None
        else brkout_cfg(Ethernet0='1x100G'),
        portTable if portTable is not None
        else port_table(('Ethernet0', '0,1,2,3')),
        targetMode,
        oidPorts=oidPorts)


class TestReadyParent:
    def test_valid_parent_becomes_ready(self):
        result = preflight('Ethernet0', '4x25G')
        assert result.status == dpb.READY
        assert result.curMode == '1x100G'
        assert result.targetMode == '4x25G'
        assert sorted(result.curChildren) == ['Ethernet0']
        assert sorted(result.targetChildren) == [
            'Ethernet0', 'Ethernet1', 'Ethernet2', 'Ethernet3']

    def test_unrelated_live_ports_do_not_block(self):
        result = preflight(
            'Ethernet0', '4x25G',
            portTable=port_table(('Ethernet0', '0,1,2,3'),
                                 ('Ethernet4', '4,5,6,7')))
        assert result.status == dpb.READY


class TestAlreadyConfigured:
    def test_same_mode_is_skipped_after_validating_current_layout(self):
        result = preflight('Ethernet0', '1x100G')
        assert result.status == dpb.SKIPPED_ALREADY_CONFIGURED
        assert result.curChildren  # current layout was validated
        assert result.targetChildren == {}  # no target planning happened

    def test_same_mode_with_broken_current_layout_still_fails(self):
        """A skip must not paper over a current layout that does not match."""
        result = preflight('Ethernet0', '1x100G',
                           portTable=port_table(('Ethernet0', '0,1')))
        assert result.status == dpb.FAILED_PRECHECK


class TestBreakoutCfgState:
    def test_missing_marker_row_fails_only_this_parent(self):
        result = preflight('Ethernet0', '4x25G', brkoutCfg={})
        assert result.status == dpb.FAILED_PRECHECK
        assert 'BREAKOUT_CFG' in result.reason

    def test_empty_marker_mode_fails(self):
        result = preflight('Ethernet0', '4x25G',
                           brkoutCfg={'Ethernet0': {'brkout_mode': '  '}})
        assert result.status == dpb.FAILED_PRECHECK

    def test_marker_mode_not_advertised_fails(self):
        result = preflight('Ethernet0', '4x25G',
                           brkoutCfg=brkout_cfg(Ethernet0='8x10G'))
        assert result.status == dpb.FAILED_PRECHECK
        assert 'not advertised' in result.reason


class TestTargetMode:
    def test_unsupported_target_keeps_the_existing_message(self):
        result = preflight('Ethernet0', '8x10G')
        assert result.status == dpb.FAILED_PRECHECK
        assert result.reason == (
            'Target mode 8x10G is not available for the port Ethernet0')

    def test_target_mode_is_case_sensitive(self):
        result = preflight('Ethernet0', '4X25G')
        assert result.status == dpb.FAILED_PRECHECK


class TestCurrentLayoutValidation:
    def test_missing_current_child_fails(self):
        result = preflight('Ethernet0', '1x100G',
                           brkoutCfg=brkout_cfg(Ethernet0='4x25G'),
                           portTable=port_table(('Ethernet0', '0'),
                                                ('Ethernet1', '1')))
        assert result.status == dpb.FAILED_PRECHECK
        assert 'missing from the PORT table' in result.reason

    def test_lane_mismatch_on_a_live_child_fails(self):
        result = preflight('Ethernet0', '4x25G',
                           portTable=port_table(('Ethernet0', '0,1')))
        assert result.status == dpb.FAILED_PRECHECK
        assert 'lanes' in result.reason

    def test_foreign_port_owning_parent_lanes_fails(self):
        result = preflight(
            'Ethernet0', '4x25G',
            portTable=port_table(('Ethernet0', '0,1,2,3'),
                                 ('Ethernet900', '2')))
        assert result.status == dpb.FAILED_PRECHECK
        assert 'Ethernet900' in result.reason


class TestTargetLayoutValidation:
    def test_target_child_colliding_with_a_foreign_port_fails(self):
        result = preflight(
            'Ethernet0', '4x25G',
            portTable=port_table(('Ethernet0', '0,1,2,3'),
                                 ('Ethernet2', '64')))
        assert result.status == dpb.FAILED_PRECHECK
        assert 'Ethernet2' in result.reason


class TestHpnParents:
    def test_hpn_parent_breaks_out_from_1x400g_to_2x100g(self):
        result = preflight(
            'Ethernet1_31', '2x100G',
            brkoutCfg=brkout_cfg(Ethernet1_31='1x400G'),
            portTable=port_table(('Ethernet1_31', '120,121')))
        assert result.status == dpb.READY
        assert sorted(result.targetChildren) == [
            'Ethernet1_31_1', 'Ethernet1_31_2']

    def test_hpn_parent_validates_when_only_children_are_live(self):
        """After the first breakout the canonical parent name is not a live
        PORT key, which must not block a subsequent transition."""
        result = preflight(
            'Ethernet1_31', '1x400G',
            brkoutCfg=brkout_cfg(Ethernet1_31='2x100G'),
            portTable=port_table(('Ethernet1_31_1', '120'),
                                 ('Ethernet1_31_2', '121')))
        assert result.status == dpb.READY
        assert sorted(result.curChildren) == [
            'Ethernet1_31_1', 'Ethernet1_31_2']


class TestPlatformEntryValidation:
    @pytest.mark.parametrize('entry, fragment', [
        ({'lanes': '', 'index': '1', 'breakout_modes': {'1x100G': []}},
         'lanes'),
        ({'lanes': '0,1', 'index': '', 'breakout_modes': {'1x100G': []}},
         'index'),
        ({'lanes': '0,1', 'index': '1', 'breakout_modes': {}},
         'breakout_modes'),
        ('not-a-mapping', 'platform.json entry'),
    ])
    def test_malformed_platform_entry_fails(self, entry, fragment):
        result = preflight('Ethernet0', '4x25G',
                           platformInterfaces={'Ethernet0': entry})
        assert result.status == dpb.FAILED_PRECHECK
        assert fragment in result.reason


class TestPreflightSet:
    def test_bad_parent_rejects_only_itself(self):
        results = dpb.preflightParents(
            parents=['Ethernet0', 'Ethernet4'],
            notParents=['Ethernet999'],
            platformInterfaces=PLATFORM_INTERFACES,
            platformFile=PLATFORM_FILE,
            # Ethernet4 has no marker row, so only it fails.
            brkoutCfg=brkout_cfg(Ethernet0='1x100G'),
            portTable=port_table(('Ethernet0', '0,1,2,3'),
                                 ('Ethernet4', '4,5,6,7')),
            targetMode='4x25G')

        byName = {result.name: result.status for result in results}
        assert byName == {
            'Ethernet999': dpb.SKIPPED_NOT_PARENT,
            'Ethernet0': dpb.READY,
            'Ethernet4': dpb.FAILED_PRECHECK,
        }
        assert [result.name for result in dpb.readyParents(results)] == [
            'Ethernet0']

    def test_skipped_and_failed_parents_contribute_no_children(self):
        results = dpb.preflightParents(
            parents=['Ethernet0', 'Ethernet4'],
            notParents=['Ethernet999'],
            platformInterfaces=PLATFORM_INTERFACES,
            platformFile=PLATFORM_FILE,
            brkoutCfg=brkout_cfg(Ethernet0='1x100G', Ethernet4='4x25G'),
            portTable=port_table(('Ethernet0', '0,1,2,3'),
                                 ('Ethernet4', '4'), ('Ethernet5', '5'),
                                 ('Ethernet6', '6'), ('Ethernet7', '7')),
            targetMode='4x25G')

        ready = dpb.readyParents(results)
        assert [result.name for result in ready] == ['Ethernet0']

        # Ethernet4 is already configured, so none of its children may reach
        # the apply inputs.
        applyChildren = set()
        for result in ready:
            applyChildren |= set(result.curChildren)
            applyChildren |= set(result.targetChildren)
        assert not applyChildren & {'Ethernet5', 'Ethernet6', 'Ethernet7'}


class TestAsicOidCompleteness:
    """A missing OID is attributable, so it must fail only its own parent.

    The engine refuses the whole aggregate when any OID is absent, which is
    the guarantee that nothing unverifiable is ever written. Deciding it here
    as well is what lets -s drop that one parent and break out the rest.
    """

    def test_complete_oids_stay_ready(self):
        result = preflight('Ethernet0', '4x25G', oidPorts={'Ethernet0'})
        assert result.status == dpb.READY

    def test_a_missing_oid_fails_precheck(self):
        result = preflight('Ethernet0', '4x25G', oidPorts=set())
        assert result.status == dpb.FAILED_PRECHECK
        assert 'no ASIC DB OID' in result.reason
        assert 'Ethernet0' in result.reason

    def test_only_old_children_need_an_oid(self):
        """Target children do not exist yet, so they cannot have OIDs."""
        result = preflight('Ethernet0', '4x25G', oidPorts={'Ethernet0'})
        assert result.status == dpb.READY
        assert sorted(result.targetChildren) == [
            'Ethernet0', 'Ethernet1', 'Ethernet2', 'Ethernet3']

    def test_every_child_without_an_oid_is_named(self):
        result = preflight(
            'Ethernet0', '1x100G',
            brkoutCfg=brkout_cfg(Ethernet0='4x25G'),
            portTable=port_table(('Ethernet0', '0'), ('Ethernet1', '1'),
                                 ('Ethernet2', '2'), ('Ethernet3', '3')),
            oidPorts={'Ethernet0', 'Ethernet2'})
        assert result.status == dpb.FAILED_PRECHECK
        assert 'Ethernet1' in result.reason
        assert 'Ethernet3' in result.reason

    def test_omitting_the_map_skips_the_check(self):
        """Callers that cannot read ASIC DB still rely on the engine guard."""
        result = preflight('Ethernet0', '4x25G', oidPorts=None)
        assert result.status == dpb.READY

    def test_an_already_configured_parent_needs_no_oid(self):
        """No delete happens, so there is nothing to watch leave ASIC DB."""
        result = preflight('Ethernet0', '1x100G', oidPorts=set())
        assert result.status == dpb.SKIPPED_ALREADY_CONFIGURED
