from pathlib import Path


def test_generate_dump_includes_fwutil_status():
    contents = Path("scripts/generate_dump").read_text(encoding="utf-8")
    assert 'save_cmd "fwutil show status" "fwutil.show.status"' in contents
