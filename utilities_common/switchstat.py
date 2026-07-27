import click
import json
import os

from natsort import natsorted
from tabulate import tabulate
from datetime import datetime
from swsscommon.swsscommon import COUNTERS_SWITCH_NAME_MAP, COUNTERS_TABLE
from utilities_common import multi_asic as multi_asic_util
from utilities_common.netstat import ns_diff, format_number_with_comma
from utilities_common.cli import UserCache, json_serial


HEADER_ALL = ["TrimSent/pkts", "TrimDrop/pkts"]
HEADER_STD = ["TrimSent/pkts", "TrimDrop/pkts"]
HEADER_TRIM = ["TrimSent/pkts", "TrimDrop/pkts"]

counter_dict = {
    "trim_tx": "SAI_SWITCH_STAT_TX_TRIM_PACKETS",
    "trim_drp": "SAI_SWITCH_STAT_DROPPED_TRIM_PACKETS"
}


class SwitchStat(object):
    def __init__(self, namespace, display, tag):
        # Initialize cache
        self.init_cache(tag)

        # Initialize the multi-asic namespace
        self.db = None
        self.multi_asic = multi_asic_util.MultiAsic(display, namespace)

        # Initialize counters default dict
        self.cnstat_dict_default = {k: "N/A" for k in counter_dict.keys()}

    def init_cache(self, tag):
        self.cache = UserCache(app_name="switchstat", tag=tag)

        self.cnstat_file = "switchstat"
        self.cnstat_dir = self.cache.get_directory()
        self.cnstat_fqn_file = os.path.join(self.cnstat_dir, self.cnstat_file)

    def is_cache_exists(self):
        return os.path.isfile(self.cnstat_fqn_file)

    def remove_stats(self, all=False):
        if all:
            self.cache.remove_all()
        else:
            self.cache.remove()

    def load_stats(self):
        return json.load(open(self.cnstat_fqn_file, "r"))

    def save_stats(self, cnstat_dict):
        json.dump(cnstat_dict, open(self.cnstat_fqn_file, "w"), default=json_serial)

    def get_cnstat(self):
        cnstat_dict = {}

        if not self.db.exists(self.db.COUNTERS_DB, COUNTERS_SWITCH_NAME_MAP):
            return self.cnstat_dict_default

        switch_name_map = self.db.get_all(self.db.COUNTERS_DB, COUNTERS_SWITCH_NAME_MAP)
        switch_oid = switch_name_map.get("ASIC", None)

        if switch_oid is None:
            return self.cnstat_dict_default

        switch_stat_key = "{}{}{}".format(
            COUNTERS_TABLE,
            self.db.get_db_separator(self.db.COUNTERS_DB),
            switch_oid
        )

        if not self.db.exists(self.db.COUNTERS_DB, switch_stat_key):
            return self.cnstat_dict_default

        switch_stat_dict = self.db.get_all(self.db.COUNTERS_DB, switch_stat_key)

        for key, value in counter_dict.items():
            cnstat_dict[key] = switch_stat_dict.get(value, "N/A")

        return cnstat_dict

    @multi_asic_util.run_on_multi_asic
    def collect_stat(self):
        cnstat_dict = self.get_cnstat()

        if self.multi_asic.is_multi_asic:
            self.cnstat_dict[self.multi_asic.current_namespace] = {}
            self.cnstat_dict[self.multi_asic.current_namespace].update(cnstat_dict)
        else:
            self.cnstat_dict.update(cnstat_dict)

    def get_cnstat_dict(self, timestamp=False):
        self.cnstat_dict = {}
        self.collect_stat()

        if timestamp:  # shallow copy to inject timestamp
            cnstat_dict = {}
            cnstat_dict.update(self.cnstat_dict)
            cnstat_dict["time"] = datetime.now()
            return cnstat_dict

        return self.cnstat_dict

    def cnstat_print(self, cnstat_dict, print_all, print_trim, detail, json_fmt):
        def print_json(cntr):
            def build_json(data):
                json_dict = {}

                json_dict["trim_sent"] = format_number_with_comma(data["trim_tx"])
                json_dict["trim_drop"] = format_number_with_comma(data["trim_drp"])

                return json_dict

            if not self.multi_asic.is_multi_asic:
                click.echo(json.dumps(build_json(cntr), indent=4, sort_keys=True))
                return

            json_dict = {}

            for ns in cntr.keys():
                json_dict[ns] = build_json(cntr[ns])

            click.echo(json.dumps(json_dict, indent=4, sort_keys=True))

        def print_detail(cntr, ns=None):
            if ns is not None:
                click.echo("Namespace: {}".format(ns))
                click.echo()

            click.echo("Trimmed Sent Packets........................... {}".format(
                format_number_with_comma(cntr["trim_tx"])
            ))
            click.echo("Trimmed Dropped Packets........................ {}".format(
                format_number_with_comma(cntr["trim_drp"])
            ))

        def print_table(cntr, ns=None):
            if ns is not None:
                click.echo("Namespace: {}".format(ns))
                click.echo()

            header = None
            body = []

            if print_all:  # all counters
                header = HEADER_ALL
                body.append((
                    format_number_with_comma(cntr["trim_tx"]),
                    format_number_with_comma(cntr["trim_drp"])
                ))
            elif print_trim:  # trim counters
                header = HEADER_TRIM
                body.append((
                    format_number_with_comma(cntr["trim_tx"]),
                    format_number_with_comma(cntr["trim_drp"])
                ))
            else:  # standard counters
                header = HEADER_STD
                body.append((
                    format_number_with_comma(cntr["trim_tx"]),
                    format_number_with_comma(cntr["trim_drp"])
                ))

            click.echo(tabulate(body, header, tablefmt="simple", stralign="right"))

        if json_fmt:
            print_json(cnstat_dict)
            return

        if not self.multi_asic.is_multi_asic:
            if detail:
                print_detail(cnstat_dict)
            else:
                print_table(cnstat_dict)
            return

        ns_list = natsorted(cnstat_dict.keys())

        if detail:
            print_detail(cnstat_dict[ns_list[0]], ns_list[0])

            for ns in ns_list[1:]:
                click.echo()
                print_detail(cnstat_dict[ns], ns)
        else:
            print_table(cnstat_dict[ns_list[0]], ns_list[0])

            for ns in ns_list[1:]:
                click.echo()
                print_table(cnstat_dict[ns], ns)

    def cnstat_diff_print(self, cnstat_dict, cnstat_old_dict, print_all, print_trim, detail, json_fmt):
        def print_json(cntr, old_cntr):
            def build_json(data, old_data):
                json_dict = {}

                json_dict["trim_sent"] = ns_diff(data["trim_tx"], old_data["trim_tx"])
                json_dict["trim_drop"] = ns_diff(data["trim_drp"], old_data["trim_drp"])

                return json_dict

            if not self.multi_asic.is_multi_asic:
                click.echo(json.dumps(build_json(cntr, old_cntr), indent=4, sort_keys=True))
                return

            json_dict = {}

            for ns in cntr.keys():
                json_dict[ns] = build_json(cntr[ns], old_cntr[ns])

            click.echo(json.dumps(json_dict, indent=4, sort_keys=True))

        def print_detail(cntr, old_cntr, ts, ns=None):
            if ns is not None:
                click.echo("Namespace: {}".format(ns))
                click.echo()

            click.echo("Trimmed Sent Packets........................... {}".format(
                ns_diff(cntr["trim_tx"], old_cntr["trim_tx"])
            ))
            click.echo("Trimmed Dropped Packets........................ {}".format(
                ns_diff(cntr["trim_drp"], old_cntr["trim_drp"])
            ))
            click.echo()

            click.echo("Time Since Counters Last Cleared............... {}".format(ts))

        def print_table(cntr, old_cntr, ns=None):
            if ns is not None:
                click.echo("Namespace: {}".format(ns))
                click.echo()

            header = None
            body = []

            if print_all:  # all counters
                header = HEADER_ALL
                body.append((
                    ns_diff(cntr["trim_tx"], old_cntr["trim_tx"]),
                    ns_diff(cntr["trim_drp"], old_cntr["trim_drp"])
                ))
            elif print_trim:  # trim counters
                header = HEADER_TRIM
                body.append((
                    ns_diff(cntr["trim_tx"], old_cntr["trim_tx"]),
                    ns_diff(cntr["trim_drp"], old_cntr["trim_drp"])
                ))
            else:  # standard counters
                header = HEADER_STD
                body.append((
                    ns_diff(cntr["trim_tx"], old_cntr["trim_tx"]),
                    ns_diff(cntr["trim_drp"], old_cntr["trim_drp"])
                ))

            click.echo(tabulate(body, header, tablefmt="simple", stralign="right"))

        if json_fmt:
            print_json(cnstat_dict, cnstat_old_dict)
            return

        if not self.multi_asic.is_multi_asic:
            if detail:
                print_detail(cnstat_dict, cnstat_old_dict, cnstat_old_dict["time"])
            else:
                print_table(cnstat_dict, cnstat_old_dict)
            return

        ns_list = natsorted(cnstat_dict.keys())

        if detail:
            print_detail(cnstat_dict[ns_list[0]], cnstat_old_dict[ns_list[0]], cnstat_old_dict["time"], ns_list[0])

            for ns in ns_list[1:]:
                click.echo()
                print_detail(cnstat_dict[ns], cnstat_old_dict[ns], cnstat_old_dict["time"], ns)
        else:
            print_table(cnstat_dict[ns_list[0]], cnstat_old_dict[ns_list[0]], ns_list[0])

            for ns in ns_list[1:]:
                click.echo()
                print_table(cnstat_dict[ns], cnstat_old_dict[ns], ns)
