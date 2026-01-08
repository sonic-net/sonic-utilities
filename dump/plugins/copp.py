import re
from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from dump.helper import handle_error, handle_multiple_keys_matched_error
from .executor import Executor

TRAP_ID_MAP = {
    "stp": "SAI_HOSTIF_TRAP_TYPE_STP",
    "lacp": "SAI_HOSTIF_TRAP_TYPE_LACP",
    "eapol": "SAI_HOSTIF_TRAP_TYPE_EAPOL",
    "lldp": "SAI_HOSTIF_TRAP_TYPE_LLDP",
    "pvrst": "SAI_HOSTIF_TRAP_TYPE_PVRST",
    "igmp_query": "SAI_HOSTIF_TRAP_TYPE_IGMP_TYPE_QUERY",
    "igmp_leave": "SAI_HOSTIF_TRAP_TYPE_IGMP_TYPE_LEAVE",
    "igmp_v1_report": "SAI_HOSTIF_TRAP_TYPE_IGMP_TYPE_V1_REPORT",
    "igmp_v2_report": "SAI_HOSTIF_TRAP_TYPE_IGMP_TYPE_V2_REPORT",
    "igmp_v3_report": "SAI_HOSTIF_TRAP_TYPE_IGMP_TYPE_V3_REPORT",
    "sample_packet": "SAI_HOSTIF_TRAP_TYPE_SAMPLEPACKET",
    "switch_cust_range": "SAI_HOSTIF_TRAP_TYPE_SWITCH_CUSTOM_RANGE_BASE",
    "arp_req": "SAI_HOSTIF_TRAP_TYPE_ARP_REQUEST",
    "arp_resp": "SAI_HOSTIF_TRAP_TYPE_ARP_RESPONSE",
    "dhcp": "SAI_HOSTIF_TRAP_TYPE_DHCP",
    "dhcp_l2": "SAI_HOSTIF_TRAP_TYPE_DHCP_L2",
    "ospf": "SAI_HOSTIF_TRAP_TYPE_OSPF",
    "pim": "SAI_HOSTIF_TRAP_TYPE_PIM",
    "vrrp": "SAI_HOSTIF_TRAP_TYPE_VRRP",
    "bgp": "SAI_HOSTIF_TRAP_TYPE_BGP",
    "dhcpv6": "SAI_HOSTIF_TRAP_TYPE_DHCPV6",
    "dhcpv6_l2": "SAI_HOSTIF_TRAP_TYPE_DHCPV6_L2",
    "ospfv6": "SAI_HOSTIF_TRAP_TYPE_OSPFV6",
    "vrrpv6": "SAI_HOSTIF_TRAP_TYPE_VRRPV6",
    "bgpv6": "SAI_HOSTIF_TRAP_TYPE_BGPV6",
    "neigh_discovery": "SAI_HOSTIF_TRAP_TYPE_IPV6_NEIGHBOR_DISCOVERY",
    "mld_v1_v2": "SAI_HOSTIF_TRAP_TYPE_IPV6_MLD_V1_V2",
    "mld_v1_report": "SAI_HOSTIF_TRAP_TYPE_IPV6_MLD_V1_REPORT",
    "mld_v1_done": "SAI_HOSTIF_TRAP_TYPE_IPV6_MLD_V1_DONE",
    "mld_v2_report": "SAI_HOSTIF_TRAP_TYPE_MLD_V2_REPORT",
    "ip2me": "SAI_HOSTIF_TRAP_TYPE_IP2ME",
    "ssh": "SAI_HOSTIF_TRAP_TYPE_SSH",
    "snmp": "SAI_HOSTIF_TRAP_TYPE_SNMP",
    "router_custom_range": "SAI_HOSTIF_TRAP_TYPE_ROUTER_CUSTOM_RANGE_BASE",
    "l3_mtu_error": "SAI_HOSTIF_TRAP_TYPE_L3_MTU_ERROR",
    "ttl_error": "SAI_HOSTIF_TRAP_TYPE_TTL_ERROR",
    "udld": "SAI_HOSTIF_TRAP_TYPE_UDLD",
    "bfd": "SAI_HOSTIF_TRAP_TYPE_BFD",
    "bfdv6": "SAI_HOSTIF_TRAP_TYPE_BFDV6",
    "src_nat_miss": "SAI_HOSTIF_TRAP_TYPE_SNAT_MISS",
    "dest_nat_miss": "SAI_HOSTIF_TRAP_TYPE_DNAT_MISS",
    "neighbor_miss": "SAI_HOSTIF_TRAP_TYPE_NEIGHBOR_MISS"
}

CFG_COPP_TRAP_TABLE_NAME = "COPP_TRAP"
CFG_COPP_GROUP_TABLE_NAME = "COPP_GROUP"
APP_COPP_TABLE_NAME = "COPP_TABLE"

ASIC_DB_PREFIX = "ASIC_STATE"

ASIC_TRAP_OBJ = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_HOSTIF_TRAP"
ASIC_TRAP_GROUP_OBJ = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP"
ASIC_HOSTIF_TABLE_ENTRY = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_HOSTIF_TABLE_ENTRY"
ASIC_HOSTIF = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_HOSTIF"
ASIC_POLICER_OBJ = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_POLICER"
ASIC_QUEUE_OBJ = ASIC_DB_PREFIX + ":" + "SAI_OBJECT_TYPE_QUEUE"


class Copp(Executor):

    ARG_NAME = "trap_id"
    CONFIG_FILE = "/etc/sonic/copp_cfg.json"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.copp_trap_cfg_key = ""
        self.trap_group = ""
        self.trap_id = ""
        self.ns = ""

    def fetch_all_trap_ids(self, ret):
        traps = []
        if not ret["error"]:
            for key in ret["keys"]:
                temp_ids = ret["return_values"][key]["trap_ids"].split(",")
                for id in temp_ids:
                    traps.append(id)
        return traps

    def get_all_args(self, ns):
        all_trap_ids = set()
        req = MatchRequest(file=Copp.CONFIG_FILE, table=CFG_COPP_TRAP_TABLE_NAME, return_fields=["trap_ids"], ns=ns)
        ret = self.match_engine.fetch(req)
        all_trap_ids.update(self.fetch_all_trap_ids(ret))

        req = MatchRequest(db="CONFIG_DB", table=CFG_COPP_TRAP_TABLE_NAME, return_fields=["trap_ids"], ns=ns)
        ret = self.match_engine.fetch(req)
        all_trap_ids.update(self.fetch_all_trap_ids(ret))
        return list(all_trap_ids)

    def execute(self, params):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB", "CONFIG_FILE"])
        self.ns = params["namespace"]
        self.trap_id = params[Copp.ARG_NAME]
        self.copp_trap_cfg_key = ""
        self.trap_group = ""
        self.handle_user_and_default_config()
        self.handle_appl_db()
        self.handle_asic_db()
        self.handle_state_db()
        return self.ret_temp

    def handle_state_db(self):
        req = MatchRequest(db="STATE_DB", table="COPP_TRAP_TABLE", key_pattern=self.copp_trap_cfg_key)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

        req = MatchRequest(db="STATE_DB", table="COPP_GROUP_TABLE", key_pattern=self.trap_group)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def handle_appl_db(self):
        req = MatchRequest(db="APPL_DB", table=APP_COPP_TABLE_NAME, key_pattern="*", field="trap_ids",
                           value=self.trap_id, match_entire_list=False, return_fields=["trap_group"])
        ret = self.match_engine.fetch(req)
        tg = ""
        if not ret["error"] and len(ret["keys"]) > 0:
            if len(ret["keys"]) > 1:
                err_str_tup = ("ERROR: Multiple COPP_TABLE Keys found for the trap_id {} in",
                               "the APPL_DB, keys found: {}")
                err_str = " ".join(err_str_tup)
                err_str = err_str.format(self.trap_id, str(ret["keys"]))
                handle_multiple_keys_matched_error(err_str, ret["keys"][0])
            self.ret_temp["APPL_DB"]["keys"].append(ret["keys"][0])
            tg = ret["return_values"][ret["keys"][0]]["trap_group"]
        else:
            self.ret_temp["APPL_DB"]["tables_not_found"].append(APP_COPP_TABLE_NAME)

        if tg != self.trap_group and not self.trap_group and not tg:
            err_str_tup = ("The Associated Trap_group for the trap_id found in APPL",
                           "and CONFIG_DB/CONFIG_FILE did not match.",
                           "In APPL_DB: {}, CONFIG_DB: {}",
                           "\n Proceding with the trap group found in APPL DB")
            err_str = " ".join(err_str_tup)
            err_str = err_str.format(tg, self.trap_group)
            handle_error(err_str, False)

        if tg:
            self.trap_group = tg

    def handle_asic_db(self):
        if self.trap_id not in TRAP_ID_MAP:
            err_str = "Invalid Trap Id {} is provided, no corresponding SAI_TRAP_OBJ is found"
            handle_error(err_str.format(self.trap_id), False)
            sai_trap_id = ""
        else:
            sai_trap_id = TRAP_ID_MAP[self.trap_id]
        sai_trap, sai_trap_grp = self.__get_asic_hostif_trap_obj(sai_trap_id)
        sai_queue, sai_policer = self.__get_asic_hostif_trap_group_obj(sai_trap_grp)
        self.__get_asic_policer_obj(sai_policer)
        self.__get_asic_queue_obj(sai_queue)
        sai_hostif_vid = self.__get_asic_hostif_entry_obj(sai_trap)
        self.__get_asic_hostif_obj(sai_hostif_vid)

    def __get_asic_hostif_trap_obj(self, sai_trap_id):
        if not sai_trap_id:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append(ASIC_TRAP_OBJ)
            return "", ""

        req = MatchRequest(db="ASIC_DB", table=ASIC_TRAP_OBJ, field="SAI_HOSTIF_TRAP_ATTR_TRAP_TYPE", value=sai_trap_id,
                           ns=self.ns, return_fields=["SAI_HOSTIF_TRAP_ATTR_TRAP_GROUP"])
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) > 0:
            if len(ret["keys"]) > 1:
                err_str = "ERROR: Multiple {} Keys found for the trap_sai_type {} in the ASIC_DB, keys found: {}".format(ASIC_TRAP_OBJ, trap_sai_obj, str(ret["keys"]))
                handle_multiple_keys_matched_error(err_str, ret["keys"][0])
            trap_asic_key = ret["keys"][0]
            self.ret_temp["ASIC_DB"]["keys"].append(trap_asic_key)
            return trap_asic_key, ret["return_values"][trap_asic_key]["SAI_HOSTIF_TRAP_ATTR_TRAP_GROUP"]
        else:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append(ASIC_TRAP_OBJ)
            return "", ""

    def __get_asic_hostif_trap_group_obj(self, trap_group_obj):
        if not trap_group_obj:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append(ASIC_TRAP_GROUP_OBJ)
            return "", ""

        req = MatchRequest(db="ASIC_DB", table=ASIC_TRAP_GROUP_OBJ, key_pattern=trap_group_obj, ns=self.ns,
                           return_fields=["SAI_HOSTIF_TRAP_GROUP_ATTR_QUEUE", "SAI_HOSTIF_TRAP_GROUP_ATTR_POLICER"])
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) > 0:
            trap_group_asic_key = ret["keys"][0]
            self.ret_temp["ASIC_DB"]["keys"].append(trap_group_asic_key)
            SAI_QUEUE_INDEX = ret["return_values"][trap_group_asic_key]["SAI_HOSTIF_TRAP_GROUP_ATTR_QUEUE"]
            SAI_POLICER_OBJ = ret["return_values"][trap_group_asic_key]["SAI_HOSTIF_TRAP_GROUP_ATTR_POLICER"]
            return SAI_QUEUE_INDEX, SAI_POLICER_OBJ
        else:
            self.ret_temp["ASIC_DB"]["tables_not_found"].append(ASIC_TRAP_GROUP_OBJ)
            return "", ""

    def __get_asic_policer_obj(self, policer_sai_obj):
        # Not adding to tables_not_found because, some of the trap_ids might not have a policer associated with them
        # and that is expected
        if not policer_sai_obj:
            return
        req = MatchRequest(db="ASIC_DB", table=ASIC_POLICER_OBJ, key_pattern=policer_sai_obj, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)

    def __get_asic_queue_obj(self, queue_sai_obj):
        # Not adding tp tables_not_found because of the type of reason specified for policer obj
        if not queue_sai_obj:
            return
        req = MatchRequest(db="ASIC_DB", table=ASIC_QUEUE_OBJ, field="SAI_QUEUE_ATTR_INDEX", value=queue_sai_obj, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)

    def __get_asic_hostif_entry_obj(self, sai_trap_key):
        # Not adding tp tables_not_found because of the type of reason specified for policer obj
        if not sai_trap_key:
            return
        matches = re.findall(r"oid:0x\w{1,14}", sai_trap_key)
        if matches:
            sai_trap_vid = matches[0]
        else:
            return
        req = MatchRequest(db="ASIC_DB", table=ASIC_HOSTIF_TABLE_ENTRY, field="SAI_HOSTIF_TABLE_ENTRY_ATTR_TRAP_ID",
                           value=sai_trap_vid, return_fields=["SAI_HOSTIF_TABLE_ENTRY_ATTR_HOST_IF"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)
        if not ret["error"] and len(ret["keys"]) > 0:
            sai_hostif_table_entry_key = ret["keys"][0]
            sai_hostif_vid = ret["return_values"][sai_hostif_table_entry_key]["SAI_HOSTIF_TABLE_ENTRY_ATTR_HOST_IF"]
            return sai_hostif_vid

    def __get_asic_hostif_obj(self, sai_hostif_vid):
        # Not adding tp tables_not_found because of the type of reason specified for policer obj
        if not sai_hostif_vid:
            return
        req = MatchRequest(db="ASIC_DB", table=ASIC_HOSTIF, key_pattern=sai_hostif_vid, ns=self.ns)
        ret = self.match_engine.fetch(req)
        self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"], False)

     # When the user writes config to CONFIG_DB, that takes precedence over default config
    def handle_user_and_default_config(self):
        # ------------------ Find trap_id_key and trap_group from both the sources
        # Search for any user-provided config for the trap-id provided
        trap_id_key_db, trap_group_db = self.__find_trap_id_in_db()
        trap_id_key_cf, trap_group_cf = "", ""
        if not trap_id_key_db:  # If nothing is found, search in CONFIG_FILE
            trap_id_key_cf, trap_group_cf = self.__find_trap_id_in_conf_file()
        elif trap_id_key_db and not trap_group_db:
            _, trap_group_cf = self.__find_trap_id_in_conf_file(trap_id_key_db.split("|")[-1], False)

        # ------------------ Find any diff and fill the return dictionary with COPP_TRAP keys
        if trap_id_key_db:
            self.ret_temp["CONFIG_DB"]["keys"].append(trap_id_key_db)
            self.copp_trap_cfg_key = trap_id_key_db.split("|")[-1]
            id_in_file, _ = self.__find_trap_id_in_conf_file(self.copp_trap_cfg_key, False)
            if id_in_file == trap_id_key_db:  # If any diff
                self.ret_temp["CONFIG_FILE"]["keys"].append(trap_id_key_db)
        elif trap_id_key_cf:
            self.ret_temp["CONFIG_FILE"]["keys"].append(trap_id_key_cf)
            self.copp_trap_cfg_key = trap_id_key_cf.split("|")[-1]
            id_in_file, _ = self.__find_trap_id_in_db(self.copp_trap_cfg_key, False)
            if id_in_file == trap_id_key_cf:  # Find the diff, if any, inside the CONFIG DB
                self.ret_temp["CONFIG_DB"]["keys"].append(trap_id_key_cf)
        else:
            self.ret_temp["CONFIG_FILE"]["tables_not_found"].append(CFG_COPP_TRAP_TABLE_NAME)
            self.ret_temp["CONFIG_DB"]["tables_not_found"].append(CFG_COPP_TRAP_TABLE_NAME)

        # ------------------ Find any diff and fill the return dictionary with COPP_GROUP keys
        if trap_group_db:  # Preference to User-provided Config
            self.trap_group = trap_group_db
            trap_in_cfg_file = False
        elif trap_group_cf:  # Then, the preference to the group found in CFG_File
            self.trap_group = trap_group_cf
            trap_in_cfg_file = True
        else:
            self.ret_temp["CONFIG_FILE"]["tables_not_found"].append(CFG_COPP_GROUP_TABLE_NAME)
            self.ret_temp["CONFIG_DB"]["tables_not_found"].append(CFG_COPP_GROUP_TABLE_NAME)
            return
        tg_in_default = self.__fill_trap_group_in_conf_file(trap_in_cfg_file)  # Check if the trap_group in cfg_file
        # Trap_group is expected to be in cfg_db when
        # 1) Trap_group is not found in cfg_file
        # 2) Trap_ID was provided by the user i.e trap_in_cfg_file = False
        # Otherwise, we're just looking for diff
        self.__fill_trap_group_in_conf_db(not(tg_in_default) and not(trap_in_cfg_file))

    def __fill_trap_group_in_conf_file(self, not_found_report=True):
        req = MatchRequest(table=CFG_COPP_GROUP_TABLE_NAME, key_pattern=self.trap_group, ns=self.ns, file=Copp.CONFIG_FILE)
        ret = self.match_engine.fetch(req)
        key_tg = ""
        if not ret["error"] and len(ret["keys"]) > 0:
            key_tg = ret["keys"][0]
            self.ret_temp["CONFIG_FILE"]["keys"].append(key_tg)
            return True
        elif not_found_report:
            self.ret_temp["CONFIG_FILE"]["tables_not_found"].append(CFG_COPP_GROUP_TABLE_NAME)
        return False

    def __fill_trap_group_in_conf_db(self, not_found_report=True):
        req = MatchRequest(table=CFG_COPP_GROUP_TABLE_NAME, key_pattern=self.trap_group, ns=self.ns, db="CONFIG_DB")
        ret = self.match_engine.fetch(req)
        key_tg = ""
        if not ret["error"] and len(ret["keys"]) > 0:
            key_tg = ret["keys"][0]
            self.ret_temp["CONFIG_DB"]["keys"].append(key_tg)
            return True
        elif not_found_report:
            self.ret_temp["CONFIG_DB"]["tables_not_found"].append(CFG_COPP_GROUP_TABLE_NAME)
        return False

    def __find_trap_id_in_conf_file(self, key_ptrn="*", do_fv_check=True):
        field_, value_ = None, None
        if do_fv_check:
            field_ = "trap_ids"
            value_ = self.trap_id
        req = MatchRequest(file=Copp.CONFIG_FILE, table=CFG_COPP_TRAP_TABLE_NAME, key_pattern=key_ptrn, match_entire_list=False,
                           ns=self.ns, return_fields=["trap_group"], field=field_, value=value_)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) > 0:
            if len(ret["keys"]) > 1:
                err_str = "ERROR (AMBIGUITY): Multiple COPP_TRAP Keys found for the trap_id {} in the copp_init file,  i.e. {}".format(self.trap_id, str(ret["keys"]))
                handle_multiple_keys_matched_error(err_str, ret["keys"][0])
            key_copp_trap = ret["keys"][0]
            return key_copp_trap, ret["return_values"][key_copp_trap]["trap_group"]
        else:
            return "", ""

    def __find_trap_id_in_db(self, key_ptrn="*", do_fv_check=True):
        field_, value_ = None, None
        if do_fv_check:
            field_ = "trap_ids"
            value_ = self.trap_id
        req = MatchRequest(db="CONFIG_DB", table=CFG_COPP_TRAP_TABLE_NAME, key_pattern=key_ptrn, match_entire_list=False,
                           ns=self.ns, return_fields=["trap_group"], field=field_, value=value_)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) > 0:
            if len(ret["keys"]) > 1:
                err_str = "Multiple COPP_TRAP Keys found for the trap_id {} in the CONFIG_DB, i.e. {}".format(self.trap_id, str(ret["keys"]))
                handle_multiple_keys_matched_error(err_str, ret["keys"][0])
            key_copp_trap = ret["keys"][0]
            return key_copp_trap, ret["return_values"][key_copp_trap]["trap_group"]
        else:
            return "", ""
