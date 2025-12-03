import os
import pytest

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))

dns_show_nameservers_header = """\
  Nameserver
------------
"""

dns_show_nameservers = """\
          Nameserver
--------------------
             1.1.1.1
2001:4860:4860::8888
"""

class TestDns(object):

    valid_nameservers = (
        ("1.1.1.1",),
        ("1.1.1.1", "8.8.8.8", "10.10.10.10",),
        ("1.1.1.1", "2001:4860:4860::8888"),
        ("2001:4860:4860::8888", "2001:4860:4860::8844", "2001:4860:4860::8800")
    )

    invalid_nameservers = (
        "0.0.0.0",
        "255.255.255.255",
        "224.0.0.0",
        "0::0",
        "0::1",
        "1.1.1.x",
        "2001:4860:4860.8888",
        "ff02::1"
    )

    config_dns_ns_add = config.config.commands["dns"].commands["nameserver"].commands["add"]
    config_dns_ns_del = config.config.commands["dns"].commands["nameserver"].commands["del"]
    show_dns_ns = show.cli.commands["dns"].commands["nameserver"]

    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

    @pytest.mark.parametrize('nameservers', valid_nameservers)
    def test_dns_config_nameserver_add_del_with_valid_ip_addresses(self, nameservers):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        for ip in nameservers:
            # config dns nameserver add <ip>
            result = runner.invoke(self.config_dns_ns_add, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert ip in db.cfgdb.get_table('DNS_NAMESERVER')

        for ip in nameservers:
            # config dns nameserver del <ip>
            result = runner.invoke(self.config_dns_ns_del, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert ip not in db.cfgdb.get_table('DNS_NAMESERVER')

    @pytest.mark.parametrize('nameserver', invalid_nameservers)
    def test_dns_config_nameserver_add_del_with_invalid_ip_addresses(self, nameserver):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        # config dns nameserver add <nameserver>
        result = runner.invoke(self.config_dns_ns_add, [nameserver], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "invalid nameserver ip address" in result.output

        # config dns nameserver del <nameserver>
        result = runner.invoke(self.config_dns_ns_del, [nameserver], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "invalid nameserver ip address" in result.output

    @pytest.mark.parametrize('nameservers', valid_nameservers)
    def test_dns_config_nameserver_add_existing_ip(self, nameservers):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        for ip in nameservers:
            # config dns nameserver add <ip>
            result = runner.invoke(self.config_dns_ns_add, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert ip in db.cfgdb.get_table('DNS_NAMESERVER')

            # Execute command once more
            result = runner.invoke(self.config_dns_ns_add, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "nameserver is already configured" in result.output

            # config dns nameserver del <ip>
            result = runner.invoke(self.config_dns_ns_del, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0

    @pytest.mark.parametrize('nameservers', valid_nameservers)
    def test_dns_config_nameserver_del_unexisting_ip(self, nameservers):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        for ip in nameservers:
            # config dns nameserver del <ip>
            result = runner.invoke(self.config_dns_ns_del, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "is not configured" in result.output

    def test_dns_config_nameserver_add_max_number(self):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        nameservers = ("1.1.1.1", "2.2.2.2", "3.3.3.3")
        for ip in nameservers:
            # config dns nameserver add <ip>
            result = runner.invoke(self.config_dns_ns_add, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0

        # config dns nameserver add <ip>
        result = runner.invoke(self.config_dns_ns_add, ["4.4.4.4"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "nameservers exceeded" in result.output

        for ip in nameservers:
            # config dns nameserver del <ip>
            result = runner.invoke(self.config_dns_ns_del, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0

    def test_dns_show_nameserver_empty_table(self):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        # show dns nameserver
        result = runner.invoke(self.show_dns_ns, [], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == dns_show_nameservers_header

    def test_dns_show_nameserver(self):
        db = Db()
        runner = CliRunner()
        obj = {'db': db.cfgdb}

        nameservers = ("1.1.1.1", "2001:4860:4860::8888")

        for ip in nameservers:
            # config dns nameserver add <ip>
            result = runner.invoke(self.config_dns_ns_add, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert ip in db.cfgdb.get_table('DNS_NAMESERVER')

        # show dns nameserver
        result = runner.invoke(self.show_dns_ns, [], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == dns_show_nameservers

        for ip in nameservers:
            # config dns nameserver del <ip>
            result = runner.invoke(self.config_dns_ns_del, [ip], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert ip not in db.cfgdb.get_table('DNS_NAMESERVER')
