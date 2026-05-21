from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from dump.match_helper import fetch_port_oid
from .executor import Executor


class Port(Executor):
    """
    Debug Dump Plugin for PORT Module
    """
    ARG_NAME = "port_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_ports = ret["keys"]
        return [key.split("|")[-1] for key in all_ports]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        port_name = params[Port.ARG_NAME]
        self.ns = params["namespace"]
        self.init_port_config_info(port_name)
        self.init_port_appl_info(port_name)
        port_asic_obj = self.init_asic_hostif_info(port_name)
        self.init_asic_port_info(port_asic_obj)
        self.init_state_port_info(port_name)
        return self.ret_temp

    def init_port_config_info(self, port_name):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern=port_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_port_appl_info(self, port_name):
        req = MatchRequest(db="APPL_DB", table="PORT_TABLE", key_pattern=port_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_state_port_info(self, port_name):
        req = MatchRequest(db="STATE_DB", table="PORT_TABLE", key_pattern=port_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_asic_hostif_info(self, port_name):
        req, asic_port_obj_id, ret = fetch_port_oid(self.match_engine, port_name, self.ns)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
        return asic_port_obj_id

    def init_asic_port_info(self, asic_port_obj_id):
        if not asic_port_obj_id:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT")
            return None
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_PORT", key_pattern=asic_port_obj_id, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
