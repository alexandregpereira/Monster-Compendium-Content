#!/usr/bin/env python3
"""Rebuild the JSON content tree from MongoDB.

This is the inverse of import.py and the code path a future /publish endpoint
should reuse: the app keeps consuming the files, so the database is only the
editing source of truth until this runs.

    python3 scripts/mongo/export.py --check           # diff against json/, write nothing
    python3 scripts/mongo/export.py --out /tmp/out
    python3 scripts/mongo/export.py --in-place        # overwrite json/
"""

import argparse
import difflib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mongo import db as dbmod        # noqa: E402
from mongo import manifest as mf     # noqa: E402
from mongo import transform          # noqa: E402

COLLECTIONS = ["monsters", "spells", "conditions", "sources"]


def load_from_db(database):
    collections_map = {}
    for name in COLLECTIONS:
        collections_map[name] = list(database[name].find({}))
    file_meta = list(database[mf.FILE_META_COLLECTION].find({}))
    if not file_meta:
        sys.exit(
            "No %s documents found. Run import.py first -- per-file formatting "
            "(indent width, trailing newline) is recorded there and the files "
            "cannot be reproduced byte-for-byte without it."
            % mf.FILE_META_COLLECTION
        )
    return collections_map, file_meta


def write_tree(rebuilt, out_root):
    for relpath, text in sorted(rebuilt.items()):
        target = os.path.join(out_root, relpath)
        directory = os.path.dirname(target)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)


def check(rebuilt, show_diff=False):
    """Compare against the working tree. Returns the list of differing paths."""
    differing = []
    for relpath, text in sorted(rebuilt.items()):
        original_path = os.path.join(mf.REPO_ROOT, relpath)
        if not os.path.exists(original_path):
            differing.append(relpath)
            continue
        with open(original_path, encoding="utf-8") as handle:
            original = handle.read()
        if text != original:
            differing.append(relpath)
            if show_diff:
                diff = difflib.unified_diff(
                    original.splitlines(True), text.splitlines(True),
                    fromfile=relpath + " (working tree)",
                    tofile=relpath + " (from database)", n=1,
                )
                sys.stdout.writelines(list(diff)[:40])
    return differing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="compare with the working tree, write nothing")
    group.add_argument("--out", help="write the rebuilt tree under this directory")
    group.add_argument("--in-place", action="store_true",
                       help="overwrite the files in json/")
    parser.add_argument("--diff", action="store_true", help="show diffs with --check")
    parser.add_argument("--uri", help="MongoDB URI (default: $MONGO_URI)")
    args = parser.parse_args(argv)

    database = dbmod.connect(args.uri)
    collections_map, file_meta = load_from_db(database)
    counts = ", ".join("%s %d" % (k, len(v)) for k, v in collections_map.items())
    print("Read from %r: %s" % (database.name, counts))

    rebuilt = transform.documents_to_files(collections_map, file_meta)
    print("Rebuilt %d files" % len(rebuilt))

    if args.check:
        differing = check(rebuilt, args.diff)
        if differing:
            print("\n%d file(s) differ from the working tree:" % len(differing))
            for relpath in differing:
                print("  %s" % relpath)
            return 1
        print("\nAll %d files are byte-identical to the working tree." % len(rebuilt))
        return 0

    out_root = mf.REPO_ROOT if args.in_place else args.out
    write_tree(rebuilt, out_root)
    print("Wrote %d files under %s" % (len(rebuilt), out_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
