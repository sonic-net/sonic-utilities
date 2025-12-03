from .executor import Executor
from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from dump.match_helper import fetch_vlan_oid

class Vlan(Executor):
    
    ARG_NAME = "vlan_name"
    
    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ret_temp = {}
        self.ns = ''
          
    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="VLAN", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_vlans = ret["keys"]
        return [key.split("|")[-1] for key in all_vlans]
            
    def execute(self, params_dict):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        vlan_name = params_dict[Vlan.ARG_NAME]
        self.ns = params_dict["namespace"]
        self.init_vlan_config_info(vlan_name)
        self.init_vlan_appl_info(vlan_name)
        self.init_state_vlan_info(vlan_name)
        self.init_asic_vlan_info(vlan_name)
        return self.ret_temp
    
    def init_vlan_config_info(self, vlan_name):
        req = MatchRequest(db="CONFIG_DB", table="VLAN", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
    
    def init_vlan_appl_info(self, vlan_name):
        req = MatchRequest(db="APPL_DB", table="VLAN_TABLE", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        
    def init_state_vlan_info(self, vlan_name):
        req = MatchRequest(db="STATE_DB", table="VLAN_TABLE", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vlan_info(self, vlan_name):
        req, _, ret = fetch_vlan_oid(self.match_engine, vlan_name, self.ns)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
