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

        self._set(d, "ORCHAGENT_QUEUE|ROUTE_TABLE", {"pending_count": "12"})
        self._set(d, "ORCHAGENT_QUEUE|NEIGH_TABLE", {"pending_count": "0"})
        self._set(d, "ORCHAGENT_QUEUE|PORT_TABLE", {"pending_count": "3"})

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

    def test_queue_show_all_includes_zero(self):
        runner = CliRunner()
        db = Db()
        d = db.db

        self._set(d, "ORCHAGENT_QUEUE|ROUTE_TABLE", {"pending_count": "5"})
        self._set(d, "ORCHAGENT_QUEUE|FDB_TABLE", {"pending_count": "0"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'],
            ['--all'], obj=db
        )
        assert result.exit_code == 0
        assert "ROUTE_TABLE" in result.output
        assert "FDB_TABLE" in result.output

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

        self._set(d, "ORCHAGENT_QUEUE|BUSTED_TABLE", {"pending_count": "n/a"})

        result = runner.invoke(
            show.cli.commands['orchagent'].commands['queue'], [], obj=db
        )
        assert result.exit_code == 0
        assert "BUSTED_TABLE" not in result.output
