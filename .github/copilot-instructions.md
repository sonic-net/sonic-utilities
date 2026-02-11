# Copilot Instructions for sonic-utilities

## Project Overview

sonic-utilities provides the command-line interface (CLI) for SONiC switches. It includes `show`, `config`, `clear`, and other commands that network operators use to configure and monitor SONiC devices. This is the primary user-facing component of SONiC — every CLI command a user types goes through this repo.

## Architecture

```
sonic-utilities/
├── config/              # 'config' command group — write CONFIG_DB
│   ├── main.py          # Main config CLI entry point
│   ├── vlan.py          # VLAN configuration
│   ├── interface.py     # Interface configuration
│   └── ...
├── show/                # 'show' command group — read and display state
│   ├── main.py
│   └── ...
├── clear/               # 'clear' command group
├── scripts/             # Standalone CLI scripts
├── acl_loader/          # ACL loading utilities
├── crm/                 # Critical Resource Monitoring CLI
├── counterpoll/         # Counter polling configuration
├── fwutil/              # Firmware update utility
├── pfc/pfcwd/           # Priority Flow Control utilities
├── generic_config_updater/ # GCU (Generic Config Updater) / patch apply
├── gcu/                 # GCU commands
├── dump/                # State dump utilities
├── rcli/                # Remote CLI
├── utilities_common/    # Shared utility functions
├── tests/               # pytest unit tests
│   └── mock_tables/     # Mock Redis data for testing
├── setup.py             # Package setup
└── doc/                 # Documentation
```

### Key Concepts
- **Click framework**: All CLI commands use the Python Click library
- **CONFIG_DB interaction**: Config commands write to Redis CONFIG_DB
- **Show commands**: Read from various Redis DBs (STATE_DB, COUNTERS_DB, APP_DB)
- **Yang models**: Configuration is validated against YANG models (sonic-yang-models)

## Language & Style

- **Primary language**: Python 3
- **Framework**: Click (command-line interface framework)
- **Indentation**: 4 spaces
- **Naming conventions**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - CLI command names: `kebab-case` (e.g., `show interfaces status`)
  - Constants: `UPPER_CASE`
- **Imports**: Standard library → third-party → local, each group separated by blank line
- **Docstrings**: Use for all public functions
- **String formatting**: Prefer f-strings

## Build Instructions

```bash
# Build Python wheel
python3 setup.py bdist_wheel

# Install for development
pip3 install -e .

# Recommended: Build inside sonic-buildimage slave container
# (handles all SONiC-specific dependencies automatically)
make configure PLATFORM=generic
make -f Makefile.work BLDENV=bookworm KEEP_SLAVE_ON=yes \
  target/python-wheels/bookworm/sonic_utilities-1.2-py3-none-any.whl
```

## Testing

```bash
# Run all tests
python3 setup.py test
# Or using pytest directly
pytest tests/ -v

# Run specific test
pytest tests/config_test.py -v -k "test_vlan"

# Tests with coverage
pytest tests/ --cov=config --cov=show --cov-report=term-missing
```

### Test Structure
- Tests are in `tests/` directory using **pytest**
- **Mock tables**: `tests/mock_tables/` contains mock Redis DB data
- Tests mock the `SonicV2Connector` / `ConfigDBConnector` to avoid needing a real Redis
- Use `click.testing.CliRunner` to test CLI commands
- New CLI commands MUST have corresponding tests

### Writing Tests
```python
from click.testing import CliRunner
from config.main import config

def test_my_config_command():
    runner = CliRunner()
    result = runner.invoke(config, ['my-feature', 'enable'])
    assert result.exit_code == 0
    assert 'Success' in result.output
```

## PR Guidelines

- **Commit format**: `[component]: Description` (e.g., `[config/vlan]: Add VLAN range support`)
- **Signed-off-by**: REQUIRED (`git commit -s`)
- **CLA**: Sign Linux Foundation EasyCLA
- **Testing**: All new commands MUST have unit tests
- **Backwards compatibility**: Don't break existing CLI command syntax
- **Yang validation**: New config commands should validate against YANG models

## Common Patterns

### Adding a New Show Command
```python
import click
from tabulate import tabulate

@show.group()
def my_feature():
    """Show my feature information"""
    pass

@my_feature.command()
def status():
    """Show my feature status"""
    db = SonicV2Connector()
    db.connect(db.STATE_DB)
    # Read data and format output
    click.echo(tabulate(data, headers))
```

### Adding a New Config Command
```python
@config.group()
def my_feature():
    """Configure my feature"""
    pass

@my_feature.command()
@click.argument('value')
def set(value):
    """Set my feature value"""
    db = ConfigDBConnector()
    db.connect()
    db.mod_entry('MY_TABLE', 'key', {'field': value})
```

### Database Access Patterns
- `ConfigDBConnector` — for CONFIG_DB reads/writes
- `SonicV2Connector` — for multi-database access
- Always use `utilities_common` helper functions where available

## Dependencies

- **sonic-py-common**: Common Python utilities
- **sonic-config-engine**: Configuration rendering
- **sonic-yang-models**: YANG model definitions for validation
- **python-swsscommon**: Python bindings for swss-common
- **Click**: CLI framework
- **tabulate**: Table formatting for show commands
- **natsort**: Natural sorting

## Gotchas

- **Mock tables must match real DB schema**: When writing tests, ensure mock data reflects actual CONFIG_DB/STATE_DB structure
- **Multi-ASIC support**: Commands must work on both single-ASIC and multi-ASIC platforms; use `multi_asic` utilities
- **YANG validation**: config commands may fail if YANG models aren't updated for new fields
- **Click context**: Use `click.pass_context` properly for nested command groups
- **Output format**: Show commands should use consistent formatting (tabulate); don't invent new formats
- **Backwards compatibility**: Never change existing command syntax without a deprecation path
- **DB schema dependencies**: If you add a new CONFIG_DB table, update sonic-yang-models too
- **Testing without SONiC**: Unit tests must work without a real SONiC environment — mock all DB access
