import os, sys, json


def create_template_dict(dbs):
    """ Generate a Template which will be returned by Executor Classes """
    return {db: {'keys': [], 'tables_not_found': []} for db in dbs}


def verbose_print(str):
    if "VERBOSE" in os.environ and os.environ["VERBOSE"] == "1":
        print(str)


def handle_error(err_str, excep=False):
    """ 
    Handles general error conditions, if any experienced by the module,
    Set excep = True, to raise a exception  
    """
    if excep:
        raise Exception("ERROR : {}".format(err_str))
    else:
        print("ERROR : {}".format(err_str), file = sys.stderr)
  

def handle_multiple_keys_matched_error(err_str, key_to_go_with="", excep=False):
    if excep:
        handle_error(err_str, True)
    else:
        print("ERROR (AMBIGUITY): {} \n Proceeding with the key {}".format(err_str, key_to_go_with), file = sys.stderr)


def sort_lists(ret_template):
    """ Used to sort the nested list returned by the template dict. """
    for db in ret_template.keys():
        for key in ret_template[db].keys():
            if isinstance(ret_template[db][key], list):
                ret_template[db][key].sort()
    return ret_template


def populate_mock(db, db_names, dedicated_dbs):
    for db_name in db_names:
        db.connect(db_name)
        # Delete any default data
        db.delete_all_by_pattern(db_name, "*")
        with open(dedicated_dbs[db_name]) as f:
            mock_json = json.load(f)
        for key in mock_json:
            for field, value in mock_json[key].items():
                db.set(db_name, key, field, value)
