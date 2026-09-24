"""Personnel evidence supplied through private runtime configuration."""
from private_artifacts import load_private_json

def personnel_evidence():
    return load_private_json("personnel_evidence.json")["evidence"]

def personnel_note():
    return load_private_json("personnel_evidence.json")["note"]
