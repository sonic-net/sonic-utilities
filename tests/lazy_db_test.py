from unittest import mock

import pytest

from utilities_common import db


def test_lazy_db_initializes_once_on_first_attribute(monkeypatch):
    initialize = mock.Mock(side_effect=lambda self: setattr(self, "cfgdb", "ready"))
    monkeypatch.setattr(db.Db, "__init__", initialize)
    lazy = db.LazyDb()

    assert not lazy._db_initialized
    assert lazy.cfgdb == "ready"
    assert lazy.cfgdb == "ready"
    initialize.assert_called_once_with(lazy)


def test_lazy_db_retries_after_failed_initialization(monkeypatch):
    initialize = mock.Mock(side_effect=[RuntimeError("failed"), None])
    monkeypatch.setattr(db.Db, "__init__", initialize)
    lazy = db.LazyDb()

    with pytest.raises(RuntimeError, match="failed"):
        lazy.missing
    assert not lazy._db_initialized
    with pytest.raises(AttributeError):
        lazy.missing
    assert lazy._db_initialized
    assert initialize.call_count == 2
