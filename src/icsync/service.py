"""LaunchAgent management: render plist, install/uninstall, load/unload, status."""

from __future__ import annotations

import subprocess
import sys
from importlib import resources
from pathlib import Path

from .config import LABEL, Config

INTERVAL_SECONDS = 60


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def render_plist(cfg: Config) -> str:
    template = resources.files("icsync.templates").joinpath("com.icsync.import.plist").read_text()
    return template.format(
        label=LABEL,
        python=sys.executable,  # this interpreter == the pipx venv that has icsync+osxphotos
        interval=INTERVAL_SECONDS,
        inbox=str(cfg.inbox),
        stdout=str(cfg.log_dir / "launchd.out.log"),
        stderr=str(cfg.log_dir / "launchd.err.log"),
    )


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def load() -> None:
    _launchctl("unload", str(plist_path()))  # idempotent
    _launchctl("load", str(plist_path()))


def unload() -> None:
    _launchctl("unload", str(plist_path()))


def install(cfg: Config) -> Path:
    cfg.ensure_dirs()
    dst = plist_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(render_plist(cfg))
    load()
    return dst


def uninstall() -> bool:
    unload()
    dst = plist_path()
    existed = dst.exists()
    dst.unlink(missing_ok=True)
    return existed


def is_loaded() -> bool:
    res = _launchctl("list")
    return LABEL in res.stdout
