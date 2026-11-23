import os
import re
import subprocess
from pathlib import Path

import pytest


ASIC_CONFIG_CHECK = Path(__file__).parents[1] / "scripts" / "asic_config_check"
LEGACY = "1" * 40
SHA256 = "a" * 64


def _run_check(tmp_path, current, destination, same_image=False):
    current_config = tmp_path / "current"
    destination_root = tmp_path / "destination"
    for config_dir, checksums in (
        (current_config, current),
        (destination_root / "etc" / "sonic", destination),
    ):
        config_dir.mkdir(parents=True)
        for suffix, checksum in checksums.items():
            (config_dir / f"asic_config_checksum{suffix}").write_text(checksum + "\n")
    (tmp_path / "host" / "image-next").mkdir(parents=True)
    (tmp_path / "tmp").mkdir()

    paths = {
        '"/etc/sonic/': f'"{current_config}/',
        '"/host/': f'"{tmp_path}/host/',
        '"/tmp/': f'"{tmp_path}/tmp/',
        "/tmp/dst_asic_config_checksum": str(tmp_path / "dst_asic_config_checksum"),
    }
    script = re.sub("|".join(re.escape(path) for path in paths),
                    lambda match: paths[match.group()], ASIC_CONFIG_CHECK.read_text())
    driver = r'''
logger() { printf '%s\n' "$*" >&2; }
sonic-installer() {
    printf 'Current: SONiC-OS-current\nNext: SONiC-OS-%s\n' "$NEXT_IMAGE"
}
mount() {
    cp -a "$DESTINATION_ROOT/." "$4/"
    printf 'mount\n' >> "$MOUNT_LOG"
}
umount() { printf 'umount\n' >> "$MOUNT_LOG"; }
''' + script
    env = dict(os.environ, DESTINATION_ROOT=str(destination_root),
               NEXT_IMAGE="current" if same_image else "next",
               MOUNT_LOG=str(tmp_path / "mount.log"))
    return subprocess.run(
        ["bash", "-e", "-c", driver], env=env,
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("current,destination,selected", [
    pytest.param({"": LEGACY}, {"": LEGACY}, LEGACY, id="old-to-old"),
    pytest.param({"": LEGACY, ".sha256": SHA256}, {"": LEGACY}, LEGACY, id="new-to-old"),
    pytest.param({"": LEGACY}, {"": LEGACY, ".sha256": SHA256}, LEGACY, id="old-to-new"),
    pytest.param({"": LEGACY, ".sha256": SHA256}, {"": "2" * 40, ".sha256": SHA256},
                 SHA256, id="prefer-sha256"),
    pytest.param({".sha256": SHA256}, {".sha256": SHA256}, SHA256, id="sha256-only"),
    pytest.param({".sha256": SHA256.upper()}, {".sha256": SHA256}, SHA256, id="hex-case"),
])
def test_strongest_common_checksum(tmp_path, current, destination, selected):
    """Use one common algorithm, preferring SHA-256 over legacy differences."""
    result = _run_check(tmp_path, current, destination)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "dst_asic_config_checksum").read_text() == selected + "\n"
    assert (tmp_path / "mount.log").read_text().splitlines() == ["mount", "umount"]
    assert not (tmp_path / "tmp" / "image-next-fs").exists()


@pytest.mark.parametrize("current,destination", [
    pytest.param({"": LEGACY}, {"": "2" * 40}, id="legacy-mismatch"),
    pytest.param({"": LEGACY, ".sha256": SHA256}, {"": LEGACY, ".sha256": "b" * 64},
                 id="sha256-mismatch-with-matching-legacy"),
])
def test_checksum_mismatch(tmp_path, current, destination):
    """Reject changed content without downgrading a SHA-256 mismatch."""
    result = _run_check(tmp_path, current, destination)

    assert result.returncode == 1
    assert "checksum failed" in result.stderr


@pytest.mark.parametrize("side", ["current", "destination"])
@pytest.mark.parametrize("invalid", ["", "a" * 63, "g" * 64])
def test_invalid_sha256_does_not_fall_back(tmp_path, side, invalid):
    """Reject malformed strong digests even when legacy checksums match."""
    checksums = {
        "current": {"": LEGACY, ".sha256": SHA256},
        "destination": {"": LEGACY, ".sha256": SHA256},
    }
    checksums[side][".sha256"] = invalid
    result = _run_check(tmp_path, checksums["current"], checksums["destination"])

    assert result.returncode == 1
    assert "Invalid SHA-256 ASIC config checksum" in result.stderr
    assert (tmp_path / "mount.log").read_text().splitlines() == ["mount", "umount"]


@pytest.mark.parametrize("current,destination", [
    pytest.param({".sha256": SHA256}, {"": LEGACY}, id="current-has-no-legacy"),
    pytest.param({"": LEGACY}, {".sha256": SHA256}, id="destination-has-no-legacy"),
    pytest.param({"": LEGACY}, {}, id="destination-has-no-checksum"),
])
def test_no_common_checksum(tmp_path, current, destination):
    """Reject incompatible image pairs and clean up the destination mount."""
    result = _run_check(tmp_path, current, destination)

    assert result.returncode == 3
    assert "Compatible ASIC config checksum not found" in result.stderr
    assert (tmp_path / "mount.log").read_text().splitlines() == ["mount", "umount"]
    assert not (tmp_path / "tmp" / "image-next-fs").exists()


@pytest.mark.parametrize("same_image", [False, True])
def test_existing_shortcuts(tmp_path, same_image):
    """Preserve unsupported-current-image and same-image bypasses."""
    current = {".sha256": "invalid"} if same_image else {}
    result = _run_check(tmp_path, current, {".sha256": SHA256}, same_image=same_image)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "mount.log").exists()
