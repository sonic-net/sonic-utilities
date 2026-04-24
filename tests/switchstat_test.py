import pytest
import importlib
import logging
import os

from click.testing import CliRunner
from utilities_common.db import Db
from utilities_common.cli import UserCache
from utilities_common.general import load_module_from_source

from .mock_tables import dbconnector
from .switchstat_input import single_asic_output
from .switchstat_input import multi_asic_output
from .switchstat_input import common_output


test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
input_path = os.path.join(test_path, "switchstat_input")
mock_counters_path = os.path.join(input_path, "mock_counters")
switchstat_path = os.path.join(scripts_path, "switchstat")
switchstat = load_module_from_source("switchstat", switchstat_path)

logger = logging.getLogger(__name__)

SUCCESS = 0


def remove_tmp_cnstat_file():
    cache = UserCache("switchstat")
    cache.remove_all()


class TestSwitchStat(object):
    show_switch_period = None

    show_switch_updated = None
    show_switch_updated_tag = None
    show_switch_all = None

    def remove_timestamp(self, output):
        lines = output.splitlines()
        pattern = "Time Since Counters Last Cleared"
        return "\n".join([line for line in lines if pattern not in line])

    def verify_counters(self, options, output, timestamp=False):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(switchstat.main, options, obj=db)
        out = self.remove_timestamp(result.output) if timestamp else result.output
        rc = result.exit_code

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert out == output
        assert rc == SUCCESS

    def verify_counters_show(self, options, output):
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "all")
        self.verify_counters(options, output)

    def verify_counters_diff(self, options, output):
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "all")
        self.verify_counters(["--clear"], common_output.show_switch_clear)
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "updated")
        self.verify_counters(options, output, "--detail" in options)
        self.verify_counters(["--delete"], common_output.show_switch_delete)

    def verify_counters_neg(self, options, output):
        self.verify_counters(options, output)

    def verify_counters_period(self):
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "all")
        self.verify_counters(["--detail", "--period", "1"], self.show_switch_period, timestamp=True)

    def verify_counters_clear(self):
        # regular stats clear
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "all")
        self.verify_counters(["--clear"], common_output.show_switch_clear)

        # stats clear by tag 1
        self.verify_counters(["--clear", "--tag", "test1"], common_output.show_switch_clear_tag1)

        # stats clear by tag 2
        self.verify_counters(["--clear", "--tag", "test2"], common_output.show_switch_clear_tag2)

        # verify regular stats clear
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "updated")
        self.verify_counters(["--all"], self.show_switch_updated)

        # verify stats clear by tag 1
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "updated_tag")
        self.verify_counters(["--all", "--tag", "test1"], self.show_switch_updated_tag)

        # verify raw stats
        dbconnector.dedicated_dbs["COUNTERS_DB"] = os.path.join(mock_counters_path, "all")
        self.verify_counters(["--all", "--raw"], self.show_switch_all)

        # delete regular stats snapshot
        self.verify_counters(["--delete"], common_output.show_switch_delete)

        # verify no regular stats snapshot
        self.verify_counters(["--all"], self.show_switch_all)

        # delete stats snapshot by tag 1
        self.verify_counters(["--delete", "--tag", "test1"], common_output.show_switch_delete_tag1)

        # verify no stats snapshot by tag 1
        self.verify_counters(["--all", "--tag", "test1"], self.show_switch_all)

        # delete all stats snapshots
        self.verify_counters(["--delete-all"], common_output.show_switch_delete_all)

        # verify no stats snapshot by tag 2
        self.verify_counters(["--all", "--tag", "test2"], self.show_switch_all)


class TestSingleAsicSwitchStat(TestSwitchStat):
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.clean_up_config()
        dbconnector.load_database_config()
        remove_tmp_cnstat_file()

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        dbconnector.dedicated_dbs.clear()
        dbconnector.clean_up_config()
        remove_tmp_cnstat_file()

    @pytest.fixture(scope="class")
    def period_data(self, request):
        logger.info("Initialize single asic counters period data")
        request.cls.show_switch_period = single_asic_output.show_switch_period

        yield

        request.cls.show_switch_period = None
        logger.info("Deinitialize single asic counters period data")

    @pytest.fixture(scope="class")
    def clear_data(self, request):
        logger.info("Initialize single asic counters clear data")

        request.cls.show_switch_updated = single_asic_output.show_switch_updated
        request.cls.show_switch_updated_tag = single_asic_output.show_switch_updated_tag
        request.cls.show_switch_all = single_asic_output.show_switch_all

        yield

        request.cls.show_switch_updated = None
        request.cls.show_switch_updated_tag = None
        request.cls.show_switch_all = None
        logger.info("Deinitialize single asic counters clear data")

    # ---------- SHOW SINGLE ASIC SWITCH COUNTERS ---------- #

    @pytest.mark.parametrize(
        "options, output", [
            pytest.param(["--all"], single_asic_output.show_switch_all, id="plain-all"),
            pytest.param(["--trim"], single_asic_output.show_switch_all, id="plain-trim"),
            pytest.param([], single_asic_output.show_switch_all, id="plain-std"),
            pytest.param(["--detail"], single_asic_output.show_switch_detailed, id="plain-detail"),
            pytest.param(["--all", "--json"], single_asic_output.show_switch_all_json, id="json-all"),
            pytest.param(["--trim", "--json"], single_asic_output.show_switch_all_json, id="json-trim"),
            pytest.param(["--json"], single_asic_output.show_switch_all_json, id="json-std")
        ]
    )
    def test_counters_show(self, options, output):
        self.verify_counters_show(options, output)

    @pytest.mark.parametrize(
        "options, output", [
            pytest.param(["--all"], single_asic_output.show_switch_updated, id="plain-all"),
            pytest.param(["--trim"], single_asic_output.show_switch_updated, id="plain-trim"),
            pytest.param([], single_asic_output.show_switch_updated, id="plain-std"),
            pytest.param(["--detail"], single_asic_output.show_switch_updated_detailed, id="plain-detail"),
            pytest.param(["--all", "--json"], single_asic_output.show_switch_updated_json, id="json-all"),
            pytest.param(["--trim", "--json"], single_asic_output.show_switch_updated_json, id="json-trim"),
            pytest.param(["--json"], single_asic_output.show_switch_updated_json, id="json-std")
        ]
    )
    def test_counters_show_diff(self, options, output):
        self.verify_counters_diff(options, output)

    @pytest.mark.parametrize(
        "options, output, cntdb", [
            pytest.param(
                ["--all"],
                single_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "no_map"),
                id="no-map-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                single_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "no_map"),
                id="no-map-json-all"
            ),
            pytest.param(
                ["--all"],
                single_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "no_counters"),
                id="no-cnt-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                single_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "no_counters"),
                id="no-cnt-json-all"
            ),
            pytest.param(
                ["--all"],
                single_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "empty"),
                id="empty-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                single_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "empty"),
                id="empty-json-all"
            ),
            pytest.param(
                ["--all"],
                single_asic_output.show_switch_neg_partial,
                os.path.join(mock_counters_path, "partial"),
                id="partial-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                single_asic_output.show_switch_neg_partial_json,
                os.path.join(mock_counters_path, "partial"),
                id="partial-json-all"
            )
        ]
    )
    def test_counters_show_neg(self, options, output, cntdb):
        dbconnector.dedicated_dbs["COUNTERS_DB"] = cntdb
        self.verify_counters_neg(options, output)

    def test_counters_period(self, period_data):
        self.verify_counters_period()

    def test_counters_clear(self, clear_data):
        self.verify_counters_clear()


class TestMultiAsicSwitchStat(TestSwitchStat):
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        from .mock_tables import mock_multi_asic_3_asics
        importlib.reload(mock_multi_asic_3_asics)
        dbconnector.clean_up_config()
        dbconnector.load_namespace_config()
        remove_tmp_cnstat_file()

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        dbconnector.dedicated_dbs.clear()
        dbconnector.clean_up_config()
        remove_tmp_cnstat_file()

    @pytest.fixture(scope="class")
    def period_data(self, request):
        logger.info("Initialize multi asic counters period data")
        request.cls.show_switch_period = multi_asic_output.show_switch_period

        yield

        request.cls.show_switch_period = None
        logger.info("Deinitialize multi asic counters period data")

    @pytest.fixture(scope="class")
    def clear_data(self, request):
        logger.info("Initialize multi asic counters clear data")

        request.cls.show_switch_updated = multi_asic_output.show_switch_updated
        request.cls.show_switch_updated_tag = multi_asic_output.show_switch_updated_tag
        request.cls.show_switch_all = multi_asic_output.show_switch_all

        yield

        request.cls.show_switch_updated = None
        request.cls.show_switch_updated_tag = None
        request.cls.show_switch_all = None
        logger.info("Deinitialize multi asic counters clear data")

    # ---------- SHOW MULTI ASIC SWITCH COUNTERS ---------- #

    @pytest.mark.parametrize(
        "options, output", [
            pytest.param(["--all"], multi_asic_output.show_switch_all, id="plain-all"),
            pytest.param(["--trim"], multi_asic_output.show_switch_all, id="plain-trim"),
            pytest.param([], multi_asic_output.show_switch_all, id="plain-std"),
            pytest.param(["--detail"], multi_asic_output.show_switch_detailed, id="plain-detail"),
            pytest.param(["--all", "--json"], multi_asic_output.show_switch_all_json, id="json-all"),
            pytest.param(["--trim", "--json"], multi_asic_output.show_switch_all_json, id="json-trim"),
            pytest.param(["--json"], multi_asic_output.show_switch_all_json, id="json-std")
        ]
    )
    def test_counters_show(self, options, output):
        self.verify_counters_show(options, output)

    @pytest.mark.parametrize(
        "options, output", [
            pytest.param(["--all"], multi_asic_output.show_switch_updated, id="plain-all"),
            pytest.param(["--trim"], multi_asic_output.show_switch_updated, id="plain-trim"),
            pytest.param([], multi_asic_output.show_switch_updated, id="plain-std"),
            pytest.param(["--detail"], multi_asic_output.show_switch_updated_detailed, id="plain-detail"),
            pytest.param(["--all", "--json"], multi_asic_output.show_switch_updated_json, id="json-all"),
            pytest.param(["--trim", "--json"], multi_asic_output.show_switch_updated_json, id="json-trim"),
            pytest.param(["--json"], multi_asic_output.show_switch_updated_json, id="json-std")
        ]
    )
    def test_counters_show_diff(self, options, output):
        self.verify_counters_diff(options, output)

    @pytest.mark.parametrize(
        "options, output, cntdb", [
            pytest.param(
                ["--all"],
                multi_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "no_map"),
                id="no-map-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                multi_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "no_map"),
                id="no-map-json-all"
            ),
            pytest.param(
                ["--all"],
                multi_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "no_counters"),
                id="no-cnt-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                multi_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "no_counters"),
                id="no-cnt-json-all"
            ),
            pytest.param(
                ["--all"],
                multi_asic_output.show_switch_neg_na,
                os.path.join(mock_counters_path, "empty"),
                id="empty-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                multi_asic_output.show_switch_neg_na_json,
                os.path.join(mock_counters_path, "empty"),
                id="empty-json-all"
            ),
            pytest.param(
                ["--all"],
                multi_asic_output.show_switch_neg_partial,
                os.path.join(mock_counters_path, "partial"),
                id="partial-plain-all"
            ),
            pytest.param(
                ["--all", "--json"],
                multi_asic_output.show_switch_neg_partial_json,
                os.path.join(mock_counters_path, "partial"),
                id="partial-json-all"
            )
        ]
    )
    def test_counters_show_neg(self, options, output, cntdb):
        dbconnector.dedicated_dbs["COUNTERS_DB"] = cntdb
        self.verify_counters_neg(options, output)

    def test_counters_period(self, period_data):
        self.verify_counters_period()

    def test_counters_clear(self, clear_data):
        self.verify_counters_clear()
