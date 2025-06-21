import os
import subprocess

GENERATE_DUMP_FILE = "/tmp/generate_dump_tmp"

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")


def run_saidump(asic_num, route_num):
    result = subprocess.run([". " + test_path + "/saidump_test.sh && test_saidump " + str(asic_num) +
                            " " + str(route_num)], capture_output=True, text=True, shell=True, executable='/bin/bash')
    return result.stdout.strip()


# saidump test list format: [ACIS number, ipv4 and ipv6 route table size, expected function save_cmd arguments]
saidump_test_list = [
    [1, 10000, "docker exec syncd saidump saidump"],
    [1, 12000, "docker exec syncd saidump saidump"],
    [1, 12001, "docker exec syncd saidump.sh saidump"],
    [1, 20000, "docker exec syncd saidump.sh saidump"],
    [2, 10000, "docker exec syncd0 saidump saidump0\ndocker exec syncd1 saidump saidump1"],
    [2, 12000, "docker exec syncd0 saidump saidump0\ndocker exec syncd1 saidump saidump1"],
    [2, 12001, "docker exec syncd0 saidump.sh saidump0\ndocker exec syncd1 saidump.sh saidump1"],
    [2, 20000, "docker exec syncd0 saidump.sh saidump0\ndocker exec syncd1 saidump.sh saidump1"]
]


def shell_pre_process(in_file, out_file):
    buf = []

    with open(in_file, 'r') as file:
        lines = file.readlines()

    for line in lines:
        if line.strip().startswith("while getopts"):
            break
        else:
            buf.append(line)

    # Write the modified content back to the file
    with open(out_file, 'w') as file:
        file.writelines(buf)


def test_saidump():
    # preprocess the generate_dump to a new script without non-functional codes
    shell_pre_process(scripts_path + '/generate_dump', GENERATE_DUMP_FILE)

    for item in saidump_test_list:
        output = run_saidump(item[0], item[1])
        assert output == item[2]

    if os.path.exists(GENERATE_DUMP_FILE):
        os.remove(GENERATE_DUMP_FILE)
