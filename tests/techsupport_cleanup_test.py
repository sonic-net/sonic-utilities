import os
import sys
import pyfakefs
import unittest
from pyfakefs.fake_filesystem_unittest import Patcher
from swsscommon import swsscommon
from utilities_common.general import load_module_from_source
from utilities_common.db import Db
from .mock_tables import dbconnector

sys.path.append("scripts")
import techsupport_cleanup as ts_mod


def set_auto_ts_cfg(redis_mock, auto_ts_state="disabled", max_ts="0"):
    redis_mock.set(ts_mod.CFG_DB, ts_mod.AUTO_TS, ts_mod.CFG_STATE, auto_ts_state)
    redis_mock.set(ts_mod.CFG_DB, ts_mod.AUTO_TS, ts_mod.CFG_MAX_TS, max_ts)


def set_auto_ts_dump_info(redis_mock, ts_dump, core_dump, timestamp, container_name):
    key = ts_mod.TS_MAP + "|" + ts_dump
    redis_mock.set(ts_mod.STATE_DB, key, ts_mod.CORE_DUMP, core_dump)
    redis_mock.set(ts_mod.STATE_DB, key, ts_mod.TIMESTAMP, timestamp)
    redis_mock.set(ts_mod.STATE_DB, key, ts_mod.CONTAINER, container_name)


class TestTechsupportCreationEvent(unittest.TestCase):

    def test_no_cleanup_state_disabled(self):
        """
        Scenario: TS_CLEANUP is disabled.  Check no cleanup is performed,
                  even though the techsupport limit is already crossed
        """
        db_wrap = Db()
        redis_mock = db_wrap.db
        set_auto_ts_cfg(redis_mock, max_ts="5")
        with Patcher() as patcher:
            patcher.fs.set_disk_usage(1000, path="/var/dump/")
            patcher.fs.create_file("/var/dump/sonic_dump_random1.tar.gz", st_size=30)
            patcher.fs.create_file("/var/dump/sonic_dump_random2.tar.gz", st_size=30)
            patcher.fs.create_file("/var/dump/sonic_dump_random3.tar.gz", st_size=30)
            ts_mod.handle_techsupport_creation_event("/var/dump/sonic_dump_random3.tar.gz", redis_mock)
            current_fs = os.listdir(ts_mod.TS_DIR)
            print(current_fs)
            assert len(current_fs) == 3
            assert "sonic_dump_random1.tar.gz" in current_fs
            assert "sonic_dump_random2.tar.gz" in current_fs
            assert "sonic_dump_random3.tar.gz" in current_fs

    def test_no_cleanup_state_enabled(self):
        """
        Scenario: TS_CLEANUP is enabled.
                  Verify no cleanup is performed, as the techsupport limit haven't crossed yet
        """
        db_wrap = Db()
        redis_mock = db_wrap.db
        set_auto_ts_cfg(redis_mock, auto_ts_state="enabled", max_ts="10")
        with Patcher() as patcher:
            patcher.fs.set_disk_usage(1000, path="/var/dump/")
            patcher.fs.create_file("/var/dump/sonic_dump_random1.tar.gz", st_size=30)
            patcher.fs.create_file("/var/dump/sonic_dump_random2.tar.gz", st_size=30)
            patcher.fs.create_file("/var/dump/sonic_dump_random3.tar.gz", st_size=30)
            ts_mod.handle_techsupport_creation_event("/var/dump/sonic_dump_random3.tar.gz", redis_mock)
            current_fs = os.listdir(ts_mod.TS_DIR)
            print(current_fs)
            assert len(current_fs) == 3
            assert "sonic_dump_random1.tar.gz" in current_fs
            assert "sonic_dump_random2.tar.gz" in current_fs
            assert "sonic_dump_random3.tar.gz" in current_fs

    def test_dump_cleanup(self):
        """
        Scenario: TS_CLEANUP is enabled. techsupport size limit is crosed
                  Verify Whether is cleanup is performed or not
        """
        db_wrap = Db()
        redis_mock = db_wrap.db
        set_auto_ts_cfg(redis_mock, auto_ts_state="enabled", max_ts="5")
        with Patcher() as patcher:
            patcher.fs.set_disk_usage(1000, path="/var/dump/")
            patcher.fs.create_file("/var/dump/sonic_dump_random1.tar.gz", st_size=25)
            patcher.fs.create_file("/var/dump/sonic_dump_random2.tar.gz", st_size=25)
            patcher.fs.create_file("/var/dump/sonic_dump_random3.tar.gz", st_size=25)
            ts_mod.handle_techsupport_creation_event("/var/dump/sonic_dump_random3.tar.gz", redis_mock)
            current_fs = os.listdir(ts_mod.TS_DIR)
            assert len(current_fs) == 2
            assert "sonic_dump_random1.tar.gz" not in current_fs
            assert "sonic_dump_random2.tar.gz" in current_fs
            assert "sonic_dump_random3.tar.gz" in current_fs

    def test_state_db_update(self):
        """
        Scenario: TS_CLEANUP is enabled. techsupport size limit is crosed
                  Verify Whether is cleanup is performed and the state_db is updated
        """
        db_wrap = Db()
        redis_mock = db_wrap.db
        set_auto_ts_cfg(redis_mock, auto_ts_state="enabled", max_ts="5")
        set_auto_ts_dump_info(redis_mock, "sonic_dump_random1", "orchagent", "1575985", "orchagent")
        set_auto_ts_dump_info(redis_mock, "sonic_dump_random2", "syncd", "1575988", "syncd")
        with Patcher() as patcher:
            patcher.fs.set_disk_usage(1000, path="/var/dump/")
            patcher.fs.create_file("/var/dump/sonic_dump_random1.tar.gz", st_size=25)
            patcher.fs.create_file("/var/dump/sonic_dump_random2.tar.gz", st_size=25)
            patcher.fs.create_file("/var/dump/sonic_dump_random3.tar.gz", st_size=25)
            ts_mod.handle_techsupport_creation_event("/var/dump/sonic_dump_random3.tar.gz", redis_mock)
            current_fs = os.listdir(ts_mod.TS_DIR)
            print(current_fs)
            assert len(current_fs) == 2
            assert "sonic_dump_random1.tar.gz" not in current_fs
            assert "sonic_dump_random2.tar.gz" in current_fs
            assert "sonic_dump_random3.tar.gz" in current_fs
        final_state = redis_mock.keys(ts_mod.STATE_DB, ts_mod.TS_MAP + "*")
        assert ts_mod.TS_MAP + "|sonic_dump_random2" in final_state
        assert ts_mod.TS_MAP + "|sonic_dump_random1" not in final_state
