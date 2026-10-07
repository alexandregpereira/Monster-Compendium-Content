#!/usr/bin/env python3
"""Load the JSON content tree into MongoDB.

Idempotent: re-running converges on the same state rather than duplicating.

    python3 scripts/mongo/import.py                 # load everything
    python3 scripts/mongo/import.py --dry-run       # no database needed
    python3 scripts/mongo/import.py --collection monsters
    python3 scripts/mongo/import.py --drop          # rebuild from scratch
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mongo import db as dbmod          # noqa: E402
from mongo import manifest as mf       # noqa: E402
from mongo import report as reportmod  # noqa: E402
from mongo import schemas              # noqa: E402
from mongo import transform            # noqa: E402

COLLECTIONS = ["monsters", "spells", "conditions", "sources",
               "monster_lore", "monster_images"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collection", action="append", choices=COLLECTIONS,
                        help="limit to one collection (repeatable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="read and validate, write nothing; needs no database")
    parser.add_argument("--drop", action="store_true",
                        help="drop the target collections before loading")
    parser.add_argument("--uri", help="MongoDB URI (default: $MONGO_URI)")
    parser.add_argument("--quiet", action="store_true", help="suppress the integrity report")
    parser.add_argument("--prune", action="store_true",
                        help="delete documents that no longer appear in any file "
                             "(reported but kept by default, because a document "
                             "created through the API is also absent from the files)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail when the content tree has integrity errors "
                             "(by default those are reported but do not fail the run)")
    return parser.parse_args(argv)


def _exit_code(args, duplicates, failed_validators, findings):
    """Non-zero means the import itself did not succeed.

    Integrity findings describe the content tree, not the run: they are
    pre-existing conditions that nothing here repairs, so failing on them would
    mean the import reports failure on every run until unrelated content is
    edited. Use --strict in a pipeline that should block on them.
    """
    if duplicates or failed_validators:
        return 1
    if args.strict and reportmod.error_count(findings):
        print("Failing because --strict was given and the content tree has "
              "%d integrity error(s)." % reportmod.error_count(findings))
        return 1
    return 0


def main(argv=None):
    args = parse_args(argv)
    targets = args.collection or COLLECTIONS

    print("Reading content tree from %s" % mf.JSON_ROOT)
    collections_map, file_meta, duplicates = transform.files_to_documents()
    for path, index in duplicates:
        print("  ERROR duplicate index %r inside %s" % (index, path))

    for name in COLLECTIONS:
        marker = " " if name in targets else "-"
        print("  %s %-11s %5d documents" % (marker, name, len(collections_map[name])))
    print("  %s %-11s %5d files" % (" ", "file meta", len(file_meta)))

    findings = reportmod.run(collections_map, file_meta)

    if args.dry_run:
        print("\nDry run: nothing written.")
        if not args.quiet:
            print(reportmod.render(findings))
        return _exit_code(args, duplicates, [], findings)

    database = dbmod.connect(args.uri)
    print("\nConnected to database %r" % database.name)

    if args.drop:
        for name in targets + [mf.FILE_META_COLLECTION]:
            database[name].drop()
        print("Dropped: %s" % ", ".join(targets + [mf.FILE_META_COLLECTION]))

    for name in targets:
        stats = dbmod.bulk_upsert(database, name, collections_map[name])
        print("  %-11s inserted %-5d replaced %-5d (matched %d)"
              % (name, stats["inserted"], stats["modified"], stats["matched"]))

    orphans = {}
    for name in targets:
        expected = {d["_id"] for d in collections_map[name]}
        present = {d["_id"] for d in database[name].find({}, {"_id": 1})}
        extra = sorted(present - expected)
        if extra:
            orphans[name] = extra

    if orphans:
        total = sum(len(v) for v in orphans.values())
        action = "deleting" if args.prune else "keeping"
        print("\n%d document(s) in the database no longer appear in any file "
              "(%s):" % (total, action))
        for name, ids in orphans.items():
            for document_id in ids[:10]:
                print("  %-14s %s" % (name, document_id))
            if len(ids) > 10:
                print("  %-14s ... and %d more" % (name, len(ids) - 10))
        if args.prune:
            for name, ids in orphans.items():
                database[name].delete_many({"_id": {"$in": ids}})
        else:
            print("  Left in place. They will be written back out on export, so "
                  "pass --prune if they are stale.")

    meta_stats = dbmod.bulk_upsert(database, mf.FILE_META_COLLECTION, file_meta)
    print("  %-11s inserted %-5d replaced %-5d"
          % (mf.FILE_META_COLLECTION, meta_stats["inserted"], meta_stats["modified"]))

    created = dbmod.ensure_indexes(
        database,
        {k: v for k, v in schemas.INDEXES.items() if k in targets},
        {k: v for k, v in schemas.TEXT_INDEXES.items() if k in targets},
    )
    print("\nIndexes created: %s" % (", ".join(created) if created else "none (already present)"))

    applied, failed = dbmod.apply_validators(
        database, {k: v for k, v in schemas.VALIDATORS.items() if k in targets})
    print("Validators applied: %s" % ", ".join(applied))
    for name, error in failed:
        print("  ERROR could not apply validator to %s: %s" % (name, error))

    for name in targets:
        print("  %-11s %5d documents in database" % (name, database[name].count_documents({})))

    if not args.quiet:
        print(reportmod.render(findings))

    return _exit_code(args, duplicates, failed, findings)


if __name__ == "__main__":
    sys.exit(main())
