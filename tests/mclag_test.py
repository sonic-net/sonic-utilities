import os
import traceback
import mock
import jsonpatch

from click.testing import CliRunner

import config.main as config
import config.mclag as mclag
import show.main as show
from utilities_common.db import Db
from mock import patch
from jsonpatch import JsonPatchConflict

MCLAG_DOMAIN_ID = "123"
MCLAG_NONEXISTENT_DOMAIN_ID = "234"
MCLAG_INVALID_DOMAIN_ID1 = "-1"
MCLAG_INVALID_DOMAIN_ID2 = "5000"
MCLAG_DOMAIN_ID2 = "500"
MCLAG_DOMAIN_ID3 = "1000"
MCLAG_SRC_IP    = "12.1.1.1"
RESERVED_IP    = "0.0.0.0"
INVALID_IP    = "255.255.255.255"
NOT_IP    = "abcd"
MCLAG_PEER_IP   = "12.1.1.2"
MCLAG_KEEPALIVE_TIMER  = "5"
MCLAG_SESSION_TIMEOUT  = "20"
MCLAG_MEMBER_PO  = "PortChannel10"
MCLAG_MEMBER_PO2 = "PortChannel20"
MCLAG_UNIQUE_IP_VLAN  = "Vlan100"

MCLAG_PEER_LINK = "PortChannel12"
MCLAG_PEER_LINK2 = "PortChannel13"
MCLAG_INVALID_SRC_IP1  = "12::1111"
MCLAG_INVALID_SRC_IP2  = "224.1.1.1"
MCLAG_INVALID_PEER_IP1  = "12::1112"
MCLAG_INVALID_PEER_IP2  = "224.1.1.2"
MCLAG_INVALID_PEER_LINK1  = "Eth1/3"
MCLAG_INVALID_PEER_LINK2  = "Ethernet257"
MCLAG_INVALID_PEER_LINK3  = "PortChannel123456"
MCLAG_INVALID_PEER_LINK4  = "Lag111"
MCLAG_INVALID_PEER_LINK5  = "Ethernet123456789"
MCLAG_INVALID_KEEPALIVE_TIMER  = "11"
MCLAG_INVALID_SESSION_TIMEOUT = "31"
MCLAG_INVALID_KEEPALIVE_TIMER_LBOUND  = "0"
MCLAG_INVALID_KEEPALIVE_TIMER_UBOUND  = "61"
MCLAG_INVALID_SESSION_TMOUT_LBOUND  = "2"
MCLAG_INVALID_SESSION_TMOUT_UBOUND  = "4000"

MCLAG_VALID_PEER_LINK_PORT = "Ethernet0"
MCLAG_VALID_PEER_LINK_PORTCHANNEL = "PortChannel1000"

MCLAG_INVALID_MCLAG_MEMBER  = "Ethernet4"
MCLAG_INVALID_PORTCHANNEL1  = "portchannel" 
MCLAG_INVALID_PORTCHANNEL2  = "PortChannelabcd" 
MCLAG_INVALID_PORTCHANNEL3  = "PortChannel10000" 
MCLAG_INVALID_PORTCHANNEL4  = "PortChannel00111" 


MCLAG_UNIQUE_IP_INTF_INVALID1  = "Ethernet100"
MCLAG_UNIQUE_IP_INTF_INVALID2  = "Ethernet100"

class TestMclag(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def verify_mclag_domain_cfg(self, db, domain_id, src_ip="", peer_ip="", peer_link=""):
        mclag_entry = db.cfgdb.get_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID)
        if len(mclag_entry) == 0:
            return False

        if src_ip is not None:
            temp = mclag_entry.get("source_ip")
            if temp is not None and temp != src_ip:
                return False
        if peer_ip is not None:
            temp = mclag_entry.get("peer_ip")
            if temp is not None and temp != peer_ip:
                return False
        if peer_link is not None:
            temp = mclag_entry.get("peer_link")
            if temp is not None and temp != peer_link:
                return False
        return True

    def verify_mclag_interface(self, db, domain_id, intf_str):
        keys = db.cfgdb.get_entry('MCLAG_INTERFACE', (domain_id, intf_str))
        if len(keys) != 0:
            return True
        return False

    def test_add_mclag_with_invalid_src_ip(self):
        mclag.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid src
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_SRC_IP1, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_mclag_with_invalid_src_mcast_ip(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid src
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_SRC_IP2, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, RESERVED_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert "" in result.output 

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, INVALID_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, NOT_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_mclag_with_invalid_peer_ip(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid peer ip
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_INVALID_PEER_IP1, MCLAG_PEER_LINK], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "mclag invalid peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, RESERVED_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, INVALID_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, NOT_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    def test_add_mclag_with_invalid_peer_mcast_ip(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid peer ip mcast
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_INVALID_PEER_IP2, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer ip mcast test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_mclag_with_valid_peer_link(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with valid port peer link
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_VALID_PEER_LINK_PORT], obj=obj)
        assert result.exit_code == 0, "mclag valid peer link test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with valid portchannel peer link
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_VALID_PEER_LINK_PORTCHANNEL], obj=obj)
        assert result.exit_code == 0, "mclag valid peer link test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_mclag_with_invalid_peer_link(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid peer link
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK1], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer link test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK2], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer link test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK3], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer link test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK4], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer link test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK5], obj=obj)
        assert result.exit_code != 0, "mclag invalid peer link test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_invalid_mclag_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [0, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [5000, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)



    def test_add_mclag_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add valid mclag domain agai = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID2, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "test_mclag_domain_add_again with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        #verify config db for the mclag domain config
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

    def test_add_invalid_mclag_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [0, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [5000, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_add_mclag_domain_invalid_yang_validation(self):
        mclag.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK4], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value={"123": "xyz"}))
    def test_add_mclag_domain_invalid_yang_validation_override(self):
        mclag.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_INVALID_PEER_LINK4], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_add_mclag_domain(self):
        mclag.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        #verify config db for the mclag domain config
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add valid mclag domain again
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID2, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "test_mclag_domain_add_again with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        #verify config db for the mclag domain config
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

    def test_mclag_invalid_keepalive_timer(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}


        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # configure non multiple keepalive timer
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_KEEPALIVE_TIMER], obj=obj)
        assert result.exit_code != 0, "failed testing of invalid keepalive timer with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add invalid keepalive values
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_KEEPALIVE_TIMER_LBOUND], obj=obj)
        assert result.exit_code != 0, "mclag invalid keepalive failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add invalid keepalive values
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_KEEPALIVE_TIMER_UBOUND], obj=obj)
        assert result.exit_code != 0, "mclag creation keepalive failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_mclag_keepalive_timer(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}


        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # configure valid keepalive timer
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_KEEPALIVE_TIMER], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "failed test for setting valid keepalive timer with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        print(result.output)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # configure valid keepalive timer
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_KEEPALIVE_TIMER], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "failed test for setting valid keepalive timer with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        mclag_entry = db.cfgdb.get_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID)
        temp = mclag_entry.get("keepalive_interval")
        assert temp is not None, "session timeout not found"
        assert temp == MCLAG_KEEPALIVE_TIMER, "keepalive timer value not set"

        # configure non multiple session timeout
        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_SESSION_TIMEOUT], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "failed invalid session timeout setting case"

        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_SESSION_TMOUT_LBOUND], obj=obj)
        assert result.exit_code != 0, "mclag session timeout invalid failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_SESSION_TMOUT_UBOUND], obj=obj)
        assert result.exit_code != 0, "mclag session timeout invalid failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_mclag_session_timeout(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # configure valid session timeout
        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_SESSION_TIMEOUT], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "failed test for setting valid session timeout with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        mclag_entry = db.cfgdb.get_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID)
        temp = mclag_entry.get("session_timeout")
        assert temp is not None, "session timeout not found"
        assert temp == MCLAG_SESSION_TIMEOUT, "keepalive timer value not set"


    def test_mclag_add_mclag_member_to_nonexisting_domain(self):
        # This is required for the add command to fail; otherwise, it incorrectly passes
        mclag.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag_cfg = db.cfgdb.get_table('MCLAG_DOMAIN')
        keys = [ (k, v) for k, v in mclag_cfg if k == MCLAG_DOMAIN_ID2 ]
        assert len(keys) == 0, "found mclag domain which is not expected"

        # add mclag member to non existing domain
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID2, MCLAG_MEMBER_PO], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "testing of adding mclag member to nonexisting domain failed" 


    def test_mclag_add_invalid_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add invaid mclag member Ethernet instead of PortChannel
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_MCLAG_MEMBER], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "testing of adding invalid member failed" 

        # add invaid mclag member Ethernet instead of PortChannel
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL1], obj=obj)
        assert result.exit_code != 0, "mclag invalid member add case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add invaid mclag member Ethernet instead of PortChannel
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL2], obj=obj)
        assert result.exit_code != 0, "mclag invalid member add case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add invaid mclag member Ethernet instead of PortChannel
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL3], obj=obj)
        assert result.exit_code != 0, "mclag invalid member add case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # add invaid mclag member Ethernet instead of PortChannel
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL4], obj=obj)
        assert result.exit_code != 0, "mclag invalid member add case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_mclag_add_invalid_member_yang_validation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag.ADHOC_VALIDATION = False

        # add valid mclag domain
        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP, "peer_ip": MCLAG_PEER_IP, "peer_link": MCLAG_PEER_LINK})
        
        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', mock.Mock(return_value=True)):
            result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_MCLAG_MEMBER], obj=obj)
            print(result.exit_code)
            print(result.output)
            assert "Invalid ConfigDB. Error" in result.output 


    def test_mclag_add_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag.ADHOC_VALIDATION = True


        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add valid mclag member
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO], obj=obj)
        assert result.exit_code == 0, "failed adding valid mclag member with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == True, "mclag member not present"

        # add mclag member again
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "testing of adding mclag member again failed" 

        # delete mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0, "testing of delete of mclag domain failed" 
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == False, "mclag member not deleted"
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID) == False, "mclag domain not deleted"

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add valid mclag member
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO], obj=obj)
        assert result.exit_code == 0, "mclag member add with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == True, "mclag member not present"

        # add valid mclag member2
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2], obj=obj)
        assert result.exit_code == 0, "mclag member add with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2) == True, "mclag member not present"


        # del valid mclag member
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO], obj=obj)
        assert result.exit_code == 0, "mclag member deletion failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == False, "mclag member not deleted "

        # del mclag member
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_MCLAG_MEMBER], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "testing of deleting valid mclag member failed" 

        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL1], obj=obj)
        assert result.exit_code != 0, "mclag invalid member del case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL2], obj=obj)
        assert result.exit_code != 0, "mclag invalid member del case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL3], obj=obj)

        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_PORTCHANNEL4], obj=obj)
        assert result.exit_code != 0, "mclag invalid member del case failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_mclag_add__unique_ip_yang_validation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP})
        
        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', return_value=True):
            result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], [MCLAG_UNIQUE_IP_VLAN], obj=obj)
            assert "Invalid ConfigDB. Error" in result.output 


    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_mclag_del_unique_ip_yang_validation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP})
        
        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', return_value=True):
            result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["del"], [MCLAG_UNIQUE_IP_VLAN], obj=obj)
            assert "Failed to delete mclag unique IP" in result.output
    

    def test_mclag_add_unique_ip(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add mclag unique ip
        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], [MCLAG_UNIQUE_IP_VLAN], obj=obj)
        assert result.exit_code == 0, "mclag unique ip add with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        keys = db.cfgdb.get_keys('MCLAG_UNIQUE_IP')
        assert len(keys) != 0, "unique ip not conifgured"


        # add mclag unique ip for vlan interface which already has ip
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["111"], obj=db)
        assert result.exit_code == 0, "add vlan for unique ip failed {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"], ["Vlan111", "111.11.11.1/24"], obj=obj)        
        assert result.exit_code != 0, "ip config for unique ip vlan failed {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], ["Vlan111"], obj=obj)
        assert result.exit_code == 0, "unique ip config for vlan with ip address case failed {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        keys = db.cfgdb.get_keys('MCLAG_UNIQUE_IP')
        assert "Vlan111" in keys, "unique ip present  config shouldn't be allowed" 

        # delete mclag unique ip
        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["del"], [MCLAG_UNIQUE_IP_VLAN], obj=obj)
        assert result.exit_code == 0, "mclag unique ip delete case failed {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        keys = db.cfgdb.get_keys('MCLAG_UNIQUE_IP')
        assert MCLAG_UNIQUE_IP_VLAN not in keys, "unique ip not conifgured" 

    def test_mclag_add_unique_ip_non_default_vrf(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        assert result.exit_code == 0, "add vlan for unique ip failed {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        db.cfgdb.set_entry("VLAN_INTERFACE", "Vlan1001", {"vrf_name": "vrf-red"})

        # add mclag unique ip for non-default vrf
        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], ["Vlan1001"], obj=obj)
        assert result.exit_code != 0, "mclag unique ip add with non default vlan interface{}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        keys = db.cfgdb.get_keys('MCLAG_UNIQUE_IP')
        assert len(keys) == 0, "non default vrf unique ip goes through, config shouldn't be allowed" 

    def test_mclag_not_present_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID], obj=obj)
        assert result.exit_code == 0, "testing  non-existing domain deletion{}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # delete invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [0], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain delete test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        # delete invalid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [5000], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain delete test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)



    def test_add_unique_ip_for_nonexisting_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add unique_ip witout mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], [MCLAG_UNIQUE_IP_VLAN], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0, "testing of adding uniqueip nonexisting mclag domain ailed"

        result = runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], [MCLAG_UNIQUE_IP_INTF_INVALID1], obj=obj)
        assert result.exit_code != 0, "mclag invalid unique ip test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        runner.invoke(config.config.commands["mclag"].commands["unique-ip"].commands["add"], [MCLAG_UNIQUE_IP_INTF_INVALID2], obj=obj)
        assert result.exit_code != 0, "mclag invalid unique ip test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

    def test_add_mclag_with_invalid_domain_id(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag with invalid domain_id
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_INVALID_DOMAIN_ID1, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_INVALID_DOMAIN_ID2, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code != 0, "mclag invalid src ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
    
    def test_del_mclag_with_invalid_domain_id(self):
        mclag.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        with mock.patch('config.main.ConfigDBConnector.get_entry', return_value=None):
            # del mclag nonexistent domain_id
            result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_NONEXISTENT_DOMAIN_ID], obj=obj)
            assert result.exit_code != 0, "mclag invalid domain id test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # del mclag with invalid domain_id
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_INVALID_DOMAIN_ID1], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain id test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_INVALID_DOMAIN_ID2], obj=obj)
        assert result.exit_code != 0, "mclag invalid domain id test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID3], obj=obj)
        print(result.output)
        assert result.exit_code == 0, "mclag invalid domain id test case with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    def test_modify_mclag_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add mclag domain entry in db
        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP})
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag add domain peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"
        print(result.output)

        # modify mclag config
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK2], obj=obj)
        assert result.exit_code == 0, "test_mclag_domain_add_again with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK2) == True, "mclag config not modified"


    def test_add_mclag_domain_no_peer_link(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}


        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, ""], obj=obj)
        assert result.exit_code != 0, "mclag add domain peer ip test caase with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP) == False, "mclag config not found"


    def test_del_mclag_domain_with_members(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK) == True, "mclag config not found"

        # add valid mclag member
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO], obj=obj)
        assert result.exit_code == 0, "mclag member add with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == True, "mclag member not present"

        # add valid mclag member2
        result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2], obj=obj)
        assert result.exit_code == 0, "mclag member add with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2) == True, "mclag member not present"

        # delete mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID], obj=obj)
        assert result.exit_code == 0, "testing  non-existing domain deletion{}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2) == False, "mclag member not deleted"
        assert self.verify_mclag_interface(db, MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO) == False, "mclag member not deleted"
        assert self.verify_mclag_domain_cfg(db, MCLAG_DOMAIN_ID) == False, "mclag domain not present"

   
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_del_mclag_domain_with_members_invalid_yang_validation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag.ADHOC_VALIDATION = False

        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP, "peer_ip": MCLAG_PEER_IP, "peer_link": MCLAG_PEER_LINK})
        db.cfgdb.set_entry('MCLAG_INTERFACE', (MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO), {'if_type':"PortChannel"} )
        db.cfgdb.set_entry('MCLAG_INTERFACE', (MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2), {'if_type':"PortChannel"} )
        
        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', return_value=True):
            result = runner.invoke(config.config.commands["mclag"].commands["member"].commands["del"], [MCLAG_DOMAIN_ID, MCLAG_MEMBER_PO2], obj=obj)
            assert "Failed to delete mclag member" in result.output

        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', return_value=True):
            result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID], obj=obj)
            assert "Invalid ConfigDB. Error" in result.output


    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_del_mclag_domain_invalid_yang_validation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag.ADHOC_VALIDATION = False

        db.cfgdb.set_entry("MCLAG_DOMAIN", MCLAG_DOMAIN_ID, {"source_ip": MCLAG_SRC_IP, "peer_ip": MCLAG_PEER_IP, "peer_link": MCLAG_PEER_LINK})
        with mock.patch('validated_config_db_connector.device_info.is_yang_config_validation_enabled', return_value=True):
            result = runner.invoke(config.config.commands["mclag"].commands["del"], [MCLAG_DOMAIN_ID], obj=obj)
            assert "Invalid ConfigDB. Error" in result.output
    

    def test_mclag_keepalive_for_non_existent_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        mclag.ADHOC_VALIDATION = True

        # configure keepalive timer for non-existing domain
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_INVALID_KEEPALIVE_TIMER], obj=obj)
        assert result.exit_code != 0, "failed testing of keepalive timer for nonexisting domain {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    def test_mclag_keepalive_config_with_nondefault_sess_tmout(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add valid mclag domain
        result = runner.invoke(config.config.commands["mclag"].commands["add"], [MCLAG_DOMAIN_ID, MCLAG_SRC_IP, MCLAG_PEER_IP, MCLAG_PEER_LINK], obj=obj)
        assert result.exit_code == 0, "mclag creation failed with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        #configure valid session timeout
        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_SESSION_TIMEOUT], obj=obj)
        assert result.exit_code == 0, "failed test for setting valid keepalive timer with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)

        # configure valid keepalive timer
        result = runner.invoke(config.config.commands["mclag"].commands["keepalive-interval"], [MCLAG_DOMAIN_ID, MCLAG_KEEPALIVE_TIMER], obj=obj)
        assert result.exit_code == 0, "failed test for setting valid keepalive timer with code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    def test_mclag_session_tmout_for_nonexistent_domain(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["mclag"].commands["session-timeout"], [MCLAG_DOMAIN_ID, MCLAG_SESSION_TIMEOUT], obj=obj)
        assert result.exit_code != 0, "failed test for session timeout with non existent dmain code {}:{} Output:{}".format(type(result.exit_code), result.exit_code, result.output)


    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
