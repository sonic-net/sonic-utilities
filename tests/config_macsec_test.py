from unittest import mock

from utilities_common.db import Db

from click.testing import CliRunner
import config.main as config


def test_macsec_default_profile():
    runner = CliRunner()
    db = Db()

    profile_name = "test"
    primary_cak = "01234567890123456789012345678912"
    primary_ckn = "01234567890123456789012345678912"
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], [profile_name, "--primary_cak=" + primary_cak,"--primary_ckn=" + primary_ckn], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    profile_table = db.cfgdb.get_entry("MACSEC_PROFILE", profile_name)
    assert profile_table
    assert profile_table["priority"] == "255"
    assert profile_table["cipher_suite"] == "GCM-AES-128"
    assert profile_table["primary_cak"] == primary_cak
    assert profile_table["primary_ckn"] == primary_ckn
    assert profile_table["policy"] == "security"
    assert "enable_replay_protect" not in profile_table
    assert "replay_window" not in profile_table
    assert profile_table["send_sci"] == "true"
    assert "rekey_period" not in profile_table

    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["del"], [profile_name], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    profile_table = db.cfgdb.get_entry("MACSEC_PROFILE", profile_name)
    assert not profile_table


def test_macsec_valid_profile():
    runner = CliRunner()
    db = Db()

    profile_name = "test"
    profile_map = {
        "primary_cak": "0123456789012345678901234567891201234567890123456789012345678912",
        "primary_ckn": "01234567890123456789012345678912",
        "priority": 64,
        "cipher_suite": "GCM-AES-XPN-256",
        "policy": "integrity_only",
        "enable_replay_protect": None,
        "replay_window": 100,
        "no_send_sci": None,
        "rekey_period": 30 * 60,
    }
    options = [profile_name]
    for k, v in profile_map.items():
        options.append("--" + k)
        if v is not None:
            options[-1] += "=" + str(v)

    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], options, obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    profile_table = db.cfgdb.get_entry("MACSEC_PROFILE", profile_name)
    assert profile_table
    assert profile_table["priority"] == str(profile_map["priority"])
    assert profile_table["cipher_suite"] == profile_map["cipher_suite"]
    assert profile_table["primary_cak"] == profile_map["primary_cak"]
    assert profile_table["primary_ckn"] == profile_map["primary_ckn"]
    assert profile_table["policy"] == profile_map["policy"]
    if "enable_replay_protect" in profile_map:
        assert "enable_replay_protect" in profile_table and profile_table["enable_replay_protect"] == "true"
        assert profile_table["replay_window"] == str(profile_map["replay_window"])
    if "send_sci" in profile_map:
        assert profile_table["send_sci"] == "true"
    if "no_send_sci" in profile_map:
        assert profile_table["send_sci"] == "false"
    if "rekey_period" in profile_map:
        assert profile_table["rekey_period"] == str(profile_map["rekey_period"])


def test_macsec_invalid_profile():
    runner = CliRunner()
    db = Db()

    # Loss primary cak and primary ckn
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test"], obj=db)
    assert result.exit_code != 0

    # Invalid primary cak
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test", "--primary_cak=abcdfghjk90123456789012345678912","--primary_ckn=01234567890123456789012345678912", "--cipher_suite=GCM-AES-128"], obj=db)
    assert result.exit_code != 0

    # Invalid primary cak length
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test", "--primary_cak=01234567890123456789012345678912","--primary_ckn=01234567890123456789012345678912", "--cipher_suite=GCM-AES-256"], obj=db)
    assert result.exit_code != 0


def test_macsec_port():
    runner = CliRunner()
    db = Db()

    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test", "--primary_cak=01234567890123456789012345678912","--primary_ckn=01234567890123456789012345678912"], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    result = runner.invoke(config.config.commands["macsec"].commands["port"].commands["add"], ["Ethernet0", "test"], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    port_table = db.cfgdb.get_entry("PORT", "Ethernet0")
    assert port_table 
    assert port_table["macsec"] == "test"

    result = runner.invoke(config.config.commands["macsec"].commands["port"].commands["del"], ["Ethernet0"], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    port_table = db.cfgdb.get_entry("PORT", "Ethernet0")
    assert not port_table["macsec"]


def test_macsec_invalid_operation():
    runner = CliRunner()
    db = Db()

    # Enable nonexisted profile 
    result = runner.invoke(config.config.commands["macsec"].commands["port"].commands["add"], ["Ethernet0", "test"], obj=db)
    assert result.exit_code != 0

    # Delete nonexisted profile
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["del"], ["test"], obj=db)
    assert result.exit_code != 0

    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test", "--primary_cak=01234567890123456789012345678912","--primary_ckn=01234567890123456789012345678912"], obj=db)
    assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
    # Repeat add profile
    result = runner.invoke(config.config.commands["macsec"].commands["profile"].commands["add"], ["test", "--primary_cak=01234567890123456789012345678912","--primary_ckn=01234567890123456789012345678912"], obj=db)
    assert result.exit_code != 0
