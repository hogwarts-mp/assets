# Substrate save (HL-01-00.sav)

The baseline save every MP client boots into (the client's substrate auto-loader loads slot
`HL-01-00`; the launcher downloads it from this repo's release on every launch and overwrites the
local copy). This directory holds the **diffable source of truth for edits** — the ordered SQL
migrations plus the build script. The saves themselves (base and built) are **release assets**, not
tracked in git.

- `HL-01-00.pristine.sav` — the original post-Sorting capture. **Not in git**; published to the
  release. Download it into this directory before rebuilding. Never hand-edit; new captures replace it.
- `migrations/*.sql` — ordered edits applied to the embedded SQLite DB. One file per change,
  numbered; each states what it does and when it was verified in-game.
- `tools/hl_save_db.py` — the extract/inject tool (vendored; `build.py` uses it by default,
  override with `HL_SAVE_DB_TOOL`).
- `HL-01-00.sav` — the built, migrated save (gitignored build artifact). Regenerate it, don't hand-edit it.

`tools/hl_save_db.py` needs the Oodle DLL `oo2core_9_win64.dll` — proprietary (ships with the game
and with UnrealReZen), **not redistributed here**. Set `HL_OO2CORE` to its path, or drop it in
`tools/oodle/` (gitignored).

## Rebuild

```bash
export HL_OO2CORE=/path/to/oo2core_9_win64.dll   # or place it in substrate/tools/oodle/
python substrate/build.py     # -> substrate/HL-01-00.sav (gitignored build artifact)
```

Extracts the pristine DB, applies `migrations/*.sql` in order in ONE sqlite session (required for
byte-deterministic output), re-injects. Requires the Oodle DLL (above) and the pristine base
downloaded from the release.

## Publish

Upload both the base and the built save so each release is self-contained. Easiest is
`build.py --publish` (builds, then uploads both via `gh`):

```bash
python substrate/build.py --publish
# equivalent manual step:
gh release upload prerelease-v1.0.0 \
  substrate/HL-01-00.pristine.sav substrate/HL-01-00.sav --clobber --repo hogwarts-mp/assets
```

The launcher pins that tag (`kPakBaseUrl` in `launcher_ui/src/game_launch.cpp`) and always
overwrites the local save, so publishing propagates to every player on next launch. For local
testing of an unpublished substrate, no-op `DownloadSubstrateSave()` in the launcher (dev-only edit,
don't commit it).

## Current migrations

1. `001-invalidate-quests.sql` — kills the three advertised quests (Charms `ZZC_01`, DADA `ZZD_01`,
   `COM_02`) + the `DayOneTime` scheduler: `Main` rows → `Invalid`, `MissionEntryPoint` rows deleted.
   Result: empty quest journal, no world quest markers at the state level. Verified in-game 2026-07-05.
