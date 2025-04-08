import json
import logging
import proto_utils
import time
import subprocess
import os
import tempfile

TIME_BETWEEN_CHUNKS = 1

class GNMIEnvironment:
    gnmi_ip = "127.0.0.1"
    gnmi_port = 8080
    work_dir = "/"
    username = "admin"
    password = "password"
    dpu_index = 0
    num_dpus = 1
def exec_cmd(cmd):
    logging.debug(cmd)
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Check the result
    if result.returncode == 0:
        logging.debug("Command executed successfully.")
        logging.debug("Output:")
        logging.debug(result.stdout)
    else:
        logging.error("Error executing the command.")
        logging.error("Error output:")
        logging.error(result.stderr)
    return result

def cleanup_proto_files(cmd_list):
    if not cmd_list:
        return
    for cmd in cmd_list:
        del_file = cmd.split("$")[-1]
        if del_file != '':
            logging.debug("Deleting file:" + del_file)
            os.unlink(del_file)

def gnmi_set(env, delete_list, update_list, replace_list):
    """
    Send GNMI set request with GNMI client

    Args:
        env: GNMIEnvironment
        delete_list: list for delete operations
        update_list: list for update operations
        replace_list: list for replace operations

    Returns:
    """
    cmd = '/usr/sbin/gnmi_set '
    cmd += '-insecure -target_addr %s:%u ' %(env.gnmi_ip, env.gnmi_port)
    cmd += '-username %s -password %s -alsologtostderr ' %(env.username, env.password)
    
    for delete in delete_list:
        cmd += '--delete ' + delete
        cmd += ' '
        logging.info("Deleting " + delete)
    for update in update_list:
        cmd += '--update ' + update
        cmd += ' '
        logging.info("Updating " + update)
    for replace in replace_list:
        cmd += '--replace ' + replace
        cmd += ' '
        logging.info("Replacing " + replace)
    
    result = exec_cmd(cmd)
    if result.returncode == 0:
        logging.info("Command executed successfully")

    # Cleanup the proto files created for update and replace
    cleanup_proto_files(update_list)
    cleanup_proto_files(replace_list)

    return

def gnmi_get(env, path_list):
    """
    Send GNMI get request with GNMI client

    Args:
        env: GNMIEnvironment
        path_list: list for get path

    Returns:
        msg_list: list for get result
    """
    base_cmd = '/usr/sbin/gnmi_get '
    base_cmd += '-insecure -target_addr %s:%u ' % (env.gnmi_ip, env.gnmi_port)
    base_cmd += '-username %s -password %s -alsologtostderr -encoding PROTO ' %(env.username, env.password)
    
    for index, path in enumerate(path_list):
        cmd = base_cmd
        cmd += "-xpath "
        cmd += path
        cmd += " "
        cmd += "-proto_file "
        cmd += "get_result"
        
        result = exec_cmd(cmd)
    
        elem = path.split('/')
        if elem[3].startswith('_'):
            tblname = elem[3][1:]
        else:
            tblname = elem[3]
        
        print("-"*25)
        print(path)        
        
        if result.returncode:
            error = "rpc error:"
            if error in result.stderr:
                rpc_error = result.stderr.split(error, 1)
                print("GRPC error: " + rpc_error[1])
            else:
                print("command failed: " + result.stderr)
            continue
        
        with open("get_result", 'rb') as file:
            # Read the entire content of the binary file
            binary_data = file.read()
            pb_obj = proto_utils.from_pb(tblname, binary_data)

        print(pb_obj)
        os.unlink("get_result")

def process_template_chunk(res, env, dest_path, batch_val, sleep_secs):

    get_list = []
    delete_list = []
    update_list = []
    replace_list = []
    update_cnt = 0
    base_path = "/sonic-db:APPL_DB"
    base_path = "%s/dpu%d" %(base_path, env.dpu_index)
    batch_cnt = 0

    for operation in res:
        batch_cnt += 1
        if operation["OP"] == "SET" or operation["OP"] == "REP":
            for k, v in operation.items():
                if k == "OP":
                    continue
                logging.debug("Config Json %s" % k)
                update_cnt += 1
                filename = "update%u" % update_cnt
                if proto_utils.ENABLE_PROTO:
                    message = proto_utils.json_to_proto(k, v)
                    with open(env.work_dir+filename, "wb") as file:
                        file.write(message)
                else:
                    text = json.dumps(v)
                    with open(env.work_dir+filename, "w") as file:
                        file.write(text)
                keys = k.split(":", 1)
                k = keys[0] + "[key=" + keys[1] + "]"
                if proto_utils.ENABLE_PROTO:
                    path = "%s/%s:$%s" % (base_path, k, env.work_dir+filename)
                else:
                    path = "%s/%s:@%s" % (base_path, k, env.work_dir+filename)
                if operation["OP"] == "REP":
                    replace_list.append(path)
                else:
                    update_list.append(path)
        elif operation["OP"] == "DEL":
            for k, v in operation.items():
                if k == "OP":
                    continue
                keys = k.split(":", 1)
                k = keys[0] + "[key=" + keys[1] + "]"
                path = "%s/%s" % (base_path, k)
                delete_list.append(path)
        elif operation["OP"] == "GET":
            for k, v in operation.items():
                if k == "OP":
                    continue
                if ":" not in k:
                    continue
                keys = k.split(":", 1)
                k = keys[0] + "[key=" + keys[1] + "]"
                path = "%s/%s" % (base_path, k)
                get_list.append(path)             
        else:
            logging.error("Invalid operation %s" % operation["OP"])
            batch_cnt -= 1

        if batch_cnt == batch_val:
            time.sleep(sleep_secs)
            if get_list:
                gnmi_get(env, get_list)
            if delete_list or update_list or replace_list:
                gnmi_set(env, delete_list, update_list, replace_list)
            batch_cnt = 0
            update_cnt = 0
            delete_list = []
            update_list = []
            replace_list = []
            get_list = []
    
    if get_list:
        gnmi_get(env, get_list)
    if delete_list or update_list or replace_list:
        gnmi_set(env, delete_list, update_list, replace_list)
   
def apply_gnmi_file(env, dest_path, batch_val=10, sleep_secs=0):
    """
    Apply dash configuration with gnmi client

    Args:
        env: GNMIEnvironment
        dest_path: configuration file path
        batch_val: how many commands in one batch
        sleep_secs: how many seconds to sleep between sending a batch and next

    Returns:
    """
    with open(dest_path, 'r') as file:
        res = json.load(file)

    if isinstance(res[0], dict):
        process_template_chunk(res, env, dest_path, batch_val, sleep_secs)
    else:
        for i in res:
            process_template_chunk(i, env, dest_path, batch_val, sleep_secs)
            time.sleep(TIME_BETWEEN_CHUNKS)
