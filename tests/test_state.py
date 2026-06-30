from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
import unittest

from deploylib.state import StateStore


class StateTests(unittest.TestCase):
    def test_state_round_trip_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state")
            document = {"environment": {"name": "feature-demo"}, "resources": {"mongo": {"database": "demo_mongo_feature_demo"}}}
            store.save("demo", "feature-demo", document)
            self.assertEqual(store.load("demo", "feature-demo"), document)
            state_file = Path(temp_dir) / "state" / "demo" / "feature-demo.json"
            self.assertEqual(stat.S_IMODE(os.stat(state_file).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
