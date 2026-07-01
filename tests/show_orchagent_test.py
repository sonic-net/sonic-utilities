import os

from click.testing import CliRunner

import show.main as show
from utilities_common.db import Db


class TestShowOrchagentQueue:
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @staticmethod
    def _set(db, key, kvs):
        for f, v in kvs.items():
            db.set(db.STATE_DB, key, f, v)

    @staticmethod
    def _clear_orchagent_queue(db):
        """Remove any ORCHAGENT_QUEUE|* keys so each test starts clean. The
        mock dbconnector backing is shared across tests in the same process."""
        for key in db.keys(db.STATE_DB, "ORCHAGENT_QUEUE|*") or []:
            db.delete(db.STATE_DB, key)

    def setup_method(self, method):
        # Per-test fresh DB. Pytest invokes this before each test method.
        db = Db().db
        self._clear_orchagent_queue(db)

    def test_queue_only_nonzero_by_default(self):
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d, "ORCHAGENT_QUEUE|RouteOrch|ROUTE_TABLE",
                  {"pending_count": "12", "orch": "RouteOrch", "consumer": "ROUTE_TABLE"})
        self._set(d, "ORCHAGENT_QUEUE|NeighOrch|NEIGH_TABLE",
                  {"pending_count": "0", "orch": "NeighOrch", "consumer": "NEIGH_TABLE"})
        self._set(d, "ORCHAGENT_QUEUE|PortsOrch|PORT_TABLE",
                  {"pending_count": "3", "orch": "PortsOrch", "consumer": "PORT_TABLE"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        # NEIGH_TABLE has pending_count=0, should NOT appear by default
        assert "NEIGH_TABLE" not in result.output
        # ROUTE_TABLE should be listed before PORT_TABLE because 12 > 3
        idx_route = result.output.find("ROUTE_TABLE")
        idx_port = result.output.find("PORT_TABLE")
        assert idx_route != -1 and idx_port != -1
        assert idx_route < idx_port
        # Owning Orch name must be visible.
        assert "RouteOrch" in result.output
        assert "PortsOrch" in result.output

    def test_queue_show_all_includes_zero(self):
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d, "ORCHAGENT_QUEUE|RouteOrch|ROUTE_TABLE",
                  {"pending_count": "5", "orch": "RouteOrch", "consumer": "ROUTE_TABLE"})
        self._set(d, "ORCHAGENT_QUEUE|FdbOrch|FDB_TABLE",
                  {"pending_count": "0", "orch": "FdbOrch", "consumer": "FDB_TABLE"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'],
            ['--all'], obj=db
        )
        assert result.exit_code == 0
        assert "ROUTE_TABLE" in result.output
        assert "FDB_TABLE" in result.output

    def test_queue_disambiguates_consumer_shared_across_orchs(self):
        """The same consumer table name (e.g. CFG_FLEX_COUNTER_TABLE) is
        registered in multiple Orchs. The CLI must show both rows with their
        owning Orch in the output, not collapse them."""
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d,
                  "ORCHAGENT_QUEUE|WatermarkOrch|CFG_FLEX_COUNTER_TABLE",
                  {"pending_count": "7",
                   "orch": "WatermarkOrch",
                   "consumer": "CFG_FLEX_COUNTER_TABLE"})
        self._set(d,
                  "ORCHAGENT_QUEUE|FlexCounterOrch|CFG_FLEX_COUNTER_TABLE",
                  {"pending_count": "4",
                   "orch": "FlexCounterOrch",
                   "consumer": "CFG_FLEX_COUNTER_TABLE"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        assert "WatermarkOrch" in result.output
        assert "FlexCounterOrch" in result.output
        # Both pending counts must be visible.
        assert "7" in result.output
        assert "4" in result.output

    def test_queue_empty_state_db(self):
        runner = CliRunner()
        db = Db()

        # setup_method has cleared ORCHAGENT_QUEUE|* keys; nothing else
        # populates them.
        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        # No keys → friendly message, not a crash
        assert ("pending tasks" in result.output
                or "No orchagent queue" in result.output)

    def test_queue_garbage_pending_count_treated_as_zero(self):
        """If the producer ever writes a non-integer pending_count (shouldn't
        happen, but be defensive), the row is treated as zero and hidden by
        default."""
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d, "ORCHAGENT_QUEUE|TestOrch|BUSTED_TABLE",
                  {"pending_count": "n/a",
                   "orch": "TestOrch",
                   "consumer": "BUSTED_TABLE"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        assert "BUSTED_TABLE" not in result.output

    def test_queue_legacy_two_part_key_still_renders(self):
        """If a row was written by a pre-upgrade orchagent that used the
        ORCHAGENT_QUEUE|<consumer> key format (no Orch prefix, no orch/
        consumer fields), the CLI should still render it rather than crash.
        Orch column shows '-' as a placeholder."""
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d, "ORCHAGENT_QUEUE|ROUTE_TABLE", {"pending_count": "9"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        assert "ROUTE_TABLE" in result.output
        assert "9" in result.output
