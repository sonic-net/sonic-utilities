from dump.match_infra import MatchRequest
from dump.helper import handle_multiple_keys_matched_error

# Return dict helper methods

def check_error(ret):
    """ Check if the match request failed """
    if ret["error"]:
        return True, ret["error"]
    else:
        return False, ""

def get_matched_keys(ret):
    """ Return Matched Keys """
    failed, err_str = check_error(ret)
    if not failed:
        return ret["keys"], ""
    else:
        return [], err_str

# Port Helper Methods

def fetch_port_oid(match_engine, port_name, ns):
    """
    Fetches thr relevant SAI_OBJECT_TYPE_PORT given port name
    """
    req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", key_pattern="*", field="SAI_HOSTIF_ATTR_NAME",
                       value=port_name, return_fields=["SAI_HOSTIF_ATTR_OBJ_ID"], ns=ns)
    ret = match_engine.fetch(req)
    asic_port_obj_id = ""
    if not ret["error"] and len(ret["keys"]) != 0:
        sai_hostif_obj_key = ret["keys"][-1]
        if sai_hostif_obj_key in ret["return_values"] and "SAI_HOSTIF_ATTR_OBJ_ID" in ret["return_values"][sai_hostif_obj_key]:
            asic_port_obj_id = ret["return_values"][sai_hostif_obj_key]["SAI_HOSTIF_ATTR_OBJ_ID"]
    return req, asic_port_obj_id, ret

# Vlan Helper Methods

def fetch_vlan_oid(match_engine, vlan_name, ns):
    # Convert 'Vlanxxx' to 'xxx'
    if vlan_name[0:4] != "Vlan" or not vlan_name[4:].isnumeric():
        vlan_num = -1
    else:
        vlan_num = int(vlan_name[4:])

    # Find the table named "ASIC_STATE:SAI_OBJECT_TYPE_VLAN:*" in which SAI_VLAN_ATTR_VLAN_ID = vlan_num
    req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN", key_pattern="*", field="SAI_VLAN_ATTR_VLAN_ID",
                    value=str(vlan_num), ns=ns)
    ret = match_engine.fetch(req)
    vlan_oid = ""
    if ret["keys"]:
        vlan_oid = ret["keys"][0].split(":", 2)[-1]
    return req, vlan_oid, ret

# LAG Helper Methods

def get_lag_members_from_cfg(match_engine, lag_name, ns):
    """
    Get the members associated with a LAG from Config DB
    """
    lag_members = []
    req = MatchRequest(db="CONFIG_DB", table="PORTCHANNEL_MEMBER", key_pattern=lag_name + "|*", ns=ns)
    ret = match_engine.fetch(req)
    for key in ret["keys"]:
        lag_members.append(key.split("|")[-1])
    return req, lag_members, ret

def get_lag_and_member_obj(match_engine, port_asic_obj, ns):
    """
    Given the member port oid, fetch lag_member & lag oid's
    """
    req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER", key_pattern="*", field="SAI_LAG_MEMBER_ATTR_PORT_ID",
                        value=port_asic_obj, return_fields=["SAI_LAG_MEMBER_ATTR_LAG_ID"], ns=ns)
    ret = match_engine.fetch(req)
    lag_member_key = ""
    lag_oid = ""
    if not ret["error"] and ret["keys"]:
        lag_member_key = ret["keys"][-1]
        if lag_member_key in ret["return_values"] and "SAI_LAG_MEMBER_ATTR_LAG_ID" in ret["return_values"][lag_member_key]:
            lag_oid = ret["return_values"][lag_member_key]["SAI_LAG_MEMBER_ATTR_LAG_ID"]
    return lag_member_key, lag_oid

def fetch_lag_oid(match_engine, lag_name, ns):
    """
    Finding the relevant SAI_OBJECT_TYPE_LAG key directly from the ASIC is not possible given a LAG name
    Thus, using the members to find SAI_LAG_MEMBER_ATTR_LAG_ID
    """
    _, lag_members, _ = get_lag_members_from_cfg(match_engine, lag_name, ns)
    lag_type_oids = set()
    for port_name in lag_members:
        _, port_asic_obj, _ = fetch_port_oid(match_engine, port_name, ns)
        if port_asic_obj:
            lag_member_key, lag_oid = get_lag_and_member_obj(match_engine, port_asic_obj, ns)
            lag_type_oids.add(lag_oid)
    lag_type_oid, lag_type_oids = "", list(lag_type_oids)
    if lag_type_oids:
        if len(lag_type_oids) > 1:
            # Ideally, only one associated lag_oid should be present for a portchannel
            handle_multiple_keys_matched_error("Multiple lag_oids matched for portchannel: {}, \
                                               lag_oids matched {}".format(lag_name, lag_type_oids), lag_type_oids[-1])
        lag_type_oid = lag_type_oids[-1]
    return lag_type_oid

# ACL helpers

def fetch_acl_counter_oid(match_engine, acl_table_name, acl_rule_name, ns):
    """
    Fetch ACL counter OID from COUNTERS DB for a particular rule
    """
    counters_db = match_engine.get_redis_source_adapter()
    counters_db.connect("COUNTERS_DB", ns)
    counters = counters_db.hgetall("COUNTERS_DB", "ACL_COUNTER_RULE_MAP")
    counter_oid = counters.get(f"{acl_table_name}{counters_db.get_separator('COUNTERS_DB')}{acl_rule_name}")
    return counter_oid
