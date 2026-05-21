from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from .executor import Executor


class Evpn(Executor):
    """
    Debug Dump Plugin for EVPN Module
    """
    ARG_NAME = "Remote VNI"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ns = ''
        self.remote_ip = ''
        self.vlan = ''
        self.tunnel_obj = ''
        self.encap_mappers = []
        self.decap_mappers = []
        self.asic_tunnel_cache = {}
        self.asic_tunnel_term_cache = {}
        self.asic_tunnel_map_cache = {}

    def get_all_args(self, ns=""):
        req = MatchRequest(db="APPL_DB", table="VXLAN_REMOTE_VNI_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        evpns = ret["keys"]
        return [key.split(":", 1)[-1] for key in evpns]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        evpn_name = params[Evpn.ARG_NAME]
        self.remote_ip = evpn_name.split(':')[-1]
        self.remote_vlan = evpn_name.split(':')[0]
        self.ns = params["namespace"]
        self.init_evpn_appl_info(evpn_name)
        self.init_asic_evpn_info()
        self.init_asic_evpn_map_info()
        self.init_asic_evpn_term_info()
        self.init_state_evpn_info(evpn_name)
        return self.ret_temp

    def init_evpn_appl_info(self, evpn_name):
        req = MatchRequest(db="APPL_DB", table="VXLAN_REMOTE_VNI_TABLE", key_pattern=evpn_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_state_evpn_info(self, evpn_name):
        state_key = "EVPN_" + self.remote_ip
        req = MatchRequest(db="STATE_DB", table="VXLAN_TUNNEL_TABLE", key_pattern=state_key, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_evpn_info(self):
        if not self.remote_ip:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL")
            return None
        if self.remote_ip in self.asic_tunnel_cache:
            ret = self.asic_tunnel_cache[self.remote_ip]
        else:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL",
                               field="SAI_TUNNEL_ATTR_ENCAP_DST_IP", value=self.remote_ip, ns=self.ns,
                               return_fields=["SAI_TUNNEL_ATTR_TYPE", "SAI_TUNNEL_ATTR_ENCAP_MAPPERS",
                               "SAI_TUNNEL_ATTR_DECAP_MAPPERS"])
            ret = self.match_engine.fetch(req)
            self.asic_tunnel_cache[self.remote_ip] = ret
        ret["keys"] = [x for x in ret["keys"] if ret["return_values"][x]["SAI_TUNNEL_ATTR_TYPE"] == "SAI_TUNNEL_TYPE_VXLAN"]
        if ret["keys"]:
            asic_key = ret["keys"][0]
            self.tunnel_obj = asic_key.replace("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:", "")
            if ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_ENCAP_MAPPERS"]:
                self.encap_mappers = ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_ENCAP_MAPPERS"].split(':', 1)[-1].split(',')
            if ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_DECAP_MAPPERS"]:
                self.decap_mappers = ret["return_values"][asic_key]["SAI_TUNNEL_ATTR_DECAP_MAPPERS"].split(':', 1)[-1].split(',')
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_evpn_term_info(self):
        if not self.tunnel_obj:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY")
            return None
        if self.tunnel_obj in self.asic_tunnel_term_cache:
            ret = self.asic_tunnel_term_cache[self.tunnel_obj]
        else:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY",
                               field="SAI_TUNNEL_TERM_TABLE_ENTRY_ATTR_ACTION_TUNNEL_ID", value=self.tunnel_obj, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.asic_tunnel_term_cache[self.tunnel_obj] = ret
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_evpn_map_info(self):
        if not (self.encap_mappers or self.decap_mappers):
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
            return None
        for key in self.encap_mappers:
            if key in self.asic_tunnel_map_cache:
                ret = self.asic_tunnel_map_cache[key]
            else:
                req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP",
                                   key_pattern=key, ns=self.ns)
                ret = self.match_engine.fetch(req)
                self.asic_tunnel_map_cache[key] = ret
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        for key in self.decap_mappers:
            if key in self.asic_tunnel_map_cache:
                ret = self.asic_tunnel_map_cache[key]
            else:
                req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP",
                                   key_pattern=key, ns=self.ns)
                ret = self.match_engine.fetch(req)
                self.asic_tunnel_map_cache[key] = ret
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
