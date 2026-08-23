"""MongoDB connection and collection setup."""

import os
import sys

DEFAULT_URI = "mongodb://root:devpassword@localhost:27017/compendium?authSource=admin"
DEFAULT_DB = "compendium"


def _load_dotenv():
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def connect(uri=None, timeout_ms=5000):
    """Return a Database handle, or exit with a useful message if unreachable."""
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        sys.exit("pymongo is not installed. Run: python3 -m pip install --user pymongo")

    _load_dotenv()
    uri = uri or os.environ.get("MONGO_URI") or DEFAULT_URI
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        sys.exit(
            "Could not reach MongoDB at %s\n  %s\n\n"
            "Start the local instance with:  docker compose up -d mongo\n"
            "or point MONGO_URI at another server."
            % (uri.split("@")[-1], exc)
        )
    name = client.get_default_database().name if "/" in uri.split("//")[-1] else DEFAULT_DB
    return client[name or DEFAULT_DB]


def ensure_indexes(database, index_specs, text_specs):
    """Create indexes if absent. Safe to re-run."""
    created = []
    for collection_name, specs in index_specs.items():
        collection = database[collection_name]
        for keys, options in specs:
            name = options.get("name")
            existing = collection.index_information()
            if name in existing:
                continue
            collection.create_index([(k, 1) for k in keys], **options)
            created.append("%s.%s" % (collection_name, name))
    for collection_name, (field, name) in text_specs.items():
        collection = database[collection_name]
        if name not in collection.index_information():
            collection.create_index([(field, "text")], name=name)
            created.append("%s.%s" % (collection_name, name))
    return created


def apply_validators(database, validators):
    """Attach $jsonSchema validators after loading.

    Applied after the data is in so that a pre-existing violation surfaces as a
    report line rather than aborting the import half way through. validationLevel
    "moderate" leaves existing documents alone and checks inserts and updates.
    """
    from pymongo.errors import PyMongoError

    applied, failed = [], []
    existing = set(database.list_collection_names())
    for name, schema in validators.items():
        if name not in existing:
            database.create_collection(name)
        try:
            database.command({
                "collMod": name,
                "validator": {"$jsonSchema": schema},
                "validationLevel": "moderate",
                "validationAction": "error",
            })
            applied.append(name)
        except PyMongoError as exc:
            failed.append((name, str(exc)))
    return applied, failed


def bulk_upsert(database, collection_name, documents, batch_size=500):
    """Idempotent load: re-running converges instead of duplicating."""
    from pymongo import ReplaceOne

    collection = database[collection_name]
    inserted = modified = matched = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        operations = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in batch]
        result = collection.bulk_write(operations, ordered=False)
        inserted += len(result.upserted_ids or {})
        modified += result.modified_count
        matched += result.matched_count
    return {"inserted": inserted, "modified": modified, "matched": matched}
