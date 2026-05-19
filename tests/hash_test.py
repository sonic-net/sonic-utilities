import pytest
import os
import logging
import show.main as show
import config.main as config


from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector
from .hash_input import assert_show_output


test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "hash_input")
mock_config_path = os.path.join(input_path, "mock_config")
mock_state_path = os.path.join(input_path, "mock_state")

PKTTYPE_STATE_DB = os.path.join(mock_state_path, "pkttype_ecmp_and_lag")

logger = logging.getLogger(__name__)


HASH_FIELD_LIST = [
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT"
]
INNER_HASH_FIELD_LIST = [
    "INNER_DST_MAC",
    "INNER_SRC_MAC",
    "INNER_ETHERTYPE",
    "INNER_IP_PROTOCOL",
    "INNER_DST_IP",
    "INNER_SRC_IP",
    "INNER_L4_DST_PORT",
    "INNER_L4_SRC_PORT"
]

HASH_ALGORITHM = [
    "CRC",
    "XOR",
    "RANDOM",
    "CRC_32LO",
    "CRC_32HI",
    "CRC_CCITT",
    "CRC_XOR"
]

PKT_TYPE_LIST = [
    "ipv4",
    "ipv6",
    "ipnip",
    "ipv4_rdma",
    "ipv6_rdma"
]

RDMA_HASH_FIELD_LIST = [
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT",
    "RDMA_BTH_OPCODE",
    "RDMA_BTH_DEST_QP"
]

SUCCESS = 0
ERROR2 = 2


class TestHash:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "ecmp_and_lag")

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))


    ########## CONFIG SWITCH-HASH GLOBAL ##########


    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    @pytest.mark.parametrize(
        "args", [
            pytest.param(
                " ".join(HASH_FIELD_LIST),
                id="outer-frame"
            ),
            pytest.param(
                " ".join(INNER_HASH_FIELD_LIST),
                id="inner-frame"
            )
        ]
    )
    def test_config_hash(self, hash, args):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            [hash] + args.split(), obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    @pytest.mark.parametrize(
        "args,pattern", [
            pytest.param(
                "DST_MAC1 SRC_MAC ETHERTYPE",
                "'DST_MAC1' is not one of",
                id="INVALID,SRC_MAC,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC SRC_MAC1 ETHERTYPE",
                "'SRC_MAC1' is not one of",
                id="DST_MAC,INVALID,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC SRC_MAC ETHERTYPE1",
                "'ETHERTYPE1' is not one of",
                id="DST_MAC,SRC_MAC,INVALID"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC ETHERTYPE",
                "duplicate hash field(s) DST_MAC",
                id="DUPLICATE,SRC_MAC,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC SRC_MAC ETHERTYPE",
                "duplicate hash field(s) DST_MAC, SRC_MAC",
                id="DUPLICATE,DUPLICATE,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC SRC_MAC ETHERTYPE ETHERTYPE",
                "duplicate hash field(s) DST_MAC, SRC_MAC, ETHERTYPE",
                id="DUPLICATE,DUPLICATE,DUPLICATE"
            )
        ]
    )
    def test_config_hash_neg(self, hash, args, pattern):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            [hash] + args.split(), obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert pattern in result.output
        assert result.exit_code == ERROR2

    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash-algorithm",
            "lag-hash-algorithm"
        ]
    )
    @pytest.mark.parametrize(
        "arg", HASH_ALGORITHM
    )
    def test_config_hash_algorithm(self, hash, arg):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            [hash, arg], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash-algorithm",
            "lag-hash-algorithm"
        ]
    )
    @pytest.mark.parametrize(
        "arg,pattern", [
            pytest.param(
                "CRC1",
                "'CRC1' is not one of",
                id="INVALID"
            )
        ]
    )
    def test_config_hash_algorithm_neg(self, hash, arg, pattern):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"],
            [hash, arg], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert pattern in result.output
        assert result.exit_code == ERROR2


    ########## SHOW SWITCH-HASH GLOBAL ##########


    @pytest.mark.parametrize(
        "cfgdb,output", [
            pytest.param(
                os.path.join(mock_config_path, "empty"),
                {
                    "plain": assert_show_output.show_hash_empty,
                    "json": assert_show_output.show_hash_empty
                },
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_config_path, "ecmp"),
                {
                    "plain": assert_show_output.show_hash_ecmp,
                    "json": assert_show_output.show_hash_ecmp_json
                },
                id="ecmp"
            ),
            pytest.param(
                os.path.join(mock_config_path, "lag"),
                {
                    "plain": assert_show_output.show_hash_lag,
                    "json": assert_show_output.show_hash_lag_json
                },
                id="lag"
            ),
            pytest.param(
                os.path.join(mock_config_path, "ecmp_and_lag"),
                {
                    "plain": assert_show_output.show_hash_ecmp_and_lag,
                    "json": assert_show_output.show_hash_ecmp_and_lag_json
                },
                id="all"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_hash(self, cfgdb, output, format):
        dbconnector.dedicated_dbs["CONFIG_DB"] = cfgdb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["global"] + ([] if format == "plain" else ["--json"]), obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output[format]
        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "statedb,output", [
            pytest.param(
                os.path.join(mock_state_path, "no_capabilities"),
                {
                    "plain": assert_show_output.show_hash_capabilities_no,
                    "json": assert_show_output.show_hash_capabilities_no_json
                },
                id="no"
            ),
            pytest.param(
                os.path.join(mock_state_path, "not_applicable"),
                {
                    "plain": assert_show_output.show_hash_capabilities_na,
                    "json": assert_show_output.show_hash_capabilities_na_json
                },
                id="na"
            ),
            pytest.param(
                os.path.join(mock_state_path, "empty"),
                {
                    "plain": assert_show_output.show_hash_capabilities_empty,
                    "json": assert_show_output.show_hash_capabilities_empty_json
                },
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_state_path, "ecmp"),
                {
                    "plain": assert_show_output.show_hash_capabilities_ecmp,
                    "json": assert_show_output.show_hash_capabilities_ecmp_json
                },
                id="ecmp"
            ),
            pytest.param(
                os.path.join(mock_state_path, "lag"),
                {
                    "plain": assert_show_output.show_hash_capabilities_lag,
                    "json": assert_show_output.show_hash_capabilities_lag_json
                },
                id="lag"
            ),
            pytest.param(
                os.path.join(mock_state_path, "ecmp_and_lag"),
                {
                    "plain": assert_show_output.show_hash_capabilities_ecmp_and_lag,
                    "json": assert_show_output.show_hash_capabilities_ecmp_and_lag_json
                },
                id="all"
            )
        ]
    )
    @pytest.mark.parametrize(
        "format", [
            "plain",
            "json",
        ]
    )
    def test_show_hash_capabilities(self, statedb, output, format):
        dbconnector.dedicated_dbs["STATE_DB"] = statedb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"],
            ["capabilities"] + ([] if format == "plain" else ["--json"]), obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output[format]
        assert result.exit_code == SUCCESS

    # ========== CONFIG PKT-TYPE SWITCH HASH ==========
    @pytest.mark.parametrize(
        "hash_cmd", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    @pytest.mark.parametrize(
        "pkt_type", PKT_TYPE_LIST
    )
    @pytest.mark.parametrize(
        "action", [
            "add",
            "del"
        ]
    )
    @pytest.mark.parametrize(
        "args", [
            pytest.param(
                " ".join(RDMA_HASH_FIELD_LIST),
                id="pkt-type"
            )
        ]
    )
    def test_config_hash_packet_type(self, hash_cmd, pkt_type, action, args):
        """Test packet-type add/del for ecmp-hash and lag-hash."""
        # use pkt-type capable STATE_DB
        dbconnector.dedicated_dbs["STATE_DB"] = PKTTYPE_STATE_DB

        db = Db()
        runner = CliRunner()

        hash_fields = args.split()
        # Build command arguments using --packet-type and --action options
        cmd_args = ["--packet-type", pkt_type, "--action", action] + hash_fields

        # Invoke the ecmp-hash command; packet-type is handled as an option
        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            cmd_args,
            obj=db
        )
        logger.debug(f"\nCommand: {hash_cmd} {cmd_args}")
        logger.debug(f"Output: {result.output}")
        logger.debug(f"Exit code: {result.exit_code}")

        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize("hash_cmd, attr_prefix", [
        pytest.param("ecmp-hash", "ecmp_hash_", id="ecmp"),
        pytest.param("lag-hash",  "lag_hash_",  id="lag"),
    ])
    @pytest.mark.parametrize("pkt_type", PKT_TYPE_LIST)
    def test_config_hash_pkt_type_add_incremental(self, hash_cmd, attr_prefix, pkt_type):
        """
        Incremental packet-type add behavior:

        a) Add base fields: DST_MAC, SRC_MAC, ETHERTYPE
        b) Add IP_PROTOCOL -> it should be appended to the existing list
        c) Add existing field again (SRC_MAC) -> command should succeed,
           but CONFIG_DB should not change (no duplicate, idempotent).
        """
        # use pkt-type capable STATE_DB
        dbconnector.dedicated_dbs["STATE_DB"] = PKTTYPE_STATE_DB

        db = Db()
        runner = CliRunner()

        base_fields = ["DST_MAC", "SRC_MAC", "ETHERTYPE"]
        extra_field = "IP_PROTOCOL"
        duplicate_field = "SRC_MAC"

        # 1) Initial add
        add1_cmd = ["--packet-type", pkt_type, "--action", "add"] + base_fields
        res1 = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            add1_cmd,
            obj=db,
        )
        logger.debug(f"\nADD1 Command: {hash_cmd} {add1_cmd}")
        logger.debug(f"Output: {res1.output}")
        logger.debug(f"Exit code: {res1.exit_code}")
        assert res1.exit_code == SUCCESS

        # 2) Add an extra field (should append only if missing)
        add2_cmd = ["--packet-type", pkt_type, "--action", "add", extra_field]
        res2 = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            add2_cmd,
            obj=db,
        )
        logger.debug(f"\nADD2 Command: {hash_cmd} {add2_cmd}")
        logger.debug(f"Output: {res2.output}")
        logger.debug(f"Exit code: {res2.exit_code}")
        assert res2.exit_code == SUCCESS

        # Snapshot CONFIG_DB after ADD2
        global_entry_after_add2 = db.cfgdb.get_entry("SWITCH_HASH", "GLOBAL")
        pkt_key = pkt_type.lower()
        attr_name = f"{attr_prefix}{pkt_key}"
        logger.debug(f"Looking for attribute: {attr_name}")
        logger.debug(f"CONFIG_DB GLOBAL entry: {global_entry_after_add2}")
        value_after_add2 = global_entry_after_add2.get(attr_name, "")
        logger.debug(f"Raw value from CONFIG_DB: '{value_after_add2}'")
        fields_after_add2 = value_after_add2.split(",") if value_after_add2 else []
        logger.debug(f"Parsed fields: {fields_after_add2}")

        # Expect base fields plus extra_field, no duplicates, order preserved
        expected_after_add2 = base_fields + [extra_field]
        assert fields_after_add2 == expected_after_add2

        # 3) Re-add an existing field (duplicate); should succeed but not change CONFIG_DB
        add3_cmd = ["--packet-type", pkt_type, "--action", "add", duplicate_field]
        res3 = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            add3_cmd,
            obj=db,
        )
        logger.debug(f"\nADD3 Command: {hash_cmd} {add3_cmd}")
        logger.debug(f"Output: {res3.output}")
        logger.debug(f"Exit code: {res3.exit_code}")
        assert res3.exit_code == SUCCESS

        global_entry_after_add3 = db.cfgdb.get_entry("SWITCH_HASH", "GLOBAL")
        value_after_add3 = global_entry_after_add3.get(attr_name, "")
        fields_after_add3 = value_after_add3.split(",") if value_after_add3 else []

        # No-op: CONFIG_DB should remain identical to state after ADD2
        assert fields_after_add3 == fields_after_add2

    @pytest.mark.parametrize(
        "hash_cmd, attr_prefix",
        [
            pytest.param("ecmp-hash", "ecmp_hash_", id="ecmp"),
            pytest.param("lag-hash",  "lag_hash_",  id="lag"),
        ],
    )
    @pytest.mark.parametrize(
        "pkt_type", PKT_TYPE_LIST
    )
    @pytest.mark.parametrize(
        "delete_fields", [
            pytest.param(
                [],  # no args -> delete whole entry
                id="del-no-args-delete-entry"
            ),
            pytest.param(
                ["DST_MAC", "SRC_MAC"],  # delete subset only
                id="del-specific-fields"
            ),
        ]
    )
    def test_config_hash_pkt_type_del_variants(self, hash_cmd, attr_prefix, pkt_type, delete_fields):
        """packet-type del: no args deletes entry, args delete only specific fields (ECMP & LAG)."""
        # use pkt-type capable STATE_DB
        dbconnector.dedicated_dbs["STATE_DB"] = PKTTYPE_STATE_DB

        db = Db()
        runner = CliRunner()

        # 1) Add full set of fields first
        add_args = " ".join(HASH_FIELD_LIST)
        add_cmd = ["--packet-type", pkt_type, "--action", "add"] + add_args.split()
        add_result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            add_cmd,
            obj=db,
        )
        logger.debug(f"\nADD Command: {hash_cmd} {add_cmd}")
        logger.debug(f"Output: {add_result.output}")
        logger.debug(f"Exit code: {add_result.exit_code}")
        assert add_result.exit_code == SUCCESS

        # 2) Run delete variant
        del_cmd = ["--packet-type", pkt_type, "--action", "del"] + delete_fields
        del_result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            del_cmd,
            obj=db,
        )
        logger.debug(f"\nDEL Command: {hash_cmd} {del_cmd}")
        logger.debug(f"Output: {del_result.output}")
        logger.debug(f"Exit code: {del_result.exit_code}")
        assert del_result.exit_code == SUCCESS

        # 3) Validate CONFIG_DB state (GLOBAL row with per-pkt-type attr)
        global_entry = db.cfgdb.get_entry("SWITCH_HASH", "GLOBAL")
        pkt_key = pkt_type.lower()
        attr_name = f"{attr_prefix}{pkt_key}"
        logger.debug(
            f"GLOBAL entry after delete for {hash_cmd}, {pkt_type}, "
            f"delete_fields={delete_fields}: {global_entry}"
        )

        if not delete_fields:
            # No ARGS -> entire packet-type attribute should be gone
            assert attr_name not in global_entry or not global_entry.get(attr_name)
            return

        value = global_entry.get(attr_name)
        if not value:
            # If attribute is gone here, it means delete_fields covered all fields
            assert set(delete_fields) == set(HASH_FIELD_LIST)
            return

        remaining = value
        if isinstance(remaining, str):
            remaining = remaining.split(",")

        # Ensure deleted fields are not present
        for f in delete_fields:
            assert f not in remaining

        # Ensure other original fields remain
        for f in HASH_FIELD_LIST:
            if f not in delete_fields:
                assert f in remaining

    @pytest.mark.parametrize(
        "pkt_type", PKT_TYPE_LIST
    )
    @pytest.mark.parametrize(
        "cmd_suffix, pattern",
        [
            pytest.param(
                ["bad_action"],  # invalid action
                "'bad_action' is not one of",
                id="invalid-action",
            ),
            pytest.param(
                ["add"],  # add with no ARGS
                "Hash fields are required when --packet-type is specified and --action is not 'del'",
                id="add-no-args",
            ),
            pytest.param(
                # 1) duplicate fields in packet-type mode
                ["add", "DST_MAC", "DST_MAC", "SRC_MAC", "ETHERTYPE"],
                "duplicate hash field(s) DST_MAC",
                id="pkt-type-duplicate-fields",
            ),
            pytest.param(
                # 2) invalid field in packet-type mode
                ["add", "DST_MAC1", "SRC_MAC", "ETHERTYPE"],
                "'DST_MAC1' is not one of",
                id="pkt-type-invalid-field",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "hash_cmd",
        [
            "ecmp-hash",
            "lag-hash",
        ],
    )
    def test_config_hash_pkt_type_negative(self, hash_cmd, pkt_type, cmd_suffix, pattern):
        """
        Negative packet-type tests:
          - invalid action word
          - add with no HASH_FIELDS
          - duplicate fields in packet-type mode
          - invalid hash field in packet-type mode
        """
        # use pkt-type capable STATE_DB
        dbconnector.dedicated_dbs["STATE_DB"] = PKTTYPE_STATE_DB

        db = Db()
        runner = CliRunner()

        # Build command args based on the negative test case
        if cmd_suffix[0] == "bad_action":
            # Test invalid action
            cmd_args = ["--packet-type", pkt_type, "--action", "bad_action"]
        elif cmd_suffix[0] == "add" and len(cmd_suffix) == 1:
            # Test add with no args
            cmd_args = ["--packet-type", pkt_type, "--action", "add"]
        else:
            # Test with hash fields (duplicate or invalid)
            action = cmd_suffix[0]
            fields = cmd_suffix[1:]
            cmd_args = ["--packet-type", pkt_type, "--action", action] + fields

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            cmd_args,
            obj=db,
        )

        logger.debug(f"\nCommand: {hash_cmd} {cmd_args}")
        logger.debug(f"Output: {result.output}")
        logger.debug(f"Exit code: {result.exit_code}")

        assert pattern in result.output
        assert result.exit_code == ERROR2

    @pytest.mark.parametrize(
        "state_db_file, hash_cmd, pkt_type, args, expected_pattern",
        [
            # 1) pkt-type capability disabled
            pytest.param(
                os.path.join(mock_state_path, "pkttype_disabled"),
                "ecmp-hash",
                "ipv4",
                " ".join(RDMA_HASH_FIELD_LIST),
                "packet-type operation is not supported",
                id="pkt-type-capability-disabled",
            ),
            # 2) pkt-type not in supported list
            pytest.param(
                os.path.join(mock_state_path, "pkttype_limited"),
                "ecmp-hash",
                "ipnip",
                " ".join(RDMA_HASH_FIELD_LIST),
                "packet-type IPNIP is not supported",
                id="pkt-type-not-in-list",
            ),
            # 3) field not supported by HASH_FIELD_LIST in pkt-type mode
            pytest.param(
                os.path.join(mock_state_path, "pkttype_limited_fields"),
                "ecmp-hash",
                "ipv4_rdma",
                " ".join(RDMA_HASH_FIELD_LIST),
                "'RDMA_BTH_DEST_QP' is not one of",
                id="pkt-type-field-not-supported",
            ),
        ],
    )
    def test_config_hash_pkt_type_capability_validation(
        self, state_db_file, hash_cmd, pkt_type, args, expected_pattern
    ):
        """
        Extra negative coverage for packet-type config:

        1) pkt-type capability disabled
        2) pkt-type not present in capability list
        3) field not allowed by HASH_FIELD_LIST in pkt-type mode
        """
        dbconnector.dedicated_dbs["STATE_DB"] = state_db_file

        db = Db()
        runner = CliRunner()

        cmd_args = ["--packet-type", pkt_type, "--action", "add"] + args.split()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            cmd_args,
            obj=db,
        )

        logger.debug(f"\nCommand: {hash_cmd} {cmd_args}")
        logger.debug(f"Output: {result.output}")
        logger.debug(f"Exit code: {result.exit_code}")

        assert expected_pattern in result.output
        assert result.exit_code == ERROR2

    @pytest.mark.parametrize("hash_cmd, attr_prefix", [
        pytest.param("ecmp-hash", "ecmp_hash_", id="ecmp"),
        pytest.param("lag-hash",  "lag_hash_",  id="lag"),
    ])
    @pytest.mark.parametrize("pkt_type", PKT_TYPE_LIST)
    def test_config_hash_pkt_type_overwrite_without_action(self, hash_cmd, attr_prefix, pkt_type):
        """When --packet-type is given without --action, hash fields overwrite existing list."""
        # use pkt-type capable STATE_DB
        dbconnector.dedicated_dbs["STATE_DB"] = PKTTYPE_STATE_DB

        db = Db()
        runner = CliRunner()

        # Initial list configured via explicit add (merge semantics)
        initial_fields = ["DST_MAC", "SRC_MAC"]
        add_cmd = ["--packet-type", pkt_type, "--action", "add"] + initial_fields
        res_add = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            add_cmd,
            obj=db,
        )
        logger.debug(f"\nInitial ADD Command: {hash_cmd} {add_cmd}")
        logger.debug(f"Output: {res_add.output}")
        logger.debug(f"Exit code: {res_add.exit_code}")
        assert res_add.exit_code == SUCCESS

        # Overwrite list using --packet-type without --action
        overwrite_fields = ["ETHERTYPE", "IP_PROTOCOL"]
        overwrite_cmd = ["--packet-type", pkt_type] + overwrite_fields
        res_overwrite = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].commands[hash_cmd],
            overwrite_cmd,
            obj=db,
        )
        logger.debug(f"\nOverwrite Command: {hash_cmd} {overwrite_cmd}")
        logger.debug(f"Output: {res_overwrite.output}")
        logger.debug(f"Exit code: {res_overwrite.exit_code}")
        assert res_overwrite.exit_code == SUCCESS

        # Validate that CONFIG_DB now contains exactly overwrite_fields for this pkt_type
        global_entry = db.cfgdb.get_entry("SWITCH_HASH", "GLOBAL")
        pkt_key = pkt_type.lower()
        attr_name = f"{attr_prefix}{pkt_key}"
        value = global_entry.get(attr_name, "")
        fields = value.split(",") if value else []

        assert fields == overwrite_fields

    def test_debug_ecmp_hash_binding(self):
        cmd = (
            config.config
            .commands["switch-hash"]
            .commands["global"]
            .commands["ecmp-hash"]
        )
        print("ecmp-hash callback:", cmd.callback, "module:", cmd.callback.__module__)

    # ========== SHOW SWITCH-HASH GLOBAL --packet-type ==========

    def test_show_hash_packet_type_option_valid(self):
        """
        Valid case: `show switch-hash global --packet-type ipv4` must be
        accepted by the `--packet-type` Click option and exit successfully.
        """
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ecmp_and_lag")

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"].commands["global"],
            ["--packet-type", "ipv4"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    def test_show_hash_packet_type_option_invalid(self):
        """
        Invalid case: an unsupported `--packet-type` value must be rejected
        by Click's Choice validation with a non-zero exit code.
        """
        dbconnector.dedicated_dbs["CONFIG_DB"] = os.path.join(mock_config_path, "ecmp_and_lag")

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"].commands["global"],
            ["--packet-type", "ipv7"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert "'ipv7' is not one of" in result.output
        assert result.exit_code == ERROR2
