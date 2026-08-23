#!/usr/bin/env python3
"""Offline checks that need no database.

Two things are worth proving before any server is involved:

  1. Round trip -- documents_to_files(files_to_documents(tree)) reproduces every
     file byte for byte. If this fails, publishing would silently reformat or
     lose content.
  2. Validator fit -- every document already in the tree satisfies the
     $jsonSchema that import.py is about to attach. A validator that rejects
     existing content would let the editor load a monster it cannot save.

    python3 scripts/mongo/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mongo import manifest as mf     # noqa: E402
from mongo import report as reportmod  # noqa: E402
from mongo import schemas            # noqa: E402
from mongo import transform          # noqa: E402

# Enough of the BSON type vocabulary to interpret the validators in schemas.py.
BSON_TYPES = {
    "string": str,
    "object": dict,
    "array": list,
    "bool": bool,
    "null": type(None),
    "int": int,
    "long": int,
    "double": float,
    "decimal": float,
}


def _matches_type(value, names):
    if isinstance(names, str):
        names = [names]
    for name in names:
        expected = BSON_TYPES.get(name)
        if expected is None:
            continue
        # bool is a subclass of int in Python but a distinct BSON type.
        if isinstance(value, bool) and expected is not bool:
            continue
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            continue
        if isinstance(value, expected):
            return True
    return False


def validate(value, schema, path=""):
    """Return a list of human-readable violations of the schema subset used here."""
    errors = []
    if "bsonType" in schema and not _matches_type(value, schema["bsonType"]):
        errors.append("%s: expected %s, got %s"
                      % (path or "<root>", schema["bsonType"], type(value).__name__))
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r not in enum" % (path or "<root>", value))
        return errors

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing required field %r" % (path or "<root>", key))
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate(value[key], subschema,
                                       "%s.%s" % (path, key) if path else key))
    elif isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: %d items, minimum %d" % (path, len(value), schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: %d items, maximum %d" % (path, len(value), schema["maxItems"]))
        if "items" in schema:
            for position, item in enumerate(value):
                errors.extend(validate(item, schema["items"], "%s[%d]" % (path, position)))
    else:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %r below minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: %r above maximum %r" % (path, value, schema["maximum"]))
    return errors


def check_roundtrip(collections_map, file_meta):
    """Compare rebuilt files with the working tree.

    A file whose formatting was detected as not reproducible is expected to
    come back reformatted; that is reported separately rather than as a
    failure, because the alternative is storing its raw bytes forever. Any
    other difference is a real fidelity bug.
    """
    rebuilt = transform.documents_to_files(collections_map, file_meta)
    read_paths = {m["_id"] for m in file_meta}
    inexact = {m["_id"] for m in file_meta if not m.get("format_exact", True)}
    problems, expected = [], []
    for relpath in sorted(read_paths - set(rebuilt)):
        problems.append("%s: read but not rebuilt" % relpath)
    for relpath in sorted(set(rebuilt) - read_paths):
        problems.append("%s: rebuilt but never read" % relpath)
    identical = 0
    for relpath, text in sorted(rebuilt.items()):
        with open(os.path.join(mf.REPO_ROOT, relpath), encoding="utf-8") as handle:
            if handle.read() == text:
                identical += 1
            elif relpath in inexact:
                expected.append(relpath)
            else:
                problems.append("%s: differs after round trip" % relpath)
    return identical, len(rebuilt), problems, expected


def check_validators(collections_map):
    results = {}
    for name, schema in schemas.VALIDATORS.items():
        failures = []
        for doc in collections_map[name]:
            errors = validate(doc, schema)
            if errors:
                failures.append((doc["_id"], errors))
        results[name] = failures
    return results


def main():
    print("Reading content tree from %s" % mf.JSON_ROOT)
    collections_map, file_meta, duplicates = transform.files_to_documents()
    failed = False

    print("\n1. Round trip")
    identical, total, problems, expected = check_roundtrip(collections_map, file_meta)
    print("   %d / %d files byte-identical" % (identical, total))
    for relpath in expected:
        print("   normalised (formatting was not reproducible): %s" % relpath)
    for problem in problems[:20]:
        print("   FAIL %s" % problem)
    if problems:
        failed = True

    print("\n2. Validator fit")
    results = check_validators(collections_map)
    for name in sorted(results):
        failures = results[name]
        total_docs = len(collections_map[name])
        if failures:
            failed = True
            print("   %-11s %d / %d documents REJECTED" % (name, len(failures), total_docs))
            for doc_id, errors in failures[:5]:
                print("     %s" % doc_id)
                for error in errors[:3]:
                    print("       %s" % error)
        else:
            print("   %-11s all %d documents accepted" % (name, total_docs))

    print("\n3. Key uniqueness")
    if duplicates:
        failed = True
        for path, index in duplicates[:10]:
            print("   FAIL duplicate index %r in %s" % (index, path))
    else:
        print("   no duplicate keys within any file")

    print(reportmod.render(reportmod.run(collections_map, file_meta)))
    print("RESULT: %s" % ("FAILED" if failed else "PASSED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
