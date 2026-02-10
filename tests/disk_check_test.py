import os
import sys
import syslog
from unittest.mock import patch
import subprocess

sys.path.append("scripts")
import disk_check

disk_check.MOUNTS_FILE = "/tmp/proc_mounts"

test_data = {
    "0": {
        "desc": "All good as /tmp is read-write",
        "args": ["", "-d", "/tmp"],
        "err": ""
    },
    "1": {
        "desc": "Not good as /tmpx is not read-write; But fix skipped",
        "args": ["", "-d", "/tmpx", "-s"],
        "err": "/tmpx is not read-write"
    },
    "2": {
        "desc": "Not good as /tmpx is not read-write; expect mount",
        "args": ["", "-d", "/tmpx"],
        "upperdir": "/tmp/tmpx",
        "workdir": "/tmp/tmpy",
        "mounts": "overlay_tmpx blahblah",
        "err": "/tmpx is not read-write|READ-ONLY: Mounted ['/tmpx'] to make Read-Write",
        "cmds": [['mount', '-t', 'overlay', 'overlay_tmpx', '-o', 'lowerdir=/tmpx,upperdir=/tmp/tmpx/tmpx,workdir=/tmp/tmpy/tmpx', '/tmpx']]
    },
    "3": {
        "desc": "Not good as /tmpx is not read-write; mount fail as create of upper fails",
        "args": ["", "-d", "/tmpx"],
        "upperdir": "/tmpx",
        "expect_ret": 1
    },
    "4": {
        "desc": "Not good as /tmpx is not read-write; mount fail as upper exist",
        "args": ["", "-d", "/tmpx"],
        "upperdir": "/tmp",
        "err": "/tmpx is not read-write|Already mounted",
        "expect_ret": 1
    },
    "5": {
        "desc": "/tmp is read-write, but as well mount exists; hence report",
        "args": ["", "-d", "/tmp"],
        "upperdir": "/tmp",
        "mounts": "overlay_tmp blahblah",
        "err": "READ-ONLY: Mounted ['/tmp'] to make Read-Write"
    },
    "6": {
        "desc": "Test another code path for good case",
        "args": ["", "-d", "/tmp"],
        "upperdir": "/tmp"
    }
}

err_data = ""
max_log_lvl = -1
cmds = []
current_tc = None

def mount_file(d):
    with open(disk_check.MOUNTS_FILE, "w") as s:
        s.write(d)


def report_err_msg(lvl, m):
    global err_data
    global max_log_lvl

    if lvl > max_log_lvl:
        max_log_lvl = lvl

    if lvl == syslog.LOG_ERR:
        if err_data:
            err_data += "|"
        err_data += m


class proc:
    returncode = 0
    stdout = None
    stderr = None

    def __init__(self, proc_upd = None):
        if proc_upd:
            self.returncode = proc_upd.get("ret", 0)
            self.stdout = proc_upd.get("stdout", None)
            self.stderr = proc_upd.get("stderr", None)


def mock_subproc_run(cmd, shell, stdout):
    global cmds

    assert shell == False
    assert stdout == subprocess.PIPE

    upd = (current_tc["proc"][len(cmds)]
            if len(current_tc.get("proc", [])) > len(cmds) else None)
    cmds.append(cmd)
    
    return proc(upd)


def init_tc(tc):
    global err_data, cmds, current_tc

    err_data = ""
    cmds = []
    mount_file(tc.get("mounts", ""))
    current_tc = tc


def swap_upper(tc):
    tmp_u = tc["upperdir"]
    tc["upperdir"] = disk_check.UPPER_DIR
    disk_check.UPPER_DIR = tmp_u


def swap_work(tc):
    tmp_w = tc["workdir"]
    tc["upperdir"] = disk_check.WORK_DIR
    disk_check.WORK_DIR = tmp_w


class TestDiskCheck(object):
    def setup(self):
        pass


    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 4096,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_readonly(self, mock_os_statvfs, mock_proc, mock_log):
        global err_data, cmds, max_log_lvl

        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        with patch('sys.argv', ["", "-l", "7", "-d", "/tmp"]):
            disk_check.main()
            assert max_log_lvl == syslog.LOG_DEBUG
            max_log_lvl = -1

        for i, tc in test_data.items():
            print("-----------Start tc {}---------".format(i))
            init_tc(tc)

            with patch('sys.argv', tc["args"]):
                if "upperdir" in tc:
                    swap_upper(tc)

                if "workdir" in tc:
                    # restore
                    swap_work(tc)

                ret = disk_check.main()

                if "upperdir" in tc:
                    # restore
                    swap_upper(tc)

                if "workdir" in tc:
                    # restore
                    swap_work(tc)

            print("ret = {}".format(ret))
            print("err_data={}".format(err_data))
            print("cmds: {}".format(cmds))

            assert ret == tc.get("expect_ret", 0)
            if  "err" in tc:
                assert err_data == tc["err"]
            assert cmds == tc.get("cmds", [])
            print("-----------End tc {}-----------".format(i))

            
        assert max_log_lvl == syslog.LOG_ERR

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('os.access', return_value=True)
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 0,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_mount_disk_full(self, mock_os_statvfs, mock_os_access, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        tc = {
            "upperdir": "/tmp",
        }
        swap_upper(tc)

        with patch('sys.argv', ["", "-d", "/tmpx"]):
            disk_check.main()

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('shutil.rmtree')
    @patch('os.access', return_value=True)
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 4096,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_unmount_disk_full(self, mock_os_statvfs, mock_os_access, mock_rmtree, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        tc = {
            "upperdir": "/tmp/tmpx",
            "workdir": "/tmp/tmpy"
        }
        swap_upper(tc)
        swap_work(tc)

        with patch('sys.argv', ["", "-d", "/tmpx"]):
            disk_check.main()

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('os.access', return_value=True)
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 0,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_diskfull(self, mock_os_statvfs, mock_os_access, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        result = disk_check.test_disk_full(["/etc"])
        assert result is True

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    def test_do_unmnt(self, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        disk_check.do_unmnt(["/etc"], "overlay_prefix")


    @classmethod
    def teardown_class(cls):
        subprocess.run("rm -rf /tmp/tmpx /tmp/tmpy", shell=True)  # cleanup the temporary dirs
        print("TEARDOWN")
