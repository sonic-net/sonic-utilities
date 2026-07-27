from dump.helper import create_template_dict
from dump.match_infra import MatchRequest
from swsscommon.swsscommon import SonicDBConfig

from dump.match_helper import fetch_acl_counter_oid
from .executor import Executor


CFG_DB_SEPARATOR = SonicDBConfig.getSeparator("CONFIG_DB")
ASIC_DB_SEPARATOR = SonicDBConfig.getSeparator("ASIC_DB")
APP_DB_SEPARATOR = SonicDBConfig.getSeparator("APPL_DB")
APP_TABLE_TYPE_NAME = "ACL_TABLE_TYPE_TABLE"
APP_TABLE_NAME = "ACL_TABLE_TABLE"
APP_RULE_NAME = "ACL_RULE_TABLE"


class Acl_Table(Executor):
    """
    Debug Dump Plugin for ACL Table Module
    """
    ARG_NAME = "acl_table_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="ACL_TABLE", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        req_app = MatchRequest(db="APPL_DB", table=APP_TABLE_NAME, key_pattern="*", ns=ns)
        ret_app = self.match_engine.fetch(req_app)
        return [key.split(CFG_DB_SEPARATOR)[-1] for key in ret.get("keys")] + \
               [key.split(APP_DB_SEPARATOR)[-1] for key in ret_app.get("keys")]

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        acl_table_name = params[self.ARG_NAME]
        self.ns = params["namespace"]
        self.init_acl_table_config_info(acl_table_name)
        self.init_acl_table_appl_info(acl_table_name)
        self.init_acl_table_asic_info(acl_table_name)
        return self.ret_temp

    def init_acl_table_config_info(self, acl_table_name):
        req = MatchRequest(db="CONFIG_DB", table="ACL_TABLE", key_pattern=acl_table_name, return_fields=["type"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        # Find corresponding ACL table type in CONFIG DB
        return_values = ret["return_values"]
        acl_table_type_name = return_values.get(CFG_DB_SEPARATOR.join(["ACL_TABLE", acl_table_name]), {}).get("type")
        req = MatchRequest(db="CONFIG_DB", table="ACL_TABLE_TYPE", key_pattern=acl_table_type_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        # If not found don't add it to the table, it might be a default table type
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_acl_table_appl_info(self, acl_table_name):
        req = MatchRequest(db="APPL_DB", table=APP_TABLE_NAME, key_pattern=acl_table_name,
                           return_fields=["type"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        # Find corresponding ACL table type in CONFIG DB
        return_values = ret["return_values"]
        acl_table_type_name = return_values.get(APP_DB_SEPARATOR.join([APP_TABLE_NAME, acl_table_name]), {}).get("type")
        req = MatchRequest(db="APPL_DB", table=APP_TABLE_TYPE_NAME, key_pattern=acl_table_type_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        # If not found don't add it to the table, it might be a default table type
        if ret["keys"]:
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def find_any_rule(self, acl_table_name):
        req = MatchRequest(db="CONFIG_DB", table="ACL_RULE", key_pattern=CFG_DB_SEPARATOR.join([acl_table_name, "*"]), ns=self.ns)
        ret = self.match_engine.fetch(req)
        acl_rules = ret["keys"]
        if acl_rules:
            return acl_rules[0].split(CFG_DB_SEPARATOR)[-1]

        # Check in APPL_DB
        req = MatchRequest(db="APPL_DB", table=APP_RULE_NAME,
                           key_pattern=APP_DB_SEPARATOR.join([acl_table_name, "*"]), ns=self.ns)
        ret = self.match_engine.fetch(req)
        acl_rules = ret["keys"]
        if acl_rules:
            return acl_rules[0].split(APP_DB_SEPARATOR)[-1]

    def init_acl_table_asic_info(self, acl_table_name):
        acl_rule_name = self.find_any_rule(acl_table_name)
        if not acl_rule_name:
            return

        counter_oid = fetch_acl_counter_oid(self.match_engine, acl_table_name, acl_rule_name, self.ns)
        if not counter_oid:
            return

        req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_COUNTER"]),
                           key_pattern=counter_oid, return_fields=["SAI_ACL_COUNTER_ATTR_TABLE_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)

        return_values = ret["return_values"]
        counter_object = return_values.get(ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_COUNTER", counter_oid]), {})
        table_oid = counter_object.get("SAI_ACL_COUNTER_ATTR_TABLE_ID")
        if not table_oid:
            raise Exception("Invalid counter object without table OID in ASIC_DB")

        req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_TABLE"]),
                           key_pattern=table_oid, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_TABLE_GROUP_MEMBER"]),
                           key_pattern="*", field="SAI_ACL_TABLE_GROUP_MEMBER_ATTR_ACL_TABLE_ID",
                           value=table_oid, return_fields=["SAI_ACL_TABLE_GROUP_MEMBER_ATTR_ACL_TABLE_GROUP_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        group_oids = set()
        for _, entry in ret["return_values"].items():
            group_oids.add(entry.get("SAI_ACL_TABLE_GROUP_MEMBER_ATTR_ACL_TABLE_GROUP_ID"))

        for group_oid in group_oids:
            req = MatchRequest(db="ASIC_DB", table=ASIC_DB_SEPARATOR.join(["ASIC_STATE", "SAI_OBJECT_TYPE_ACL_TABLE_GROUP"]),
                               key_pattern=group_oid, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])
