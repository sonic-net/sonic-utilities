mock_json_op = \
    [
        {
            "name": "sdx",
            "kname": "sdx",
            "fstype": "",
            "label": "",
            "mountpoint": "",
            "size": "3965714432",
            "maj:min": "8:0",
            "rm": "0",
            "model": "SMART EUSB",
            "vendor": "SMART EUSB",
            "serial": "SPG200807J1",
            "hctl": "2:0:0:0",
            "tran": "usb",
            "rota": "1",
            "type": "disk",
            "ro": "0",
            "owner": "",
            "group": "",
            "mode": "brw-rw----",
            "children": [
                {
                    "name": "sdx1",
                    "kname": "sdx1",
                    "fstype": "ext4",
                    "label": "",
                    "mountpoint": "/host",
                    "size": "3964665856",
                    "maj:min": "8:1",
                    "rm": "0",
                    "model": " ",
                    "vendor": " ",
                    "serial": "",
                    "hctl": "",
                    "tran": "",
                    "rota": "1",
                    "type": "part",
                    "ro": "0",
                    "owner": "",
                    "group": "",
                    "mode": "brw-rw----",
                    "children": [],
                    "parents": ["sdx"],
                    "statistics": {
                        "major": "8",
                        "minor": "1",
                        "kname": "sdx1",
                        "reads_completed": "22104",
                        "reads_merged": "5299",
                        "sectors_read": "1091502",
                        "time_spent_reading_ms": "51711",
                        "writes_completed": "11283",
                        "writes_merged": "13401",
                        "sectors_written": "443784",
                        "time_spent_ writing": "133398",
                        "ios_in_progress": "0",
                        "time_spent_doing_ios_ms": "112040",
                        "weighted_time_ios_ms": "112040",
                    },
                }
            ],
            "parents": [],
            "statistics": {
                "major": "8",
                "minor": "0",
                "kname": "sdx",
                "reads_completed": "22151",
                "reads_merged": "5299",
                "sectors_read": "1093606",
                "time_spent_reading_ms": "52005",
                "writes_completed": "11283",
                "writes_merged": "13401",
                "sectors_written": "443784",
                "time_spent_ writing": "133398",
                "ios_in_progress": "0",
                "time_spent_doing_ios_ms": "112220",
                "weighted_time_ios_ms": "112220",
            },
        }
    ]


class BlkDiskInfo:
    def __init__(self):
        return

    def get_disks(self, filters):
        return mock_json_op
