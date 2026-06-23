# icsync

Sync **Android camera photos & videos into your iCloud Photo Library** — as
full-resolution originals, in the real Photos app, not some third-party gallery.

There is **no public Apple API** to write into the iCloud Photo Library. icsync
uses the only robust path: an always-on Mac signed into iCloud, importing media
via [`osxphotos`](https://github.com/RhetTbull/osxphotos) and letting Photos sync
it up.

```
Android DCIM/Camera ──Syncthing send-only──▶ Mac inbox
        Mac inbox ──icsync (launchd)──▶ osxphotos import ──▶ Photos.app ──▶ iCloud Photos
```

icsync is the **Mac-side bridge**: a small CLI that watches an inbox folder,
imports stable media into Photos, archives the originals, and installs itself as
a `launchd` agent. The Android→Mac transport is off-the-shelf
([Syncthing](https://syncthing.net/) — no port-forwarding, no exposing the Mac).

## Install

```bash
pipx install icsync      # pulls in osxphotos automatically
icsync install           # creates dirs + loads the LaunchAgent (runs every 60s)
icsync doctor            # check prerequisites
```

From source:

```bash
git clone https://github.com/akurach/icsync && cd icsync
pipx install .
```

## Prerequisites

1. **Photos.app** signed into your Apple ID, **iCloud Photos ON**
   (Photos → Settings → iCloud).
2. **Syncthing** on the Mac with a **Receive Only** folder at the icsync inbox
   (`~/Documents/icsync/data/inbox` by default), paired to the Android device's
   **Send Only** folder on `DCIM/Camera`.
3. On first import macOS will ask to grant **Automation → Photos**; `osxphotos`
   may also need **Full Disk Access** (System Settings → Privacy & Security).

## Commands

| Command | Does |
|---------|------|
| `icsync install` | Create data dirs, write + load the LaunchAgent. |
| `icsync uninstall` | Unload + remove the LaunchAgent. |
| `icsync start` / `stop` | Load / unload the agent. |
| `icsync status` | Show install state, pending media, paths. |
| `icsync run` | Run one import cycle (what launchd calls). |
| `icsync watch` | Loop cycles in the foreground (no launchd). |
| `icsync doctor` | Check osxphotos, dirs, agent, reminders. |

## How it behaves

- **Idempotent** — `osxphotos import --skip-dups`; re-delivered files don't duplicate.
- **Safe** — imported originals are *moved* to `data/archive/<date>/`, not deleted;
  a retention prune removes them after `ICSYNC_RETENTION_DAYS` (default 7). Set it
  high to keep originals indefinitely.
- **One-way** — Syncthing send-only → receive-only; nothing flows back to the phone.
- **Mac off = delay, not loss** — Syncthing on Android queues and retries; icsync
  catches up when the Mac returns.
- **Partial-write safe** — only files older than `ICSYNC_STABLE_SECONDS` (default
  20) are imported, so half-synced files are skipped until complete.

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `ICSYNC_ROOT` | `~/Documents/icsync/data` | Base data dir. |
| `ICSYNC_INBOX` | `…/inbox` | Watched folder (Syncthing target). |
| `ICSYNC_ARCHIVE` | `…/archive` | Where originals land after import. |
| `ICSYNC_STABLE_SECONDS` | `20` | Min file age before import. |
| `ICSYNC_RETENTION_DAYS` | `7` | Archive purge age. |
| `ICSYNC_OSXPHOTOS` | autodetect | Explicit path to the `osxphotos` binary. |

To override for the agent, add them to the `EnvironmentVariables` dict in
`~/Library/LaunchAgents/com.icsync.import.plist` and `icsync start`.

## Limitations

- Requires an always-on Mac as the bridge — no Apple device means no reliable path.
- Android "motion photos" import as stills (no Apple Live Photo pairing).
- Not affiliated with Apple; uses the public Photos import surface only.

## License

MIT
