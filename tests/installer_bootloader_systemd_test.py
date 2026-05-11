import pathlib
from unittest.mock import patch

from sonic_installer.bootloader import systemd_boot
from sonic_sdboot_utils import sdboot_config


def create_sdboot_config(version: str, image_dir: str):
  return sdboot_config.SdbootConfig(
      title="ignored title",
      version=version,
      sort_key=((1 << 64) - 1),
      linux=pathlib.Path("dev/null"),
      initrd=pathlib.Path("dev/null"),
      options=["rw"],
      image_dir=pathlib.Path(image_dir),
  )


@patch("sonic_sdboot_utils.sdboot_config.find_configs")
def test_get_image_path_happy_path_one_entry(fc_mock):
  fc_mock.side_effect = [
      {"sonic_a": create_sdboot_config("cool-version", "image-A")}
  ]
  bootloader = systemd_boot.SystemdBootBootloader()
  assert bootloader.get_image_path("cool-version") == pathlib.Path(
      "/host/image-A"
  )


@patch("sonic_sdboot_utils.sdboot_config.find_configs")
def test_get_image_path_happy_path_one_entry_with_prefix(fc_mock):
  fc_mock.side_effect = [
      {"sonic_a": create_sdboot_config("cool-version", "image-A")}
  ]
  bootloader = systemd_boot.SystemdBootBootloader()
  assert bootloader.get_image_path("SONiC-OS-cool-version") == pathlib.Path(
      "/host/image-A"
  )


@patch("sonic_sdboot_utils.sdboot_config.find_configs")
def test_get_image_path_happy_path_two_entries(fc_mock):
  fc_mock.side_effect = [{
      "sonic_a": create_sdboot_config("cool-version", "image-A"),
      "sonic_b": create_sdboot_config("lame-version", "image-B"),
  }]
  bootloader = systemd_boot.SystemdBootBootloader()
  assert bootloader.get_image_path("lame-version") == pathlib.Path(
      "/host/image-B"
  )


@patch("sonic_sdboot_utils.sdboot_config.find_configs")
def test_get_image_path_happy_path_two_entries_with_prefix(fc_mock):
  fc_mock.side_effect = [{
      "sonic_a": create_sdboot_config("cool-version", "image-A"),
      "sonic_b": create_sdboot_config("lame-version", "image-B"),
  }]
  bootloader = systemd_boot.SystemdBootBootloader()
  assert bootloader.get_image_path("SONiC-OS-lame-version") == pathlib.Path(
      "/host/image-B"
  )
