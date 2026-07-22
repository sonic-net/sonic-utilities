import json
import os
import sys

# Path setup for imports must happen before importing local SONiC modules
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

import show.main as show  # noqa: E402
from click.testing import CliRunner  # noqa: E402
from .utils import get_result_and_return_code  # noqa: E402


class TestPortStatTopN:
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING_IS_SUP"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_IS_PACKET_CHASSIS"] = "0"

    def test_top_default(self):
        """Default invocation: 3 interfaces from mock DB, sorted by total BPS."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            []
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        lines = result.output.strip().splitlines()
        table_rows = [
            line for line in lines if line.strip()
            and not line.startswith('Sampled at')
            and not line.startswith('---')
            and 'RANK' not in line
            and 'IFACE' not in line
        ]
        assert len(table_rows) == 3, f"Expected 3 rows, got {len(table_rows)}: {table_rows}"
        assert 'Ethernet0' in table_rows[0], \
            f"Expected Ethernet0 at rank 1, got: {table_rows[0]}"

    def test_top_custom_count(self):
        """Test -n 2 returns 2 rows; -n 10 returns all 3."""
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['-n', '2']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"
        lines = result.output.strip().splitlines()
        table_rows = [
            line for line in lines if line.strip()
            and not line.startswith('Sampled at')
            and not line.startswith('---')
            and 'RANK' not in line
            and 'IFACE' not in line
        ]
        assert len(table_rows) == 2, f"Expected 2 rows, got {len(table_rows)}: {table_rows}"

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['-n', '10']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"
        lines = result.output.strip().splitlines()
        table_rows = [
            line for line in lines if line.strip()
            and not line.startswith('Sampled at')
            and not line.startswith('---')
            and 'RANK' not in line
            and 'IFACE' not in line
        ]
        assert len(table_rows) == 3, f"Expected 3 rows, got {len(table_rows)}: {table_rows}"

    def test_top_flags(self):
        """Verify --sort and --units flags are routed correctly by Click."""
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['--sort', 'rx']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['--sort', 'util']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['--units', 'pps']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

    def test_top_error_handling(self):
        """Test -n 0 / -n -1 return non-zero exit codes."""
        return_code, result = get_result_and_return_code(['portstat', '-X', '0'])
        assert return_code != 0, f"Expected non-zero exit for -n 0, got {return_code}"
        assert 'positive integer' in result.lower() or 'error' in result.lower(), \
            f"Expected error message for -n 0, got: {result}"

        return_code, result = get_result_and_return_code(['portstat', '-X', '-1'])
        assert return_code != 0, f"Expected non-zero exit for -n -1, got {return_code}"
        assert 'positive integer' in result.lower() or 'error' in result.lower(), \
            f"Expected error message for -n -1, got: {result}"

    def test_top_json_output(self):
        """Test --json output parses via json.loads() with correct structure."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["counters"].commands["top"],
            ['--json']
        )
        assert result.exit_code == 0, f"CLI exited with code {result.exit_code}: {result.output}"

        data = json.loads(result.output)

        assert 'sampled_at' in data, "Missing 'sampled_at' in JSON output"
        assert 'sort_key' in data, "Missing 'sort_key' in JSON output"
        assert 'count' in data, "Missing 'count' in JSON output"
        assert 'interfaces' in data, "Missing 'interfaces' in JSON output"

        assert data['count'] == 3, f"Expected count=3, got {data['count']}"
        assert isinstance(data['interfaces'], list), "'interfaces' should be a list"
        assert len(data['interfaces']) == 3, f"Expected 3 interfaces, got {len(data['interfaces'])}"

        for iface in data['interfaces']:
            for field in ('rx_bps', 'rx_pps', 'tx_bps', 'tx_pps',
                          'total_bps', 'total_pps', 'rx_util_pct', 'tx_util_pct'):
                assert isinstance(iface[field], float), \
                    f"Expected float for {field} in {iface['iface']}, got {type(iface[field])}: {iface[field]}"
