from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from .executor import Executor


class Vxlan_tunnel(Executor):
    """
    Debug Dump Plugin for Vxlan Tunnel Module
    """
    ARG_NAME = "vxlan_tunnel_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ns = ''
        self.src_ip = ''
        self.dst_ip = ''
        self.tunnel_obj = ''
        self.encap_mappers = []
        self.decap_mappers = []

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="VXLAN_TUNNEL", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        vxlan_tunnels = ret["keys"]
        return [key.split("|")[-1] for key in vxlan_tunnels]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        vxlan_tunnel_name = params[Vxlan_tunnel.ARG_NAME]
        self.ns = params["namespace"]
        self.init_vxlan_tunnel_config_info(vxlan_tunnel_name)
        self.init_vxlan_tunnel_appl_info(vxlan_tunnel_name)
        self.init_asic_vxlan_tunnel_info()
        self.init_asic_vxlan_tunnel_map_info()
        self.init_asic_vxlan_tunnel_term_info()
        self.init_state_vxlan_tunnel_info(vxlan_tunnel_name)
        return self.ret_temp

    def init_vxlan_tunnel_config_info(self, vxlan_tunnel_name):
        req = MatchRequest(db="CONFIG_DB", table="VXLAN_TUNNEL", key_pattern=vxlan_tunnel_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_vxlan_tunnel_appl_info(self, vxlan_tunnel_name):
        req = MatchRequest(db="APPL_DB", table="VXLAN_TUNNEL_TABLE", key_pattern=vxlan_tunnel_name, ns=self.ns,
                           return_fields=["src_ip", "dst_ip"])
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            app_key = ret["keys"][0]
            self.src_ip = ret["return_values"][app_key]["src_ip"]
            self.dst_ip = ret["return_values"][app_key]["dst_ip"]
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_state_vxlan_tunnel_info(self, vxlan_tunnel_name):
        req = MatchRequest(db="STATE_DB", table="VXLAN_TUNNEL_TABLE", key_pattern=vxlan_tunnel_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vxlan_tunnel_info(self):
        if not self.src_ip:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL")
            return None
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL", field="SAI_TUNNEL_ATTR_ENCAP_SRC_IP", value=self.src_ip, ns=self.ns,
                           return_fields=["SAI_TUNNEL_ATTR_TYPE", "SAI_TUNNEL_ATTR_ENCAP_DST_IP",
                                          "SAI_TUNNEL_ATTR_ENCAP_MAPPERS", "SAI_TUNNEL_ATTR_DECAP_MAPPERS"])
        ret = self.match_engine.fetch(req)
        ret["keys"] = [x for x in ret["keys"] if ret["return_values"][x]["SAI_TUNNEL_ATTR_TYPE"] == "SAI_TUNNEL_TYPE_VXLAN"]
        ret["keys"] = [x for x in ret["keys"] if not self.dst_ip and ret["return_values"][x]["SAI_TUNNEL_ATTR_ENCAP_DST_IP"] == "" or
                       ret["return_values"][x]["SAI_TUNNEL_ATTR_ENCAP_DST_IP"] == self.dst_ip]
        if ret["keys"]:
            asic_key = ret["keys"][0]
            self.tunnel_obj = asic_key.replace("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:", "")
            if ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_ENCAP_MAPPERS"]:
                self.encap_mappers = ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_ENCAP_MAPPERS"].split(':', 1)[-1].split(',')
            if ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_DECAP_MAPPERS"]:
                self.decap_mappers = ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_DECAP_MAPPERS"].split(':', 1)[-1].split(',')
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vxlan_tunnel_term_info(self):
        if not self.tunnel_obj:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY")
            return None
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY",
                           field="SAI_TUNNEL_TERM_TABLE_ENTRY_ATTR_ACTION_TUNNEL_ID", value=self.tunnel_obj, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_vxlan_tunnel_map_info(self):
        if not (self.encap_mappers or self.decap_mappers):
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
            return None
        for key in self.encap_mappers:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP",
                               key_pattern=key, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        for key in self.decap_mappers:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP",
                               key_pattern=key, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
