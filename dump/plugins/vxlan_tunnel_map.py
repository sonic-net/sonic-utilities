from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from .executor import Executor


class Vxlan_tunnel_map(Executor):
    """
    Debug Dump Plugin for Vxlan Tunnel Map Module
    """
    ARG_NAME = "vxlan_tunnel_map_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ns = ''
        self.vlan = ''
        self.vni = ''
        self.tunnel_map_obj = ''
        self.encap_mappers = []
        self.decap_mappers = []

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="VXLAN_TUNNEL_MAP", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        vxlan_tunnel_maps = ret["keys"]
        return [key.split("|", 1)[-1] for key in vxlan_tunnel_maps]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        vxlan_tunnel_map_name = params[Vxlan_tunnel_map.ARG_NAME]
        self.ns = params["namespace"]
        self.init_vxlan_tunnel_map_config_info(vxlan_tunnel_map_name)
        self.init_vxlan_tunnel_map_appl_info(vxlan_tunnel_map_name)
        self.init_asic_vxlan_tunnel_map_entry_info()
        self.init_asic_vxlan_tunnel_map_info()
        return self.ret_temp

    def init_vxlan_tunnel_map_config_info(self, vxlan_tunnel_map_name):
        req = MatchRequest(db="CONFIG_DB", table="VXLAN_TUNNEL_MAP", key_pattern=vxlan_tunnel_map_name, ns=self.ns,
                           return_fields=["vlan", "vni"])
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            cfg_key = ret["keys"][0]
            self.vlan = ret["return_values"][cfg_key]["vlan"].replace("Vlan", "")
            self.vni = ret["return_values"][cfg_key]["vni"]
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_vxlan_tunnel_map_appl_info(self, vxlan_tunnel_map_name):
        app_vxlan_tunnel_map_name = vxlan_tunnel_map_name.replace('|', ':')
        req = MatchRequest(db="APPL_DB", table="VXLAN_TUNNEL_MAP_TABLE", key_pattern=app_vxlan_tunnel_map_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vxlan_tunnel_map_entry_info(self):
        if not self.vlan:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY")
            return None
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY",
                           field="SAI_TUNNEL_MAP_ENTRY_ATTR_VLAN_ID_VALUE", value=self.vlan, ns=self.ns,
                           return_fields=["SAI_TUNNEL_MAP_ENTRY_ATTR_TUNNEL_MAP_TYPE",
                                          "SAI_TUNNEL_MAP_ENTRY_ATTR_VNI_ID_KEY",
                                          "SAI_TUNNEL_MAP_ENTRY_ATTR_TUNNEL_MAP"])
        ret = self.match_engine.fetch(req)
        ret["keys"] = [x for x in ret["keys"] if ret["return_values"][x]["SAI_TUNNEL_MAP_ENTRY_ATTR_TUNNEL_MAP_TYPE"] == "SAI_TUNNEL_MAP_TYPE_VNI_TO_VLAN_ID"]
        ret["keys"] = [x for x in ret["keys"] if ret["return_values"][x]["SAI_TUNNEL_MAP_ENTRY_ATTR_VNI_ID_KEY"] == self.vni]
        if ret["keys"]:
            self.tunnel_map_obj = ret["return_values"][ret["keys"][0]]["SAI_TUNNEL_MAP_ENTRY_ATTR_TUNNEL_MAP"]
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vxlan_tunnel_map_info(self):
        if not self.tunnel_map_obj:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
            return None
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP",
                           key_pattern=self.tunnel_map_obj, value=self.vlan, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
