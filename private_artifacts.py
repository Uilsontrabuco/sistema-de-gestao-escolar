"""Read private deployment artifacts without embedding records in public code.

Provision these files separately in a trusted environment. Missing configuration
is an error; never manufacture replacement personnel or financial records.
"""
import json
import os
import hashlib
from functools import lru_cache
from pathlib import Path


class PrivateConfigurationError(FileNotFoundError):
    """Required private configuration has not been provisioned."""


def private_path(filename):
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Expected a private artifact filename")
    directory = Path(os.environ.get("SCHOOL_PRIVATE_DATA_DIR") or Path(__file__).parent / "private" / "runtime")
    return directory / filename


def load_private_json(filename):
    return json.loads(read_private_bytes(filename))


def read_private_bytes(filename, local_path=None):
    path = private_path(filename) if local_path is None else local_path
    private_path(filename)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        if not os.environ.get("VERCEL"):
            raise PrivateConfigurationError("Required private configuration is unavailable") from None
    return _read_cloud_artifact(filename)


@lru_cache(maxsize=16)
def _read_cloud_artifact(filename):
    from private_artifact_manifest import ARTIFACT_SHA256
    if filename not in ARTIFACT_SHA256:
        raise PrivateConfigurationError("Private artifact is not configured")
    import psycopg
    from cloud_store import configuration, connection_options, PROJECT, SOURCE_HASH
    dsn, _, _ = configuration()
    with psycopg.connect(dsn, connect_timeout=10, sslmode="require", prepare_threshold=None, **connection_options(dsn)) as db:
        db.execute("SET TRANSACTION READ ONLY")
        marker = db.execute("SELECT project_ref,source_sha256 FROM seven7_app.metadata WHERE id=1").fetchone()
        if not marker or tuple(marker) != (PROJECT, SOURCE_HASH):
            raise PrivateConfigurationError("Private configuration identity mismatch")
        exposed = db.execute("SELECT has_schema_privilege('anon','seven7_app','USAGE') OR has_schema_privilege('authenticated','seven7_app','USAGE')").fetchone()[0]
        if exposed:
            raise PrivateConfigurationError("Private configuration access is not restricted")
        row = db.execute("SELECT content FROM seven7_app.assets WHERE id=%s", ("private-runtime/" + filename,)).fetchone()
    if not row:
        raise PrivateConfigurationError("Required private configuration is unavailable")
    raw = bytes(row[0])
    if hashlib.sha256(raw).hexdigest() != ARTIFACT_SHA256[filename]:
        raise PrivateConfigurationError("Private configuration integrity mismatch")
    return raw


def private_text(key):
    return load_private_json("private_text.json")[key]
