"""Class that encapsulates encoding and decoding Systemd Boot config files."""

import pathlib
import sys
import typing as t
import uuid

from . import utils

_SDBOOT_EFIVAR_UUID = uuid.UUID("4a67b082-0a4c-41cf-b6c7-440b29bb8c4f")
_EFIVARS_PATH = pathlib.Path("/sys/firmware/efi/efivars")


class SdbootEntry:
    """Represents the boot entry itself (irrespective of file contents)."""

    def __init__(self, identifier: str, bootcount: tuple[int, int] | None):
        self.identifier = identifier
        self.bootcount = bootcount

    def to_stem(self) -> str:
        if self.bootcount is None:
            return f"{self.identifier}"
        ndigits = len(str(self.attempts_done))
        rem = f"{self.attempts_left:>0{ndigits}}"
        tot = f"{self.attempts_done:>0{ndigits}}"
        return f"{self.identifier}+{rem}-{tot}"

    @property
    def attempts_left(self) -> int | None:
        return None if self.bootcount is None else self.bootcount[0]

    @property
    def attempts_done(self) -> int | None:
        return None if self.bootcount is None else self.bootcount[1]

    def is_bad(self) -> bool:
        if (attempts := self.attempts_left) is None:
            return False
        else:
            return attempts == 0

    @classmethod
    def from_stem(cls, stem: str) -> t.Self:
        if "." in stem:
            raise ValueError(f"{stem} contains a '.'")

        if "+" not in stem:
            return cls(identifier=stem, bootcount=None)
        ident, bootcount = stem.split("+", maxsplit=1)
        countsplit = bootcount.split("-", maxsplit=1)

        if len(countsplit) != 2:
            raise ValueError(f"Invalid boot count '{bootcount}'")

        def checkparse(n, name):
            if not n.isdigit():
                raise ValueError(f"Invalid value for {name}: {n}")
            return int(n)

        rem = checkparse(countsplit[0], "remaining")
        tot = checkparse(countsplit[1], "total")

        return cls(identifier=ident, bootcount=(rem, tot))

    @classmethod
    def from_filename(cls, fname: pathlib.Path | str) -> t.Self:
        return cls.from_stem(pathlib.Path(fname).stem)

    def __repr__(self):
        return (
                "SdbootEntry("
                f"identifier={repr(self.identifier)}, "
                f"bootcount={repr(self.bootcount)}"
                ")"
        )

    def __eq__(self, other: t.Self) -> bool:
        def inner():
            yield self.identifier == other.identifier
            yield self.bootcount == other.bootcount

        return all(inner())

    def __hash__(self):
        return hash((self.identifier, self.bootcount))


def set_oneshot(
        entry: SdbootEntry,
        include_bootcount: bool,
        dry_run: bool,
):
    """Sets the boot oneshot to the given entry."""
    ident = "{}.conf".format(
            entry.to_stem() if include_bootcount else entry.identifier
    )
    print(f"Setting oneshot to {ident}")
    utils.run_cmd(["bootctl", "set-oneshot", ident], dry_run=dry_run)


def reset_bootcount(
        bootconf_path: pathlib.Path,
        dry_run: bool,
):
    ok_bootcounts = {None, (1, 0)}
    entry = SdbootEntry.from_filename(bootconf_path)
    if entry.bootcount in ok_bootcounts:
        print(
                f"Not resetting boot count for {bootconf_path}: No need.",
                file=sys.stderr,
        )
        return

    reset_count = None if entry.bootcount is None else (1, 0)
    new_entry = SdbootEntry(entry.identifier, reset_count)
    new_path = bootconf_path.parent / f"{new_entry.to_stem()}.conf"
    print(
        "Reset bootcount: {}->{}".format(bootconf_path, new_path),
        file=sys.stderr,
    )
    if dry_run:
        return
    bootconf_path.rename(new_path)


class SdbootConfig:
    """Class that encapsulates encoding and decoding Systemd Boot config files."""

    def __init__(
            self,
            *,
            title: str,
            version: str,
            sort_key: int,
            linux: pathlib.Path,
            initrd: pathlib.Path,
            options: list[str],
            image_dir: pathlib.Path,
    ):
        def check_rel(path: pathlib.Path) -> pathlib.Path:
            if path.is_absolute():
                raise ValueError(f"{path} is absolute when it should be relative.")
            return path

        self.title = title
        self.version = version
        self.sort_key = sort_key
        self.linux = check_rel(linux)
        self.initrd = check_rel(initrd)
        self.options = options
        self.image_dir = image_dir

    @classmethod
    def from_file(cls, path: pathlib.Path) -> t.Self:
        with open(path) as f:
            lines = map(str.strip, f)
            lines = (line.split(maxsplit=1) for line in lines)
            lines = {key: val for key, val in lines}

        RType = t.TypeVar("RType")

        def get(key: str, rtype: type[RType] = str) -> RType:
            val = lines.get(key)
            if val is None:
                raise ValueError(f"Missing key {key}")
            return rtype(val)

        return cls(
                title=get("title"),
                version=get("version"),
                sort_key=int(get("sort-key"), 0),
                linux=get("linux", pathlib.Path).relative_to("/"),
                initrd=get("initrd", pathlib.Path).relative_to("/"),
                options=get("options").split(),
                image_dir=get("#sonic:image-dir#", pathlib.Path),
        )

    @classmethod
    def from_dict(cls, mapping: t.Dict[str, t.Any]) -> t.Self:
        """Parse an SdbootConfig from a dictionary."""
        return SdbootConfig(
                title=mapping["title"],
                version=mapping["version"],
                sort_key=int(mapping["sort-key"], 0),
                linux=mapping["linux"],
                initrd=mapping["initrd"],
                options=mapping["options"],
                image_dir=mapping["image-dir"],
        )

    def to_dict(self) -> t.Dict[str, t.Any]:
        """Serialize the config to a dict."""
        return {
                "title": self.title,
                "sort-key": self.key_str(),
                "version": self.version,
                "linux": self.linux,
                "initrd": self.initrd,
                "options": self.options,
                "image-dir": self.image_dir,
        }

    def key_str(self):
        # TODO(scotthaiden): make this work as a tuple.
        return f"0x{self.sort_key:016x}"

    def write_file(self, path: pathlib.Path) -> t.Self:
        options = " ".join(self.options)
        with open(path, "wt") as f:
            f.write(f"title             {self.title}\n")
            f.write(f"version           {self.version}\n")
            f.write(f"sort-key          {self.key_str()}\n")
            f.write(f"linux             /{self.linux}\n")
            f.write(f"initrd            /{self.initrd}\n")
            f.write(f"options           {options}\n")
            f.write(f"#sonic:image-dir# {self.image_dir}\n")

    def __eq__(self, other) -> bool:
        def inner():
            yield self.title == other.title
            yield self.sort_key == other.sort_key
            yield self.linux == other.linux
            yield self.initrd == other.initrd
            yield self.options == other.options
            yield self.image_dir == other.image_dir

        return all(inner())


def find_configs(path: pathlib.Path) -> dict[str, SdbootConfig]:
    """Returns a dict of all SONIC configs in the directory.

    Returns:
        Dict with keys corresponding to the conf file name (including boot count and
        '.conf'), and values containing the parsed sdboot config.
    """
    if not path.is_dir():
        raise FileNotFoundError(f"{path} is not a directory.")

    ret = {}

    confs = path.glob("*.conf")
    for conf in confs:
        try:
            SdbootEntry.from_filename(conf)
        except ValueError as x:
            print(
                    f"Failed to parse boot entry metadata from {conf}; skipping. error"
                    f" = {x}",
                    file=sys.stderr,
            )
            continue

        try:
            config = SdbootConfig.from_file(conf)
        except ValueError as x:
            print(
                    f"Failed to parse config file {conf}; skipping. error = {x}",
                    file=sys.stderr,
            )
            continue

        ret[conf.name] = config

    return ret


def _read_efivar(
        varname: str,
        *,
        uuid: uuid.UUID = _SDBOOT_EFIVAR_UUID,
        efivars_path: pathlib.Path = _EFIVARS_PATH,
) -> str:
    path = efivars_path / f"{varname}-{uuid}"

    with open(path, "rb") as efivars_file:
        contents: bytes = efivars_file.read()

    if (count := len(contents)) < 4:
        raise ValueError(
                f"Invalid EFIVars file: Too short! (expected len >= 4, got {count}"
        )

    parsed = contents[4:].decode("utf-16")
    if (count := len(parsed)) == 0:
        raise ValueError("Invalid EFIVars file: Variable exists but is empty.")
    if parsed[-1] != "\x00":
        raise ValueError("Invalid EFIVars file: Variable is not null terminated.")

    return parsed[:-1]


def get_oneshot(
        efivars_path: pathlib.Path = _EFIVARS_PATH,
) -> SdbootEntry | None:
    try:
        if cont := _read_efivar("LoaderEntryOneShot", efivars_path=efivars_path):
            return SdbootEntry.from_filename(cont)
        return None
    except (ValueError, FileNotFoundError):
        return None


def get_cur_boot(
        efivars_path: pathlib.Path = _EFIVARS_PATH,
) -> SdbootEntry | None:
    """Uses bootctl to determine the currently booted boot entry.

    Returns:
        The ID of the current boot.
    """
    try:
        if cont := _read_efivar("LoaderEntrySelected", efivars_path=efivars_path):
            return SdbootEntry.from_filename(cont)
        return None
    except (ValueError, FileNotFoundError):
        return None
