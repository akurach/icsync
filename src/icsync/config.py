"""Runtime configuration for icsync, resolved from env with sane defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LABEL = "com.icsync.import"

MEDIA_EXTS = frozenset({
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff",
    ".dng", ".raw", ".cr2", ".cr3", ".nef", ".arw",
    ".mov", ".mp4", ".m4v", ".3gp", ".avi", ".mkv",
})
# Syncthing scratch / OS junk to never touch.
SKIP_PREFIXES = (".syncthing.", "~syncthing~", ".stfolder", ".stversions", ".")
SKIP_SUFFIXES = (".tmp", ".part", ".partial")


def _path(env: str, default: Path) -> Path:
    val = os.environ.get(env)
    return Path(val).expanduser() if val else default


def _int(env: str, default: int) -> int:
    try:
        return int(os.environ[env])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    root: Path
    inbox: Path
    archive: Path
    log_dir: Path
    lock_file: Path
    stable_seconds: int
    retention_days: int
    osxphotos: str  # "" => autodetect

    @classmethod
    def from_env(cls) -> "Config":
        root = _path("ICSYNC_ROOT", Path.home() / "Documents" / "icsync" / "data")
        return cls(
            root=root,
            inbox=_path("ICSYNC_INBOX", root / "inbox"),
            archive=_path("ICSYNC_ARCHIVE", root / "archive"),
            log_dir=_path("ICSYNC_LOG_DIR", root / "logs"),
            lock_file=_path("ICSYNC_LOCK", root / "icsync.lock"),
            stable_seconds=_int("ICSYNC_STABLE_SECONDS", 20),
            retention_days=_int("ICSYNC_RETENTION_DAYS", 7),
            osxphotos=os.environ.get("ICSYNC_OSXPHOTOS", ""),
        )

    def ensure_dirs(self) -> None:
        for d in (self.inbox, self.archive, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)
