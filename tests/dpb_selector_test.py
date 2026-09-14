import pytest

from config.dpb import (
    DpbPlatformDataError,
    DpbSelectorError,
    ExactTerm,
    RangeTerm,
    getPlatformParents,
    parseSelector,
    resolveParents,
)


def platform_interfaces(*names):
    return {name: {'breakout_modes': {}} for name in names}


FLAT_PLATFORM = platform_interfaces(
    'Ethernet0', 'Ethernet8', 'Ethernet16', 'Ethernet24', 'Ethernet64')

# Deliberately sparse: 32 and 48 are absent, so a range must skip them.
SPARSE_PLATFORM = platform_interfaces(
    'Ethernet0', 'Ethernet8', 'Ethernet64', 'Ethernet128')

HPN_PLATFORM = platform_interfaces(
    'Ethernet1_31', 'Ethernet1_32', 'Ethernet2_1')


class TestSelectorParsing:
    def test_single_exact_term(self):
        assert parseSelector('Ethernet0') == [ExactTerm('Ethernet0')]

    def test_flat_range(self):
        assert parseSelector('Ethernet0-64') == [RangeTerm(0, 64)]

    def test_csv_of_exact_terms(self):
        assert parseSelector('Ethernet0,Ethernet8,Ethernet16') == [
            ExactTerm('Ethernet0'), ExactTerm('Ethernet8'),
            ExactTerm('Ethernet16')]

    def test_mixed_csv_and_range(self):
        assert parseSelector('Ethernet0-8,Ethernet64') == [
            RangeTerm(0, 8), ExactTerm('Ethernet64')]

    def test_hpn_names_are_preserved_verbatim(self):
        assert parseSelector('Ethernet1_31,Ethernet1_32') == [
            ExactTerm('Ethernet1_31'), ExactTerm('Ethernet1_32')]

    def test_equal_bounds_are_an_inclusive_range(self):
        assert parseSelector('Ethernet8-8') == [RangeTerm(8, 8)]

    def test_zero_bounds_are_accepted(self):
        assert parseSelector('Ethernet0-0') == [RangeTerm(0, 0)]

    @pytest.mark.parametrize('selector', [
        '',                                 # empty selector
        'Ethernet0,',                       # trailing comma
        ',Ethernet0',                       # leading comma
        'Ethernet0,,Ethernet8',             # empty inner term
        'Ethernet0, Ethernet8',             # whitespace after comma
        'Ethernet 0',                       # embedded whitespace
        'Ethernet0\t-8',                    # embedded tab
    ])
    def test_malformed_csv_is_rejected(self, selector):
        with pytest.raises(DpbSelectorError):
            parseSelector(selector)

    @pytest.mark.parametrize('selector', [
        'Ethernet64-0',                     # descending
        'Ethernet0-8-16',                   # extra hyphen
        'Ethernet-8',                       # missing start
        'Ethernet0-',                       # missing end
        '-Ethernet8',                       # leading hyphen
        'Ethernet00-8',                     # leading zero start
        'Ethernet0-08',                     # leading zero end
        'Ethernet0-8a',                     # non-decimal bound
        'EthernetX-8',                      # non-decimal start
        'PortChannel0-8',                   # not an Ethernet range
        'Ethernet-BP0-8',                   # back-panel range unsupported
    ])
    def test_malformed_range_is_rejected(self, selector):
        with pytest.raises(DpbSelectorError):
            parseSelector(selector)

    @pytest.mark.parametrize('selector', [
        'Ethernet1_1-32',
        'Ethernet1_1-1_32',
    ])
    def test_compact_hpn_ranges_are_rejected(self, selector):
        with pytest.raises(DpbSelectorError) as excinfo:
            parseSelector(selector)
        assert 'hierarchical port names' in str(excinfo.value)

    def test_oversized_bounds_fail_safely(self):
        with pytest.raises(DpbSelectorError) as excinfo:
            parseSelector('Ethernet0-' + '9' * 500)
        assert 'digits' in str(excinfo.value)

    def test_none_selector_is_rejected(self):
        with pytest.raises(DpbSelectorError):
            parseSelector(None)


class TestParentResolution:
    def resolve(self, selector, platform=FLAT_PLATFORM):
        return resolveParents(
            parseSelector(selector), platform)

    def test_range_is_inclusive_of_both_bounds(self):
        result = self.resolve('Ethernet0-64')
        assert result.parents == [
            'Ethernet0', 'Ethernet8', 'Ethernet16', 'Ethernet24', 'Ethernet64']
        assert result.notParents == []

    def test_range_omits_sparse_gaps_without_allocating_names(self):
        result = self.resolve('Ethernet0-128', SPARSE_PLATFORM)
        assert result.parents == [
            'Ethernet0', 'Ethernet8', 'Ethernet64', 'Ethernet128']

    def test_range_bounds_exclude_out_of_range_parents(self):
        result = self.resolve('Ethernet8-24')
        assert result.parents == ['Ethernet8', 'Ethernet16', 'Ethernet24']

    def test_range_matching_nothing_selects_nothing(self):
        result = self.resolve('Ethernet100-120')
        assert result.parents == []
        assert result.notParents == []

    def test_overlapping_terms_are_deduplicated(self):
        result = self.resolve('Ethernet0-16,Ethernet8,Ethernet0-8')
        assert result.parents == ['Ethernet0', 'Ethernet8', 'Ethernet16']

    def test_output_uses_natural_not_lexicographic_order(self):
        platform = platform_interfaces(
            'Ethernet0', 'Ethernet2', 'Ethernet10', 'Ethernet100')
        result = self.resolve('Ethernet0-100', platform)
        assert result.parents == [
            'Ethernet0', 'Ethernet2', 'Ethernet10', 'Ethernet100']

    def test_exact_non_parent_is_reported_not_raised(self):
        result = self.resolve('Ethernet0,Ethernet999')
        assert result.parents == ['Ethernet0']
        assert result.notParents == ['Ethernet999']

    def test_exact_hpn_parents_resolve(self):
        result = self.resolve('Ethernet1_31,Ethernet1_32', HPN_PLATFORM)
        assert result.parents == ['Ethernet1_31', 'Ethernet1_32']

    def test_hpn_child_is_never_folded_back_to_its_parent(self):
        result = self.resolve('Ethernet1_31_2', HPN_PLATFORM)
        assert result.parents == []
        assert result.notParents == ['Ethernet1_31_2']

    def test_flat_range_does_not_match_hpn_parents(self):
        result = self.resolve('Ethernet0-64', HPN_PLATFORM)
        assert result.parents == []

    def test_flat_range_ignores_non_ethernet_platform_keys(self):
        platform = platform_interfaces('Ethernet0', 'Ethernet-BP8', 'Cpu0')
        result = self.resolve('Ethernet0-64', platform)
        assert result.parents == ['Ethernet0']


class TestPlatformParents:
    def test_valid_mapping_is_returned(self):
        data = {'interfaces': FLAT_PLATFORM}
        assert getPlatformParents(data) == FLAT_PLATFORM

    @pytest.mark.parametrize('data', [
        {},                          # no interfaces key
        {'interfaces': {}},          # empty mapping
        {'interfaces': []},          # wrong type
        {'interfaces': None},
        [],                          # not an object at all
    ])
    def test_malformed_platform_data_is_rejected(self, data):
        with pytest.raises(DpbPlatformDataError):
            getPlatformParents(data)
