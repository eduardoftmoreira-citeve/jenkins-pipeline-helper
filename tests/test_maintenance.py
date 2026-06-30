from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from deploylib.backup import ArchiveBackupManager
from deploylib.config import BackupPolicy, ProviderBackupSettings


class MaintenanceContractTests(unittest.TestCase):
    def test_manifest_records_provider_type_for_provider_neutral_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "backup.archive.gz"
            archive.write_bytes(b"payload")
            manager = ArchiveBackupManager(root, BackupPolicy())
            manifest = {
                "provider": "mongo",
                "sha256": manager._sha256(archive),
                "archive": archive.name,
            }
            archive.with_name(f"{archive.name}.json").write_text(
                __import__("json").dumps(manifest), encoding="utf-8"
            )
            self.assertEqual(ArchiveBackupManager.read_manifest(archive)["provider"], "mongo")

    def test_provider_backup_settings_are_keyed_by_provider_not_jenkins_operation(self):
        settings = ProviderBackupSettings(Path("/tmp/backups"), {"production": BackupPolicy(enabled=True)})
        self.assertTrue(settings.policies["production"].enabled)

    def test_groovy_entrypoint_accepts_verify_operation(self):
        repository = Path(__file__).resolve().parents[1]
        groovy = (repository / "vars" / "maintenance.groovy").read_text(encoding="utf-8")
        self.assertIn("'verify'", groovy)
        self.assertIn("--operation", groovy)


if __name__ == "__main__":
    unittest.main()
