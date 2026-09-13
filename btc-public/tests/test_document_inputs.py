"""Check optional document inputs independently with tiny synthetic fixtures."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

import config
from tests import test_documents


class DocumentInputTests(unittest.TestCase):
    def test_missing_partial_and_complete_optional_inputs(self):
        original_read = Path.read_text
        docs = {config.ROOT / "README.md", config.ROOT / "WRITEUP.md"}
        phrases = ("\nup to five further data-derived phrases are checked when their source files are available\n"
                   "log-scale correlation 0.42\n"
                   "all 1 OI-covered print days, of which 0 fall inside the sealed blocks\n"
                   "(1 first-of-month training days)\n")

        def read_text(path, *args, **kwargs):
            result = original_read(path, *args, **kwargs)
            return result + phrases if path in docs else result

        for mix, liquidations, expected in ((False, False, 0), (True, False, 2),
                                             (False, True, 3), (True, True, 5)):
            with self.subTest(mix=mix, liquidations=liquidations), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                if mix:
                    (root / "leverage_mix.json").write_text(json.dumps({"corr": 0.42}))
                if liquidations:
                    (root / "liquidations.parquet").write_text("fixture read by stub")
                stdout = io.StringIO()
                with patch.object(config, "RAW", root), patch.object(config, "INTERIM", root), \
                     patch.object(Path, "read_text", read_text), \
                     patch.object(pd, "read_parquet", return_value=pd.DataFrame({"ts": ["2021-03-01"]})), \
                     contextlib.redirect_stdout(stdout):
                    test_documents.main()
                self.assertIn("52 quoted phrases", stdout.getvalue())
                self.assertIn(f"{expected} data-derived phrases match available inputs", stdout.getvalue())
                self.assertIn(f"{5 - expected} data-derived phrases not checked", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
