#!/usr/bin/env python3
"""
Pre-warm-reboot GR timer fix.

1. Sets bgp_timer in WARM_RESTART|bgp (fpmsyncd reconciliation timer, default 120s → 360s)
2. Patches constants.yml (GR restart-time 240s → 360s) on current + next-boot images
3. Updates running FRR GR restart-time + staggered peer reset (first run only)

First invocation: updates timers + staggered peer reset (one at a time, ECMP-safe).
Subsequent invocations: no-op (all values already at target).

Usage:
    sudo python3 /usr/local/bin/warm-reboot-gr-fix.py
"""

import json
import logging
import os
import subprocess
import sys
import time

import yaml

TARGET_GR_RESTART_TIME = 360
TARGET_BGP_TIMER = 360
PEER_ESTABLISH_TIMEOUT = 30
CONSTANTS_PATH = "/etc/sonic/constants.yml"

logger = logging.getLogger("warm-reboot-gr-fix")


def run(cmd, check=True):
    """Run a shell command, return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        logger.error("Command failed: %s\n  stderr: %s", cmd, result.stderr.strip())
        sys.exit(1)
    return result.stdout.strip()


def vtysh(cmd):
    """Run a vtysh command inside bgp container."""
    return run(f'docker exec bgp vtysh -c "{cmd}"')


def vtysh_config(*cmds):
    """Run vtysh config commands inside bgp container."""
    parts = " ".join(f'-c "{c}"' for c in ["conf t"] + list(cmds))
    return run(f"docker exec bgp vtysh {parts}")


def get_current_gr_time():
    """Get current GR restart-time from running config."""
    output = vtysh("show running-config")
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("bgp graceful-restart restart-time"):
            return int(line.split()[-1])
    return None


def get_asn():
    """Get BGP ASN from SONiC config."""
    output = run('sonic-cfggen -d -v "DEVICE_METADATA.localhost.bgp_asn"')
    return output.strip()


def get_peers():
    """Get unique list of BGP peer addresses."""
    output = vtysh("show bgp summary json")
    data = json.loads(output)
    peers = set()
    for af_data in data.values():
        if isinstance(af_data, dict) and "peers" in af_data:
            peers.update(af_data["peers"].keys())
    return sorted(peers)


def get_peer_state(peer):
    """Get BGP state for a single peer."""
    output = vtysh(f"show bgp neighbor {peer} json")
    data = json.loads(output)
    for info in data.values():
        return info.get("bgpState", "")
    return ""


def wait_for_established(peer, timeout=PEER_ESTABLISH_TIMEOUT):
    """Wait for a peer to reach Established state."""
    for _ in range(timeout):
        if get_peer_state(peer) == "Established":
            return True
        time.sleep(1)
    return False


def update_gr_timer(asn):
    """Update GR restart-time and reset peers one at a time."""
    logger.info("Updating GR restart-time to %ds...", TARGET_GR_RESTART_TIME)
    vtysh_config(f"router bgp {asn}", f"bgp graceful-restart restart-time {TARGET_GR_RESTART_TIME}")

    peers = get_peers()
    logger.info("Resetting %d peers (staggered, one at a time)...", len(peers))

    for i, peer in enumerate(peers, 1):
        logger.info("  [%d/%d] Resetting %s...", i, len(peers), peer)
        vtysh(f"clear bgp {peer}")
        if wait_for_established(peer):
            logger.info("  [%d/%d] %s: Established", i, len(peers), peer)
        else:
            logger.warning("  [%d/%d] %s: not Established after %ds, continuing",
                           i, len(peers), peer, PEER_ESTABLISH_TIMEOUT)


# --- constants.yml persistence ---

def get_image_dirs():
    """Get list of image directories under /host/."""
    dirs = []
    for entry in os.listdir("/host"):
        if entry.startswith("image-"):
            dirs.append(os.path.join("/host", entry))
    return dirs


def patch_constants_yml(target_path):
    """Patch constants.yml at target_path to set GR restart-time."""
    file_exists = os.path.exists(target_path)
    if file_exists:
        with open(target_path, "r") as f:
            data = yaml.safe_load(f)
    else:
        # Read from squashfs (current running copy) as template
        with open(CONSTANTS_PATH, "r") as f:
            data = yaml.safe_load(f)

    # Navigate/create the nested structure
    constants = data.setdefault("constants", {})
    bgp = constants.setdefault("bgp", {})
    gr = bgp.setdefault("graceful_restart", {})

    current = gr.get("restart_time")
    if current == TARGET_GR_RESTART_TIME and file_exists:
        return False  # already patched and file exists on disk

    gr["restart_time"] = TARGET_GR_RESTART_TIME
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return True


def patch_all_images():
    """Patch constants.yml in current and next-boot image overlays."""
    patched = []

    # Patch current running system (takes effect on next bgp container restart/reboot)
    if patch_constants_yml(CONSTANTS_PATH):
        patched.append("current")

    # Patch all image rw layers (covers next-boot regardless of which image)
    for image_dir in get_image_dirs():
        rw_constants = os.path.join(image_dir, "rw", "etc", "sonic", "constants.yml")
        if patch_constants_yml(rw_constants):
            patched.append(os.path.basename(image_dir))

    if patched:
        logger.info("Patched constants.yml (restart_time=%ds) in: %s",
                     TARGET_GR_RESTART_TIME, ", ".join(patched))
    else:
        logger.info("constants.yml already has restart_time=%ds in all images",
                     TARGET_GR_RESTART_TIME)


def set_bgp_timer():
    """Set fpmsyncd warm-restart timer in CONFIG_DB to prevent stale route deletion."""
    current = run('sonic-db-cli CONFIG_DB HGET "WARM_RESTART|bgp" "bgp_timer"', check=False)
    if current == str(TARGET_BGP_TIMER):
        logger.info("bgp_timer already %ds in WARM_RESTART|bgp", TARGET_BGP_TIMER)
        return
    run(f'sonic-db-cli CONFIG_DB HSET "WARM_RESTART|bgp" "bgp_timer" "{TARGET_BGP_TIMER}"')
    logger.info("Set WARM_RESTART|bgp bgp_timer=%ds", TARGET_BGP_TIMER)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%b %d %H:%M:%S",
    )

    # 0. Set fpmsyncd warm-restart timer (prevents T0 stale route deletion)
    set_bgp_timer()

    # 1. Patch constants.yml for persistence across reboots
    patch_all_images()

    # 2. Update running FRR config for immediate effect
    current_gr = get_current_gr_time()
    logger.info("Current running GR restart-time: %s", current_gr)

    if current_gr != TARGET_GR_RESTART_TIME:
        asn = get_asn()
        update_gr_timer(asn)
    else:
        logger.info("GR restart-time already %ds, skipping peer reset", TARGET_GR_RESTART_TIME)

    logger.info("Done.")


if __name__ == "__main__":
    main()
