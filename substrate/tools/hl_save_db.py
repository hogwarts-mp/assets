#!/usr/bin/env python3
"""Extract and query the SQLite database embedded in Hogwarts Legacy .sav files.

HL saves are GVAS files whose `RawDatabaseImage` property holds a UE compressed
archive (magic 0x9E2A83C1): u64 magic, u64 block size (0x20000), u64 compressed
total, u64 uncompressed total, then [u64 comp, u64 uncomp] per chunk followed by
the chunk data. Chunks are Oodle-compressed (NOT zlib). The decompressed stream
starts with an 8-byte size prefix (u32 image size, u32 db size) before the
'SQLite format 3' magic. Multiple archive segments may repeat back-to-back.

Write-back (`inject`) rebuilds the RawDatabaseImage property from a modified DB:
stream = u32(dbLen+4) + u32(dbLen) + db, split into 0x20000 chunks, each its own
one-chunk archive segment (matching the game's layout), Oodle-Kraken compressed;
then the ArrayProperty u64 payload size + u32 byte count are patched and the
payload spliced (GVAS is sequential — following properties just shift). Verified
round-trip 2026-07-05. ALWAYS back up the .sav first; the tool refuses in-place.

Needs the Oodle DLL (oo2core_9_win64.dll) — proprietary, ships with the game and
with UnrealReZen; not redistributed here. Set HL_OO2CORE or drop it in tools/oodle/.

Usage:
  python hl_save_db.py find                      # list save files (modded + vanilla dirs)
  python hl_save_db.py extract SAVE [-o OUT.db]  # write the embedded SQLite to disk
  python hl_save_db.py tables SAVE               # non-empty tables + row counts
  python hl_save_db.py query SAVE "SQL..."       # run SQL against the embedded DB
  python hl_save_db.py inject SAVE DB -o OUT.sav # write DB back into a COPY of SAVE
"""

import argparse
import ctypes
import glob
import os
import sqlite3
import struct
import sys
import tempfile

OODLE_CANDIDATES = [
    os.environ.get("HL_OO2CORE", ""),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "oodle", "oo2core_9_win64.dll"),
]

SAVE_DIRS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Hogwarts Legacy\HogwartsMP\Saved\SaveGames"),
    os.path.expandvars(r"%LOCALAPPDATA%\Hogwarts Legacy\Saved\SaveGames"),
]

UE_MAGIC = b"\xc1\x83\x2a\x9e"  # 0x9E2A83C1 little-endian


def load_oodle():
    for p in OODLE_CANDIDATES:
        if p and os.path.exists(p):
            dll = ctypes.CDLL(p)
            dll.OodleLZ_Decompress.restype = ctypes.c_int64
            return dll
    sys.exit("oo2core_9_win64.dll not found (set HL_OO2CORE or place it at tools\\oodle\\)")


def oodle_decompress(dll, src: bytes, dst_len: int) -> bytes:
    dst = ctypes.create_string_buffer(dst_len)
    n = dll.OodleLZ_Decompress(
        src, ctypes.c_int64(len(src)), dst, ctypes.c_int64(dst_len),
        ctypes.c_int(1), ctypes.c_int(0), ctypes.c_int(0),  # fuzzSafe, checkCRC, verbosity
        None, ctypes.c_int64(0), None, None, None, ctypes.c_int64(0),
        ctypes.c_int(3),  # threadPhase = all
    )
    if n != dst_len:
        raise RuntimeError(f"Oodle decompress returned {n}, expected {dst_len}")
    return dst.raw


def oodle_compress(dll, src: bytes) -> bytes:
    dll.OodleLZ_Compress.restype = ctypes.c_int64
    dst = ctypes.create_string_buffer(len(src) + 0x10000)
    n = dll.OodleLZ_Compress(
        ctypes.c_int(8), src, ctypes.c_int64(len(src)), dst,  # 8 = Kraken
        ctypes.c_int(4),  # level Normal
        None, None, None, None, ctypes.c_int64(0),
    )
    if n <= 0:
        raise RuntimeError(f"Oodle compress returned {n}")
    return dst.raw[:n]


def parse_db_property(data: bytes):
    """Locate RawDatabaseImage's ArrayProperty. Returns (sizeOff, countOff, payloadOff, payloadLen)."""
    name = b"RawDatabaseImage\x00"
    i = data.find(name)
    if i < 0:
        sys.exit("no RawDatabaseImage property")
    p = i + len(name)
    (tl,) = struct.unpack_from("<I", data, p); p += 4
    if data[p : p + tl] != b"ArrayProperty\x00":
        sys.exit("RawDatabaseImage is not an ArrayProperty — format changed?")
    p += tl
    size_off = p; p += 8            # u64 payload size (= 4 + byte count)
    (il,) = struct.unpack_from("<I", data, p); p += 4 + il  # inner type "ByteProperty\0"
    p += 1                          # hasGuid terminator
    count_off = p
    (count,) = struct.unpack_from("<I", data, p); p += 4
    if data[p : p + 4] != UE_MAGIC:
        sys.exit("RawDatabaseImage payload doesn't start with archive magic")
    return size_off, count_off, p, count


def cmd_inject(args):
    if not args.output or os.path.abspath(args.output) == os.path.abspath(args.save):
        sys.exit("inject writes a NEW file: pass -o OUT.sav (never in-place; keep a backup)")
    data = open(args.save, "rb").read()
    db = open(args.db, "rb").read()
    if not db.startswith(b"SQLite format 3"):
        sys.exit(f"{args.db}: not a SQLite database")
    size_off, count_off, payload_off, count = parse_db_property(data)
    # stream = u32(dbLen+4) + u32(dbLen) + db, one single-chunk archive segment per 0x20000 slice
    stream = struct.pack("<II", len(db) + 4, len(db)) + db
    dll = load_oodle()
    payload = b""
    for at in range(0, len(stream), 0x20000):
        raw = stream[at : at + 0x20000]
        comp = oodle_compress(dll, raw)
        payload += struct.pack("<QQQQ", 0x9E2A83C1, 0x20000, len(comp), len(raw))
        payload += struct.pack("<QQ", len(comp), len(raw)) + comp
    out = (data[:size_off] + struct.pack("<Q", len(payload) + 4)
           + data[size_off + 8 : count_off] + struct.pack("<I", len(payload))
           + payload + data[payload_off + count :])
    with open(args.output, "wb") as f:
        f.write(out)
    print(f"wrote {args.output} ({len(out)} bytes; db {len(db)}, payload {len(payload)})")
    back = extract_db(args.output)
    if back != db:
        sys.exit("VERIFY FAILED: re-extracted DB differs — do not use the output")
    print("verify OK: re-extracted DB is byte-identical")


def extract_db(sav_path: str) -> bytes:
    data = open(sav_path, "rb").read()
    pos = data.find(UE_MAGIC)
    if pos < 0:
        sys.exit(f"{sav_path}: no UE compressed-archive magic (not a data save?)")
    dll = load_oodle()
    out = b""
    # Archive segments repeat: header, chunk table, chunk data, next header...
    while pos < len(data) - 32 and data[pos : pos + 4] == UE_MAGIC:
        _, _blocksize, comp_total, _uncomp_total = struct.unpack_from("<QQQQ", data, pos)
        pos += 32
        chunks, got = [], 0
        while got < comp_total:
            c, u = struct.unpack_from("<QQ", data, pos)
            pos += 16
            chunks.append((c, u))
            got += c
        for c, u in chunks:
            out += oodle_decompress(dll, data[pos : pos + c], u)
            pos += c
    i = out.find(b"SQLite format 3")
    if i < 0:
        sys.exit(f"{sav_path}: decompressed OK but no SQLite magic — format changed?")
    return out[i:]


def open_db(sav_path: str) -> sqlite3.Connection:
    db = extract_db(sav_path)
    tmp = os.path.join(tempfile.gettempdir(), "hl_save_extract.db")
    with open(tmp, "wb") as f:
        f.write(db)
    return sqlite3.connect(tmp)


def cmd_find(_args):
    import datetime
    rows = []
    for d in SAVE_DIRS:
        kind = "modded " if "HogwartsMP" in d else "vanilla"
        for f in glob.glob(os.path.join(d, "*", "HL-*.sav")):
            rows.append((os.stat(f).st_mtime, kind, f, os.path.getsize(f)))
    for mtime, kind, f, size in sorted(rows, reverse=True):  # newest first
        print(f"{datetime.datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}  {kind}  {size:>8}  {f}")


def cmd_extract(args):
    out = args.output or (os.path.splitext(os.path.basename(args.save))[0] + ".db")
    db = extract_db(args.save)
    with open(out, "wb") as f:
        f.write(db)
    print(f"wrote {len(db)} bytes -> {out}")


def cmd_tables(args):
    con = open_db(args.save)
    cur = con.cursor()
    names = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in names:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
        except sqlite3.Error:
            continue
        if n:
            print(f"{n:>7}  {t}")


def cmd_query(args):
    con = open_db(args.save)
    cur = con.cursor()
    for row in cur.execute(args.sql):
        print(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("find")
    p = sub.add_parser("extract")
    p.add_argument("save")
    p.add_argument("-o", "--output")
    p = sub.add_parser("tables")
    p.add_argument("save")
    p = sub.add_parser("query")
    p.add_argument("save")
    p.add_argument("sql")
    p = sub.add_parser("inject")
    p.add_argument("save")
    p.add_argument("db")
    p.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    {"find": cmd_find, "extract": cmd_extract, "tables": cmd_tables, "query": cmd_query, "inject": cmd_inject}[args.cmd](args)


if __name__ == "__main__":
    main()
