"""Per-user display baselines for cumulative gearbox FEC counters."""

import json
import os
import sys

from utilities_common.cli import UserCache


GEARBOX_CACHE_KEY = '_gearbox'
GB_COUNTERS_DB = 'GB_COUNTERS_DB'
FEC_HISTOGRAM_BINS = tuple(
    'SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S{}'.format(i) for i in range(16)
)
FEC_COUNTERS = FEC_HISTOGRAM_BINS + (
    'SAI_PORT_STAT_IF_IN_FEC_CORRECTABLE_FRAMES',
    'SAI_PORT_STAT_IF_IN_FEC_NOT_CORRECTABLE_FRAMES',
    'SAI_PORT_STAT_IF_IN_FEC_SYMBOL_ERRORS',
    'SAI_PORT_STAT_IF_IN_FEC_CORRECTED_BITS',
)


def snapshot_gearbox_counters(db):
    """Read both sides from an already connected ASIC, without clearing Redis."""
    if GB_COUNTERS_DB not in db.get_db_list():
        return {}
    port_map = db.get_all(GB_COUNTERS_DB, 'COUNTERS_PORT_NAME_MAP') or {}
    ports = {}
    for oid in set(port_map.values()):
        counters = db.get_all(GB_COUNTERS_DB, 'COUNTERS:' + oid) or {}
        ports[oid] = {name: counters[name] for name in FEC_COUNTERS if name in counters}
    return ports


def load_gearbox_baseline(namespace):
    """Read the default portstat snapshot for the same user and namespace."""
    try:
        path = os.path.join(UserCache(app_name='portstat').get_directory(), 'portstat')
        with open(path) as stream:
            saved = json.load(stream)
        baseline = saved.get(GEARBOX_CACHE_KEY, {}).get(namespace or '', {})
        if not isinstance(baseline, dict) or any(not isinstance(v, dict) for v in baseline.values()):
            raise ValueError('Expected gearbox counter dictionaries')
        return baseline
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, AttributeError) as e:
        print('Warning: failed to read gearbox counter baseline: {}'.format(e), file=sys.stderr)
        return {}


def subtract_gearbox_baseline(counters, baseline):
    """Subtract integer counts; a decreased count starts a new counter lifetime."""
    result = dict(counters)
    for name in FEC_COUNTERS:
        if name not in counters or name not in baseline:
            continue
        current, previous = int(counters[name]), int(baseline[name])
        result[name] = str(current - previous if current >= previous else current)
    return result


def get_gearbox_fec_max_t(counters, fallback):
    """Find the highest histogram bin with codewords since the saved baseline."""
    if any(name not in counters for name in FEC_HISTOGRAM_BINS):
        return fallback
    return str(max((i for i, name in enumerate(FEC_HISTOGRAM_BINS)
                    if int(counters[name]) > 0), default=-1))
