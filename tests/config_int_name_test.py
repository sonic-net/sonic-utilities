from unittest import mock

from utilities_common.db import Db

import config.main as config


def test_interface_name_checker():
    db = Db()
    db.cfgdb.set_entry("LOOPBACK_INTERFACE", "Loopback0", {"NULL": "NULL"})

    assert config.interface_name_is_valid(db.cfgdb, "Loopback0")
