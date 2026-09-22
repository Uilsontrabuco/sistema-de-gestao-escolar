"""Offline checks using synthetic data only."""
import json
import os
from pathlib import Path
import tempfile
import hashlib
import unittest
from unittest.mock import patch, Mock

from private_artifacts import PrivateConfigurationError, load_private_json, private_path
import private_artifacts
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

    def test_cloud_artifact_requires_private_schema_identity_and_hash(self):
        import cloud_store
        raw=b'{"synthetic":true}'
        db=Mock();db.execute.return_value.fetchone.side_effect=[(cloud_store.PROJECT,cloud_store.SOURCE_HASH),(False,),(raw,)]
        connection=Mock();connection.__enter__=Mock(return_value=db);connection.__exit__=Mock(return_value=False)
        private_artifacts._read_cloud_artifact.cache_clear()
        with patch('private_artifact_manifest.ARTIFACT_SHA256',{'fixture.json':hashlib.sha256(raw).hexdigest()}), patch('cloud_store.configuration',return_value=('postgresql://fixture/db','fixture','fixture')),patch('cloud_store.connection_options',return_value={}),patch('psycopg.connect',return_value=connection):
            self.assertEqual(private_artifacts._read_cloud_artifact('fixture.json'),raw)
        private_artifacts._read_cloud_artifact.cache_clear()
        db.execute.return_value.fetchone.side_effect=[(cloud_store.PROJECT,cloud_store.SOURCE_HASH),(True,)]
        with patch('private_artifact_manifest.ARTIFACT_SHA256',{'fixture.json':hashlib.sha256(raw).hexdigest()}),patch('cloud_store.configuration',return_value=('postgresql://fixture/db','fixture','fixture')),patch('cloud_store.connection_options',return_value={}),patch('psycopg.connect',return_value=connection):
            with self.assertRaises(PrivateConfigurationError):private_artifacts._read_cloud_artifact('fixture.json')

    def test_cloud_artifact_does_not_accept_unpinned_filename(self):
        with patch('psycopg.connect') as connection:
            with self.assertRaises(PrivateConfigurationError):private_artifacts._read_cloud_artifact('unapproved-fixture.json')
            connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
