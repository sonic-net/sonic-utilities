import pytest

import os
import json
import logging

import show.main as show

from click.testing import CliRunner

from utilities_common.cli import UserCache
from utilities_common.cli import json_dump

from .utils import get_result_and_return_code
from .queuestat_input import assert_show_output


test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

logger = logging.getLogger(__name__)

SUCCESS = 0


def remove_tmp_cnstat_file():
    cache = UserCache("queuestat")
    cache.remove_all()


def remove_timestamp(result):
    result_json = json.loads(result)
    for key in result_json.keys():
        result_json[key].pop("time", None)
    return json_dump(result_json)


def verify_after_clear(output, expected_out):
    # ignore lines containing 'Last cached time was' as it has time stamp and is diffcult to compare
    lines = [x for x in output.splitlines() if 'Last cached time was' not in x]
    new_output = '\n'.join(lines)
    assert new_output == expected_out


class TestQueueStat(object):
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"

    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    @pytest.mark.parametrize(
        "output", [
            pytest.param(
                {
                    "plain": assert_show_output.counters_all,
                    "json": assert_show_output.counters_all_json
                },
                id="all"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_queue_counters(self, format, output):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            ["--all"] if format == "plain" else ["--all", "--json"]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        if format == "json":
            assert "{}\n".format(remove_timestamp(result.output)) == output[format]
        else:
            assert result.output == output[format]

        assert result.exit_code == SUCCESS

        cmd = ['queuestat', '--all']

        if format == "json":
            cmd.append('-j')

        return_code, result = get_result_and_return_code(cmd)
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        if format == "json":
            result = "{}\n".format(remove_timestamp(result))

        assert result == output[format]
        assert return_code == SUCCESS


class TestQueueTrimStat(object):
    @classmethod
    def setup_class(cls):
        logger.info("SETUP")
        remove_tmp_cnstat_file()
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"

    @classmethod
    def teardown_class(cls):
        logger.info("TEARDOWN")
        remove_tmp_cnstat_file()
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    @pytest.mark.parametrize(
        "output", [
            pytest.param(
                {
                    "plain": assert_show_output.trim_counters_all,
                    "json": assert_show_output.trim_counters_all_json
                },
                id="all"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_queue_trim_counters(self, format, output):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            ["--trim"] if format == "plain" else ["--trim", "--json"]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        if format == "json":
            assert "{}\n".format(remove_timestamp(result.output)) == output[format]
        else:
            assert result.output == output[format]

        assert result.exit_code == SUCCESS

        cmd = ['queuestat', '--trim']

        if format == "json":
            cmd.append('-j')

        return_code, result = get_result_and_return_code(cmd)
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        if format == "json":
            result = "{}\n".format(remove_timestamp(result))

        assert result == output[format]
        assert return_code == SUCCESS

    @pytest.mark.parametrize(
        "intf,output", [
            pytest.param(
                "Ethernet0",
                {
                    "plain": assert_show_output.trim_eth0_counters,
                    "json": assert_show_output.trim_eth0_counters_json
                },
                id="eth0"
            ),
            pytest.param(
                "Ethernet4",
                {
                    "plain": assert_show_output.trim_eth4_counters,
                    "json": assert_show_output.trim_eth4_counters_json
                },
                id="eth4"
            ),
            pytest.param(
                "Ethernet8",
                {
                    "plain": assert_show_output.trim_eth8_counters,
                    "json": assert_show_output.trim_eth8_counters_json
                },
                id="eth8"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_queue_trim_counters_intf(self, format, intf, output):
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["queue"].commands["counters"],
            [intf, "--trim"] if format == "plain" else [intf, "--trim", "--json"]
        )
        logger.debug("result:\n{}".format(result.output))
        logger.debug("return_code:\n{}".format(result.exit_code))

        if format == "json":
            assert "{}\n".format(remove_timestamp(result.output)) == output[format]
        else:
            assert result.output == output[format]

        assert result.exit_code == SUCCESS

        cmd = ['queuestat', '--trim', '-p', intf]

        if format == "json":
            cmd.append('-j')

        return_code, result = get_result_and_return_code(cmd)
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        if format == "json":
            result = "{}\n".format(remove_timestamp(result))

        assert result == output[format]
        assert return_code == SUCCESS

    def test_clear_queue_trim_counters(self):
        # Clear counters
        return_code, result = get_result_and_return_code(
            ['queuestat', '-c']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_clear_msg
        assert return_code == SUCCESS

        # Verify updated stats
        return_code, result = get_result_and_return_code(
            ['queuestat', '--trim']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        verify_after_clear(result, assert_show_output.trim_counters_clear_stat)
        assert return_code == SUCCESS

        # Verify stats after snapshot cleanup
        return_code, result = get_result_and_return_code(
            ['queuestat', '--trim', '-d']
        )
        logger.debug("result:\n{}".format(result))
        logger.debug("return_code:\n{}".format(return_code))

        assert result == assert_show_output.trim_counters_all
        assert return_code == SUCCESS
