"""Read private deployment artifacts without embedding records in public code.

Provision these files separately in a trusted environment. Missing configuration
is an error; never manufacture replacement personnel or financial records.
"""
import json
import os
from pathlib import Path


class PrivateConfigurationError(FileNotFoundError):
    """Required private configuration has not been provisioned."""


def private_path(filename):
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Expected a private artifact filename")
    directory = Path(os.environ.get("SCHOOL_PRIVATE_DATA_DIR") or Path(__file__).parent / "private" / "runtime")
    return directory / filename


def load_private_json(filename):
    try:
        return json.loads(private_path(filename).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PrivateConfigurationError("Required private configuration is unavailable") from None


def private_text(key):
    return load_private_json("private_text.json")[key]
