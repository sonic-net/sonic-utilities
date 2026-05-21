import json
import os
from deepdiff import DeepDiff
from utilities_common.db import Db
import importlib
import tempfile
from unittest import mock
from .mock_tables import dbconnector
fast_reboot_dump = importlib.import_module("scripts.fast-reboot-dump")

class TestFastRebootDump(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

        test_db_dumps_directory = os.getcwd() + '/tests/fast_reboot_dump_dbs'
        asic_db_object = Db()
        app_db_object = Db()
        asic_db = asic_db_object.db
        app_db = app_db_object.db
        populate_db(asic_db, test_db_dumps_directory, 'ASIC_DB.json')
        populate_db(app_db, test_db_dumps_directory, 'APPL_DB.json')

        cls.asic_db = asic_db
        cls.app_db = app_db

    #Test fast-reboot-dump script to generate all required objects when there is a VLAN interface with a PortChannel member.
    def test_generate_fdb_entries_vlan_portchannel_member(self):
        vlan_ifaces = ['Vlan2']

        fdb_entries, all_available_macs, map_mac_ip_per_vlan = fast_reboot_dump.generate_fdb_entries_logic(self.asic_db, self.app_db, vlan_ifaces)

        expectd_fdb_entries = [{'FDB_TABLE:Vlan2:52-54-00-5D-FC-B7': {'type': 'dynamic', 'port': 'PortChannel0001'}, 'OP': 'SET'}]
        assert not DeepDiff(fdb_entries, expectd_fdb_entries, ignore_order=True)

        expectd_all_available_macs = {('Vlan2', '52:54:00:5d:fc:b7')}
        assert not DeepDiff(all_available_macs, expectd_all_available_macs, ignore_order=True)

        expectd_map_mac_ip_per_vlan = {'Vlan2': {'52:54:00:5d:fc:b7': 'PortChannel0001'}}
        assert not DeepDiff(map_mac_ip_per_vlan, expectd_map_mac_ip_per_vlan, ignore_order=True)

    @mock.patch.object(fast_reboot_dump.syslog, "syslog", return_value=None)
    @mock.patch.object(fast_reboot_dump, "SonicV2Connector")
    def test_generate_neighbor_entries(self, mock_sonicv2, _mock_syslog):
        conn = dbconnector.SonicV2Connector()
        mock_sonicv2.return_value = conn

        conn.connect(conn.APPL_DB)

        # Included: (Vlan2, mac) is present in all_available_macs
        key_included = 'NEIGH_TABLE:Vlan2:192.168.0.2'
        conn.set(conn.APPL_DB, key_included, 'neigh', '52:54:00:5D:FC:B7')

        # Excluded: exists in DB, but (Vlan3, mac) is NOT present in all_available_macs
        # so generate_neighbor_entries() skip it
        key_excluded = 'NEIGH_TABLE:Vlan3:192.168.0.3'
        conn.set(conn.APPL_DB, key_excluded, 'neigh', 'aa:bb:cc:dd:ee:ff')

        all_available_macs = {('Vlan2', '52:54:00:5d:fc:b7')}

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, 'arp.json')

            neighbor_entries = fast_reboot_dump.generate_neighbor_entries(
                outfile, all_available_macs
            )

            assert neighbor_entries == [
                ('Vlan2', '52:54:00:5d:fc:b7', '192.168.0.2')
            ]

            with open(outfile) as fp:
                data = json.load(fp)

        assert len(data) == 1
        obj = data[0]
        assert key_included in obj
        assert obj[key_included]['neigh'] == '52:54:00:5D:FC:B7'
        assert obj['OP'] == 'SET'
        assert not any(key_excluded in item for item in data)

    @mock.patch.object(fast_reboot_dump, "SonicV2Connector")
    def test_generate_default_route_entries(self, mock_sonicv2):
        conn = dbconnector.SonicV2Connector()
        mock_sonicv2.return_value = conn

        conn.connect(conn.APPL_DB)
        conn.set(conn.APPL_DB, 'ROUTE_TABLE:0.0.0.0/0', 'nexthop', '10.0.0.1')
        conn.set(conn.APPL_DB, 'ROUTE_TABLE:0.0.0.0/0', 'ifname', 'Ethernet0')
        conn.set(conn.APPL_DB, 'ROUTE_TABLE::/0', 'nexthop', '2001:db8::1')
        conn.set(conn.APPL_DB, 'ROUTE_TABLE::/0', 'ifname', 'Ethernet0')

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, 'default_routes.json')
            fast_reboot_dump.generate_default_route_entries(outfile)

            with open(outfile) as fp:
                data = json.load(fp)

        ipv4_obj = next(item for item in data if 'ROUTE_TABLE:0.0.0.0/0' in item)
        assert ipv4_obj['ROUTE_TABLE:0.0.0.0/0']['nexthop'] == '10.0.0.1'
        assert ipv4_obj['ROUTE_TABLE:0.0.0.0/0']['ifname'] == 'Ethernet0'
        assert ipv4_obj['OP'] == 'SET'

        ipv6_candidates = [item for item in data if 'ROUTE_TABLE::/0' in item]
        if ipv6_candidates:
            ipv6_obj = ipv6_candidates[0]
            assert ipv6_obj['ROUTE_TABLE::/0']['nexthop'] == '2001:db8::1'
            assert ipv6_obj['ROUTE_TABLE::/0']['ifname'] == 'Ethernet0'

    @mock.patch.object(fast_reboot_dump, "SonicV2Connector")
    def test_generate_media_config(self, mock_sonicv2):
        conn = dbconnector.SonicV2Connector()
        mock_sonicv2.return_value = conn

        conn.connect(conn.APPL_DB)

        key = 'PORT_TABLE:Ethernet0'
        conn.set(conn.APPL_DB, key, 'preemphasis', '1')
        conn.set(conn.APPL_DB, key, 'idriver', '2')
        conn.set(conn.APPL_DB, key, 'speed', '100000')

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, 'media_config.json')
            media_config = fast_reboot_dump.generate_media_config(outfile)

            with open(outfile) as fp:
                file_data = json.load(fp)

        entry = next(item for item in media_config if key in item)
        attrs = entry[key]
        assert attrs == {
            'preemphasis': '1',
            'idriver': '2'
        }
        assert 'speed' not in attrs

        file_entry = next(item for item in file_data if key in item)
        assert file_entry[key] == attrs
        assert entry['OP'] == 'SET'
        assert file_entry['OP'] == 'SET'

    @mock.patch.object(fast_reboot_dump, "get_vlan_ifaces", return_value=[])
    @mock.patch.object(fast_reboot_dump, "SonicV2Connector")
    def test_generate_fdb_entries(self, mock_sonicv2, _mock_get_vlan_ifaces):
        conn = dbconnector.SonicV2Connector()
        mock_sonicv2.return_value = conn

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, 'fdb.json')

            all_available_macs, map_mac_ip_per_vlan = fast_reboot_dump.generate_fdb_entries(outfile)

            assert all_available_macs == set()
            assert map_mac_ip_per_vlan == {}

            with open(outfile) as fp:
                data = json.load(fp)

            assert data == []


    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

def populate_db(dbconn, test_db_dumps_directory, db_dump_filename):
    db = getattr(dbconn, db_dump_filename.replace('.json',''))
    with open(test_db_dumps_directory + '/' + db_dump_filename) as DB:
        db_dump = json.load(DB)
        for table, fields in db_dump.items():
            for key, value in fields['value'].items():
                dbconn.set(db, table, key, value)
