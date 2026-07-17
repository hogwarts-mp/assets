#!/usr/bin/env python3
"""Rebuild HL-01-00.sav from the pristine capture + migrations/*.sql (in order).

All migrations run in ONE sqlite session — that keeps the output byte-deterministic
(page layout depends on the edit session structure, not just the logical result).

Uses the vendored hl-save-db tool (tools/hl_save_db.py; override with HL_SAVE_DB_TOOL),
which needs the Oodle DLL (oo2core_9_win64.dll) — set HL_OO2CORE or drop it in tools/oodle/.
The pristine base (HL-01-00.pristine.sav) is not tracked here — download it from the
release into this directory before building.
"""

import argparse
import glob
import os
import sqlite3
import subprocess
import sys

RELEASE_TAG = "prerelease-v1.0.0"
RELEASE_REPO = "hogwarts-mp/assets"

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser(description="Rebuild HL-01-00.sav from the pristine capture + migrations.")
ap.add_argument("--publish", action="store_true",
                help=f"after building, upload both saves to the {RELEASE_TAG} release (needs gh)")
opts = ap.parse_args()

TOOL = os.environ.get("HL_SAVE_DB_TOOL", os.path.join(HERE, "tools", "hl_save_db.py"))
PRISTINE = os.path.join(HERE, "HL-01-00.pristine.sav")
if not os.path.exists(PRISTINE):
    sys.exit(f"missing {os.path.basename(PRISTINE)} — download the base save from the release into {HERE}")
OUT = os.path.join(HERE, "HL-01-00.sav")  # build artifact (gitignored); publish to the release
WORK_DB = os.path.join(HERE, "work.db")

subprocess.run([sys.executable, TOOL, "extract", PRISTINE, "-o", WORK_DB], check=True)

con = sqlite3.connect(WORK_DB)
for f in sorted(glob.glob(os.path.join(HERE, "migrations", "*.sql"))):
    print(f"applying {os.path.basename(f)}")
    con.executescript(open(f).read())
con.commit()
con.close()

subprocess.run([sys.executable, TOOL, "inject", PRISTINE, WORK_DB, "-o", OUT], check=True)
os.remove(WORK_DB)
print(f"built {OUT}")

if opts.publish:
    # Upload base + built together so each release is self-contained.
    subprocess.run(["gh", "release", "upload", RELEASE_TAG, PRISTINE, OUT,
                    "--clobber", "--repo", RELEASE_REPO], check=True)
    print(f"published {os.path.basename(PRISTINE)} + {os.path.basename(OUT)} to {RELEASE_TAG}")
else:
    print("publish base + built save to the release (keeps each release self-contained):")
    print(f"  python substrate/build.py --publish   # or: gh release upload {RELEASE_TAG} "
          f"{os.path.basename(PRISTINE)} {os.path.basename(OUT)} --clobber --repo {RELEASE_REPO}")
