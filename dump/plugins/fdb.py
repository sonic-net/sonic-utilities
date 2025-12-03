from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from .executor import Executor


class Fdb(Executor):
    """
    Debug Dump Plugin for FDB Module
    """
    ARG_NAME = "Vlan:fdb_entry"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)

    def get_all_args(self, ns=""):
        req = MatchRequest(db="STATE_DB", table="FDB_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        fdb_entries = ret["keys"]
        return [key.split("|")[-1] for key in fdb_entries]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        fdb_entry = params[Fdb.ARG_NAME]
        self.ns = params["namespace"]
        self.init_fdb_appl_info(fdb_entry)
        self.init_asic_fdb_info(fdb_entry)
        self.init_state_fdb_info(fdb_entry)
        return self.ret_temp

    def init_state_fdb_info(self, fdb_name):
        req = MatchRequest(db="STATE_DB", table="FDB_TABLE", key_pattern=fdb_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_fdb_appl_info(self, fdb_name):
        req = MatchRequest(db="APPL_DB", table="FDB_TABLE", key_pattern=fdb_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)
        req = MatchRequest(db="APPL_DB", table="VXLAN_FDB_TABLE", key_pattern=fdb_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)
        req = MatchRequest(db="APPL_DB", table="MCLAG_FDB_TABLE", key_pattern=fdb_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)

    def init_asic_fdb_info(self, fdb_name):
        # One colon between Vlan and MAC and 5 colons in mac address are expected in key
        if fdb_name.count(':') != 6:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            return

        key_split = fdb_name.split(":",1)
        vlan_name = key_split[0]
        mac = key_split[1]
        if vlan_name[0:4] != "Vlan" or not vlan_name[4:].isnumeric():
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            return

        vlan_num = int(vlan_name[4:])
        # Find the table named "ASIC_STATE:SAI_OBJECT_TYPE_VLAN:*" in which SAI_VLAN_AT'TR_VLAN_ID = vlan_num
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN", key_pattern="*", field="SAI_VLAN_ATTR_VLAN_ID", 
                           value=str(vlan_num), ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) == 1:
            vlan_obj = ret["keys"][0].split(":",2)[-1]
        else:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            return

        # ASIC_DB FDB format is bvid:vlan_obj + mac:mac_address + switch id which is wildcard here
        fdb_key = '{"bvid":"' + vlan_obj + '","mac":"' + mac.upper() + '"*}'
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY", key_pattern=fdb_key, 
                           return_fields=["SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        bridge_port_id = ""
        if not ret["error"] and len(ret["keys"]) != 0:
            asic_fdb_key = ret["keys"][0]
            if asic_fdb_key in ret["return_values"] and "SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID" in ret["return_values"][asic_fdb_key]:
                bridge_port_id = ret["return_values"][asic_fdb_key]["SAI_FDB_ENTRY_ATTR_BRIDGE_PORT_ID"]
            else:
                self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            
        if bridge_port_id:
            bridge_port_req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT",
                                           key_pattern = bridge_port_id, ns = self.ns)
            bridge_ret = self.match_engine.fetch(bridge_port_req)
            if not bridge_ret["error"] and len(bridge_ret["keys"]) != 0:
                self.ret_temp[bridge_port_req.db]["keys"].append(bridge_ret["keys"][0])
            else:
                self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            
            
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
