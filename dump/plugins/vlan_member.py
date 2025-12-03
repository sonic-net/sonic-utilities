from .executor import Executor
from dump.match_infra import MatchRequest
from dump.helper import create_template_dict

class Vlan_Member(Executor):

    ARG_NAME = "vlan_member_name"
    
    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ret_temp = {}
        self.ns = ''
          
    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="VLAN_MEMBER", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_vlans = ret["keys"]
        return [key.split("|",1)[-1] for key in all_vlans]
            
    def execute(self, params_dict):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        vlan_member_name = params_dict[Vlan_Member.ARG_NAME]
        vlan_member_name_list = vlan_member_name.split('|', 1)
        if len(vlan_member_name_list) < 2:
            self.ret_temp["CONFIG_DB"]["tables_not_found"].append("VLAN_MEMBER")
            self.ret_temp["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
            self.ret_temp["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
            return self.ret_temp
        vlan_name = vlan_member_name_list[0]
        member_name = vlan_member_name_list[1]
        self.ns = params_dict["namespace"]
        self.init_vlan_member_config_info(vlan_name, member_name)
        self.init_vlan_member_appl_info(vlan_name, member_name)
        self.init_state_vlan_member_info(vlan_name, member_name)
        self.init_asic_vlan_member_info(vlan_name, member_name)
        return self.ret_temp
    
    def init_vlan_member_config_info(self, vlan_name, member_name):
        req = MatchRequest(db="CONFIG_DB", table="VLAN_MEMBER", key_pattern=vlan_name+'|'+member_name+"*", ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            for mem in ret["keys"]:
                self.ret_temp[req.db]["keys"].append(mem)
        else:
            self.ret_temp[req.db]["tables_not_found"].append(req.table)
    
    def init_vlan_member_appl_info(self, vlan_name, member_name):
        req = MatchRequest(db="APPL_DB", table="VLAN_MEMBER_TABLE", key_pattern=vlan_name+':'+member_name+"*", ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        
    def init_state_vlan_member_info(self, vlan_name, member_name):
        req = MatchRequest(db="STATE_DB", table="VLAN_MEMBER_TABLE", key_pattern=vlan_name+'|'+member_name+"*", ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vlan_member_info(self, vlan_name, member_name):
        
        bridge_ret = {}
        member_ret = {}
        
        # Convert 'Vlanxxx' to 'xxx'
        if vlan_name[0:4] != "Vlan" or not vlan_name[4:].isnumeric():
            self.ret_temp["ASIC_DB"]["tables_not_found"] =["ASIC_STATE:SAI_OBJECT_TYPE_VLAN"]
            return
        vlan_num = int(vlan_name[4:])
        
        # Find the table named "ASIC_STATE:SAI_OBJECT_TYPE_VLAN:*" in which SAI_VLAN_ATTR_VLAN_ID = vlan_num and store OID part of table name
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN", key_pattern="*", field="SAI_VLAN_ATTR_VLAN_ID", 
                           value=str(vlan_num), ns=self.ns)
        vlan_ret = self.match_engine.fetch(req)
        # Example contents of vlan_ret:
        # {'error': '', 'keys': ['ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:0x26000000000618'], 'return_values': {}}
        if not vlan_ret["error"] and len(vlan_ret["keys"]) != 0:
            vlan_oid=vlan_ret['keys'][0].split(':',2)[2]
        else:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
            return 
        
        # Find OID of vlan member - find a table named ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:* whose SAI_HOSTIF_ATTR_NAME is the member name,
        # and read the member OID from SAI_HOSTIF_ATTR_OBJ_ID in that table
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", key_pattern="*", field="SAI_HOSTIF_ATTR_NAME",
                           value=member_name, return_fields=["SAI_HOSTIF_ATTR_OBJ_ID"], ns=self.ns)
        hostif_ret = self.match_engine.fetch(req)
        # Example contents of hostif_ret:
        # {'error': '', 'keys': ['ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd0000000003c1'], 
        #  'return_values': {'ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd0000000003c1': {'SAI_HOSTIF_ATTR_OBJ_ID': 'oid:0x10000000002f6'}}}
        member_oid = ""
        if not hostif_ret["error"] and len(hostif_ret["keys"]) != 0:
            sai_hostif_obj_key = hostif_ret["keys"][-1]
            if sai_hostif_obj_key in hostif_ret["return_values"] and "SAI_HOSTIF_ATTR_OBJ_ID" in hostif_ret["return_values"][sai_hostif_obj_key]:
                member_oid = hostif_ret["return_values"][sai_hostif_obj_key]["SAI_HOSTIF_ATTR_OBJ_ID"]

        # Find the table named "ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:*" in which field SAI_BRIDGE_PORT_ATTR_PORT_ID = vlan member OID
        if member_oid:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT", key_pattern="*", 
                               field="SAI_BRIDGE_PORT_ATTR_PORT_ID", value=member_oid, ns=self.ns)
            bridge_ret = self.match_engine.fetch(req)
            # Example contents of bridge_ret:
            # {'error': '', 'keys': ['ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a00000000061b'], 'return_values': {}}
            
        # Find the tables named "ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:*" in which field SAI_VLAN_MEMBER_ATTR_BRIDGE_PORT_ID = SAI object bridge port OID.
        # There should be one of these for each vlan in which the port is a member.
        if bridge_ret and not bridge_ret["error"] and len(bridge_ret["keys"]) != 0:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER", key_pattern="*", 
                               field="SAI_VLAN_MEMBER_ATTR_BRIDGE_PORT_ID", value=bridge_ret['keys'][0].split(':',2)[2], ns=self.ns)
            member_ret = self.match_engine.fetch(req)
            # Example contents of member_ret:
            # {'error': '', 'keys': ['ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x2700000000061c', 'ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x2700000000061d'], 'return_values': {}}

        # Since this function is invoked for a given vlan and member, we expect that member_ret contains exactly one entry describing the port's
        # membership in that vlan if it is a member, and zero if it is not.  Only output the vlan member and bridge port tables
        # if this port is a member of this vlan.
        if member_ret and not member_ret["error"] and len(member_ret["keys"]) != 0:
            is_member = False
            for member_with_vlan in member_ret["keys"]:
                req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER", key_pattern=member_with_vlan.split(":",2)[2], 
                                   field="SAI_VLAN_MEMBER_ATTR_VLAN_ID", value=vlan_oid, ns=self.ns)
                vlan_bridge_ret = self.match_engine.fetch(req)
                # Example contents of vlan_bridge_ret:
                # {'error': '', 'keys': ['ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x2700000000061c'], 'return_values': {}}
                if not vlan_bridge_ret["error"] and len(vlan_bridge_ret["keys"]) != 0:
                    self.ret_temp[req.db]["keys"].append(vlan_bridge_ret["keys"][0])
                    self.ret_temp[req.db]["keys"].append(bridge_ret["keys"][0])
                    is_member = True
            if not is_member:
                self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
                self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        else:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
