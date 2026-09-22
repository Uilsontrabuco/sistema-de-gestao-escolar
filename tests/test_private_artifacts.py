"""Offline checks using synthetic data only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from private_artifacts import PrivateConfigurationError, load_private_json, private_path
from personnel_evidence import personnel_evidence
from personnel_projection import official_projection


class PrivateArtifactTests(unittest.TestCase):
    def test_missing_configuration_fails_without_fabricating_records(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SCHOOL_PRIVATE_DATA_DIR": directory}):
            with self.assertRaises(PrivateConfigurationError):
                personnel_evidence()
            with self.assertRaises(PrivateConfigurationError):
                official_projection([])

    def test_private_values_are_fresh_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SCHOOL_PRIVATE_DATA_DIR": directory}):
            path = Path(directory) / "personnel_evidence.json"
            raw = json.dumps({"evidence": {"rows": [{"id": "synthetic-1", "amount": 123}]}, "note": "Synthetic fixture"})
            path.write_text(raw, encoding="utf-8")
            personnel_evidence()["rows"][0]["amount"] = 999
            self.assertEqual(personnel_evidence()["rows"][0]["amount"], 123)
            self.assertEqual(path.read_text(encoding="utf-8"), raw)

    def test_configuration_path_cannot_escape_directory(self):
        for name in ("../example.json", "..\\example.json", "/example.json", ""):
            with self.assertRaises(ValueError):
                private_path(name)

    def test_invalid_json_is_not_replaced_with_empty_data(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SCHOOL_PRIVATE_DATA_DIR": directory}):
            (Path(directory) / "invalid.json").write_text("invalid", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_private_json("invalid.json")


if __name__ == "__main__":
    unittest.main()
