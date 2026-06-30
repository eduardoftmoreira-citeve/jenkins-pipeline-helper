from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from deploylib.backup import ArchiveBackupManager
from deploylib.config import BackupPolicy


class BackupRetentionTests(unittest.TestCase):
    def _write_record(self, directory: Path, timestamp: datetime) -> Path:
        archive = directory / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}.archive.gz"
        archive.write_bytes(b"backup")
        manifest = {
            "created_at": timestamp.isoformat(),
            "archive": archive.name,
            "sha256": "not-used-by-retention",
        }
        (directory / f"{archive.name}.json").write_text(json.dumps(manifest), encoding="utf-8")
        return archive

    def test_gfs_retention_keeps_daily_weekly_and_monthly_restore_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            now = datetime(2026, 6, 30, 2, 15, tzinfo=timezone.utc)
            archives = [self._write_record(directory, now - timedelta(days=offset)) for offset in (0, 1, 2, 8, 15, 30, 45, 100)]
            manager = ArchiveBackupManager(
                directory,
                BackupPolicy(
                    enabled=True,
                    daily_retention_days=2,
                    weekly_retention_weeks=4,
                    monthly_retention_months=4,
                ),
            )
            keep = manager._retained_paths(directory, now)
            self.assertIn(archives[0], keep)
            self.assertIn(archives[1], keep)
            self.assertIn(archives[4], keep)
            self.assertIn(archives[-1], keep)


if __name__ == "__main__":
    unittest.main()
