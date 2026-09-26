import re
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
INLINE_PYTHON = re.compile(
    r'\bpython(?:3)?\b(?P<options>[^\n]*?)(?:(?<!\S)-c\b|<<)'
)
ISOLATED_OPTION = re.compile(r'(?<!\S)-I(?!\S)')


@pytest.mark.parametrize('script_name', [
    'generate_dump',
    'reboot',
    'fast-reboot',
    'reboot_smartswitch_helper',
])
def test_inline_python_uses_isolated_mode(script_name):
    script = (SCRIPTS_DIR / script_name).read_text()

    violations = [
        match.group(0)
        for match in INLINE_PYTHON.finditer(script)
        if ISOLATED_OPTION.search(match.group('options')) is None
    ]

    assert violations == []


@pytest.mark.parametrize('command', [
    'python -c "import sys"',
    'python3 -E -c "import sys"',
    'python3 -B -E -c "import sys"',
    'python3 <<EOF',
    'python3 - "$file" <<EOF',
])
def test_non_isolated_inline_python_pattern_catches_intervening_flags(command):
    match = INLINE_PYTHON.search(command)

    assert match is not None
    assert ISOLATED_OPTION.search(match.group('options')) is None


@pytest.mark.parametrize('command', [
    'python3 -I -c "import sys"',
    'python3 -E -I -c "import sys"',
    'python3 -I <<EOF',
    'python3 -I - "$file" <<EOF',
])
def test_isolated_inline_python_pattern_accepts_isolated_mode(command):
    match = INLINE_PYTHON.search(command)

    assert match is not None
    assert ISOLATED_OPTION.search(match.group('options')) is not None
