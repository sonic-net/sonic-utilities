import errno
import os
import sys
import syslog
from unittest.mock import patch
import subprocess

sys.path.append("scripts")
import disk_check

disk_check.MOUNTS_FILE = "/tmp/proc_mounts"

real_open = open

test_data = {
    "0": {
        "desc": "All good as /tmp is read-write",
        "args": ["", "-d", "/tmp"],
        "err": ""
    },
    "1": {
        "desc": "Not good as /tmpx is not read-write; But fix skipped",
        "args": ["", "-d", "/tmpx", "-s"],
        "err": "/tmpx is not read-write. Monit diskCheck write marker failed: "
               "[Errno 30] Read-only file system"
    },
    "2": {
        "desc": "Not good as /tmpx is not read-write; expect mount",
        "args": ["", "-d", "/tmpx"],
        "upperdir": "/tmp/tmpx",
        "workdir": "/tmp/tmpy",
        "mounts": "overlay_tmpx blahblah",
        "err": "/tmpx is not read-write. Monit diskCheck write marker failed: "
               "[Errno 30] Read-only file system|"
               "READ-ONLY: Mounted ['/tmpx'] to make Read-Write",
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
        "err": "/tmpx is not read-write. Monit diskCheck write marker failed: "
               "[Errno 30] Read-only file system|Already mounted",
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


def mock_disk_open(file, *args, **kwargs):
    if file == "/tmpx/.monit_diskCheck_rw_marker":
        raise OSError(errno.EROFS, os.strerror(errno.EROFS), file)

    return real_open(file, *args, **kwargs)


def assert_error_messages(actual, expected):
    actual_messages = actual.split("|") if actual else []
    expected_messages = expected.split("|") if expected else []

    assert len(actual_messages) == len(expected_messages)
    for actual_message, expected_message in zip(actual_messages, expected_messages):
        assert actual_message.startswith(expected_message)


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
    tc["workdir"] = disk_check.WORK_DIR
    disk_check.WORK_DIR = tmp_w


class TestDiskCheck(object):
    def setup_method(self):
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

            with patch('sys.argv', tc["args"]), \
                    patch("builtins.open", side_effect=mock_disk_open):
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
                assert_error_messages(err_data, tc["err"])
            assert cmds == tc.get("cmds", [])
            print("-----------End tc {}-----------".format(i))

            
        assert max_log_lvl == syslog.LOG_ERR

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch("disk_check.test_writable", return_value=True)
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 0,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_mount_disk_full(self, mock_os_statvfs, mock_test_writable, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        tc = {
            "upperdir": "/tmp",
        }
        init_tc(tc)

        swap_upper(tc)
        try:
            with patch('sys.argv', ["", "-d", "/tmpx"]):
                ret = disk_check.main()
        finally:
            swap_upper(tc)

        assert ret == 1
        assert err_data == "/tmpx has no free disk space|Already mounted"
        assert cmds == []
        mock_test_writable.assert_called_once_with(["/tmpx"])

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('shutil.rmtree')
    @patch("disk_check.test_writable", return_value=True)
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 4096,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_unmount_disk_full(self, mock_os_statvfs, mock_test_writable, mock_rmtree,
                               mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        tc = {
            "upperdir": "/tmp/tmpx",
            "workdir": "/tmp/tmpy",
            "mounts": "overlay_disk_full_tmpx blahblah",
            "cmds": [["umount", "-l", "overlay_disk_full_tmpx"]]
        }
        init_tc(tc)
        os.makedirs(tc["upperdir"], exist_ok=True)
        os.makedirs(tc["workdir"], exist_ok=True)

        swap_upper(tc)
        swap_work(tc)
        try:
            with patch('sys.argv', ["", "-d", "/tmpx"]):
                ret = disk_check.main()
        finally:
            swap_upper(tc)
            swap_work(tc)

        assert ret == 0
        assert cmds == tc["cmds"]
        mock_test_writable.assert_called_once_with(["/tmpx"])
        assert mock_rmtree.call_count == 2

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch('os.statvfs', return_value=os.statvfs_result((4096, 4096, 1909350, 1491513, 0,
                                                         971520, 883302, 883302, 4096, 255)))
    def test_diskfull(self, mock_os_statvfs, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        result = disk_check.test_disk_full(["/etc"])
        assert result is True

    @patch("disk_check.syslog.syslog")
    @patch("disk_check.subprocess.run")
    @patch("disk_check.shutil.rmtree")
    def test_do_unmnt(self, mock_rmtree, mock_proc, mock_log):
        global max_log_lvl
        max_log_lvl = -1
        mock_proc.side_effect = mock_subproc_run
        mock_log.side_effect = report_err_msg

        tc = {
            "cmds": [["umount", "-l", "overlay_prefix_etc"]]
        }
        init_tc(tc)

        ret = disk_check.do_unmnt(["/etc"], "overlay_prefix")

        assert ret == 0
        assert cmds == tc["cmds"]
        assert mock_rmtree.call_count == 2


    @classmethod
    def teardown_class(cls):
        subprocess.run(["rm", "-rf", "/tmp/tmpx", "/tmp/tmpy"])  # cleanup the temporary dirs
        print("TEARDOWN")
