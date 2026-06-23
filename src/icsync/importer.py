"""Core import cycle: inbox -> `osxphotos import` -> archive -> prune."""

from __future__ import annotations

import csv
import datetime as dt
import fcntl
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .config import MEDIA_EXTS, SKIP_PREFIXES, SKIP_SUFFIXES, Config

log = logging.getLogger("icsync")


def find_osxphotos(cfg: Config) -> str:
    """Locate the osxphotos executable.

    Prefers the one installed alongside this interpreter (same pipx venv),
    then falls back to PATH and common install dirs.
    """
    if cfg.osxphotos:
        return cfg.osxphotos
    sibling = Path(sys.executable).parent / "osxphotos"
    if sibling.exists():
        return str(sibling)
    extra = [str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    path = os.pathsep.join(extra + [os.environ.get("PATH", "")])
    found = shutil.which("osxphotos", path=path)
    if not found:
        raise FileNotFoundError(
            "osxphotos not found. It is a dependency of icsync; "
            "reinstall with `pipx install icsync` or `pipx install osxphotos`."
        )
    return found


def acquire_lock(cfg: Config):
    """Single-instance guard. Returns the held file handle, or None if locked."""
    cfg.lock_file.parent.mkdir(parents=True, exist_ok=True)
    fh = open(cfg.lock_file, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    return fh


def _is_candidate(p: Path, now: float, stable: int) -> bool:
    name = p.name
    if not p.is_file():
        return False
    if name.startswith(SKIP_PREFIXES) or name.endswith(SKIP_SUFFIXES):
        return False
    if p.suffix.lower() not in MEDIA_EXTS:
        return False
    try:
        if now - p.stat().st_mtime < stable:
            return False  # still possibly being written/synced
    except OSError:
        return False
    return True


def gather(cfg: Config, now: float) -> list[Path]:
    if not cfg.inbox.exists():
        return []
    return sorted(p for p in cfg.inbox.rglob("*") if _is_candidate(p, now, cfg.stable_seconds))


def _run_osxphotos(exe: str, files: list[Path], report_csv: Path) -> int:
    cmd = [
        exe, "import",
        "--skip-dups", "--no-progress",
        "--report", str(report_csv),
        *[str(f) for f in files],
    ]
    log.info("Importing %d file(s)...", len(files))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout.strip():
        log.info("osxphotos: %s", proc.stdout.strip()[-2000:])
    if proc.returncode != 0 and proc.stderr.strip():
        log.warning("osxphotos stderr: %s", proc.stderr.strip()[-2000:])
    return proc.returncode


def _handled_from_report(report_csv: Path) -> set[str]:
    handled: set[str] = set()
    try:
        with open(report_csv, newline="") as fh:
            for row in csv.DictReader(fh):
                low = {k.lower(): (v or "") for k, v in row.items()}
                path = low.get("filepath") or low.get("filename") or ""
                if not path:
                    continue
                imported = low.get("imported", "").strip().lower() in ("true", "1", "yes")
                skipped = low.get("skipped", "").strip().lower() in ("true", "1", "yes")
                error = low.get("error", "").strip()
                if (imported or skipped) and not error:
                    handled.add(str(Path(path).resolve()))
    except (OSError, csv.Error) as e:
        log.warning("Could not parse report (%s); falling back to exit code.", e)
    return handled


def archive(cfg: Config, files: list[Path]) -> None:
    day = dt.datetime.now().strftime("%Y-%m-%d")
    dest_dir = cfg.archive / day
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = dest_dir / f.name
        n = 1
        while dest.exists():
            dest = dest_dir / f"{f.stem}__{n}{f.suffix}"
            n += 1
        try:
            shutil.move(str(f), str(dest))
        except OSError as e:
            log.error("Archive move failed for %s: %s", f, e)


def prune_archive(cfg: Config, now: float) -> None:
    if not cfg.archive.exists():
        return
    cutoff = now - cfg.retention_days * 86400
    for p in cfg.archive.rglob("*"):
        if p.is_file():
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass
    for d in sorted(cfg.archive.glob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def run_once(cfg: Config) -> int:
    """One import cycle. Returns count of files imported+archived."""
    lock = acquire_lock(cfg)
    if lock is None:
        log.info("Another instance is running; exiting.")
        return 0
    try:
        now = time.time()
        files = gather(cfg, now)
        if not files:
            prune_archive(cfg, now)
            return 0

        exe = find_osxphotos(cfg)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
            report_csv = Path(tf.name)
        try:
            rc = _run_osxphotos(exe, files, report_csv)
            handled = _handled_from_report(report_csv)
            if handled:
                ok = [f for f in files if str(f.resolve()) in handled]
                failed = [f for f in files if str(f.resolve()) not in handled]
            elif rc == 0:
                ok, failed = files, []
            else:
                ok, failed = [], files
        finally:
            report_csv.unlink(missing_ok=True)

        if ok:
            archive(cfg, ok)
            log.info("Imported+archived %d file(s).", len(ok))
        if failed:
            log.warning("%d file(s) left in inbox for retry.", len(failed))
        prune_archive(cfg, time.time())
        return len(ok)
    finally:
        lock.close()
