"""icsync command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from . import __version__, service
from .config import Config
from .importer import find_osxphotos, gather, run_once


def _setup_logging(cfg: Config, to_file: bool = True) -> None:
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if to_file:
        handlers.append(logging.FileHandler(cfg.log_dir / "icsync.log"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


# --- commands ---------------------------------------------------------------

def cmd_run(cfg: Config, _args) -> int:
    _setup_logging(cfg)
    run_once(cfg)
    return 0


def cmd_watch(cfg: Config, args) -> int:
    _setup_logging(cfg)
    logging.getLogger("icsync").info("Watching %s every %ds (Ctrl-C to stop)", cfg.inbox, args.interval)
    try:
        while True:
            run_once(cfg)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def cmd_install(cfg: Config, _args) -> int:
    dst = service.install(cfg)
    print(f"Installed LaunchAgent: {dst}")
    print(f"Inbox (point Syncthing receive-only here): {cfg.inbox}")
    print(f"Logs: {cfg.log_dir / 'icsync.log'}")
    print("Agent loaded and running every 60s.")
    return 0


def cmd_uninstall(cfg: Config, _args) -> int:
    existed = service.uninstall()
    print("Removed LaunchAgent." if existed else "No LaunchAgent was installed.")
    return 0


def cmd_start(cfg: Config, _args) -> int:
    service.load()
    print("Agent loaded." if service.is_loaded() else "Agent load attempted (not listed yet).")
    return 0


def cmd_stop(cfg: Config, _args) -> int:
    service.unload()
    print("Agent unloaded.")
    return 0


def cmd_status(cfg: Config, _args) -> int:
    loaded = service.is_loaded()
    pending = len(gather(cfg, time.time())) if cfg.inbox.exists() else 0
    print(f"LaunchAgent installed: {service.plist_path().exists()}")
    print(f"LaunchAgent loaded:    {loaded}")
    print(f"Inbox:                 {cfg.inbox}")
    print(f"Pending media:         {pending}")
    print(f"Archive:               {cfg.archive}  (retention {cfg.retention_days}d)")
    print(f"Logs:                  {cfg.log_dir / 'icsync.log'}")
    return 0


def cmd_doctor(cfg: Config, _args) -> int:
    ok = True
    try:
        exe = find_osxphotos(cfg)
        print(f"[ok] osxphotos: {exe}")
    except FileNotFoundError as e:
        ok = False
        print(f"[FAIL] {e}")
    for label, d in (("inbox", cfg.inbox), ("archive", cfg.archive), ("logs", cfg.log_dir)):
        print(f"[{'ok' if d.exists() else '--'}] {label} dir: {d}")
    print(f"[{'ok' if service.plist_path().exists() else '--'}] LaunchAgent: {service.plist_path()}")
    print(f"[{'ok' if service.is_loaded() else '--'}] agent loaded")
    print("\nReminders (cannot auto-check):")
    print(" - Photos.app signed in with 'iCloud Photos' ON.")
    print(" - Grant python Automation->Photos and Full Disk Access on first import.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="icsync", description="Bridge Android camera media into iCloud Photos via a Mac.")
    p.add_argument("--version", action="version", version=f"icsync {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="run one import cycle (used by launchd)").set_defaults(func=cmd_run)

    w = sub.add_parser("watch", help="loop import cycles in the foreground")
    w.add_argument("--interval", type=int, default=60, help="seconds between cycles")
    w.set_defaults(func=cmd_watch)

    sub.add_parser("install", help="install + load the LaunchAgent").set_defaults(func=cmd_install)
    sub.add_parser("uninstall", help="unload + remove the LaunchAgent").set_defaults(func=cmd_uninstall)
    sub.add_parser("start", help="load the LaunchAgent").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="unload the LaunchAgent").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="show bridge status").set_defaults(func=cmd_status)
    sub.add_parser("doctor", help="check prerequisites").set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.from_env()
    return args.func(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
