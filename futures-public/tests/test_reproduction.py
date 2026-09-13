"""Offline regression checks for resume, retained hold-out and missing splice inputs."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

import build
import config
import progress
from candidates import splice_check
from stages import s9


class ReproductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, relative in (("ROOT", "."), ("RAW", "data/raw"),
                               ("GRID", "data/grid"), ("STAGES", "data/stages"),
                               ("REPORTS", "reports"), ("STAGE_REPORTS", "reports/stage_reports")):
            path = self.root / relative
            path.mkdir(parents=True, exist_ok=True)
            self.enter_patch(patch.object(config, name, path))
        self.enter_patch(patch.object(progress, "PATH", config.REPORTS / "progress.json"))
        self.enter_patch(patch.object(s9, "LOOKS", config.REPORTS / "holdout_looks.json"))
        self.enter_patch(patch.object(progress, "commit"))
        self.enter_patch(contextlib.redirect_stdout(io.StringIO()))

    def enter_patch(self, manager):
        value = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return value

    def complete_state(self):
        progress.save({stage: {"status": "complete"} for stage in progress.STAGES})
        (config.GRID / "w0.parquet").write_text("fixture")
        for stage in progress.STAGES[:-1]:
            (self.root / stage).write_text("fixture")

    def run_build(self, argv=(), fail=None, real_manifest=False):
        called = []

        def module(name):
            stage = name.split(".")[-1]

            def main():
                called.append(stage)
                if stage == fail:
                    raise RuntimeError("interrupted fixture")
                return "fixture completed"

            if stage == "s9":
                return SimpleNamespace(main=main, retained_result=lambda: "historical hold-out retained")
            return SimpleNamespace(main=main)

        manifest = contextlib.nullcontext() if real_manifest else patch.object(
            build, "required_outputs", lambda stage: [self.root / stage], create=True)
        with manifest, \
             patch.object(build.importlib, "import_module", side_effect=module), \
             patch.object(sys, "argv", ["build.py", *argv]):
            if fail:
                with self.assertRaisesRegex(RuntimeError, "interrupted fixture"):
                    build.main()
            else:
                build.main()
        return called

    def test_missing_intermediate_rebuilds_downstream_despite_w0(self):
        self.complete_state()
        (self.root / "s2").unlink()
        self.assertEqual(self.run_build(), progress.STAGES[2:9])
        self.assertEqual(progress.load()["s9"]["status"], "retained")

    def test_resume_after_s0_rebuilds_missing_training_outputs(self):
        self.complete_state()
        for path in build.required_outputs("s0"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        self.assertEqual(self.run_build(real_manifest=True), progress.STAGES[1:9])

    def test_interrupted_rebuild_invalidates_old_downstream_completions(self):
        self.complete_state()
        (self.root / "s2").unlink()
        self.run_build(fail="s2")
        self.assertEqual(progress.load()["s3"]["status"], "pending")

    def test_complete_build_still_validates_retained_s9(self):
        self.complete_state()
        self.assertEqual(self.run_build(), [])
        self.assertEqual(progress.load()["s9"]["status"], "retained")

    def test_force_from_rebuilds_requested_stages(self):
        self.complete_state()
        self.assertEqual(self.run_build(["--force-from", "s6"]), ["s6", "s7", "s8"])

    def test_only_missing_stage_does_not_run_other_stages(self):
        self.complete_state()
        (self.root / "s4").unlink()
        self.assertEqual(self.run_build(["--only", "s4"]), ["s4"])
        self.assertEqual(progress.load()["s5"]["status"], "pending")

    def historical_holdout(self):
        s9.LOOKS.write_text(json.dumps({"holdout": {"looks": 1, "history": [{"at": "2026-09-12"}]}}))
        for path in (config.REPORTS / "RESULTS.md", config.STAGE_REPORTS / "s9.md"):
            path.write_text("historical result fixture")

    def test_retention_leaves_reports_counter_and_scoring_untouched(self):
        self.historical_holdout()
        paths = [s9.LOOKS, config.REPORTS / "RESULTS.md", config.STAGE_REPORTS / "s9.md"]
        before = {path: path.read_bytes() for path in paths}
        with patch.object(s9.signal_eval, "load", side_effect=AssertionError("must not score")):
            self.assertIn("retained", s9.main())
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertFalse((config.STAGES / "s9_stats.json").exists())

    def test_missing_or_empty_retained_report_halts_without_rescoring(self):
        for missing, empty in (("RESULTS.md", False), ("s9.md", False), ("RESULTS.md", True)):
            with self.subTest(missing=missing, empty=empty):
                self.historical_holdout()
                path = (config.REPORTS if missing == "RESULTS.md" else config.STAGE_REPORTS) / missing
                path.write_text("") if empty else path.unlink()
                before = s9.LOOKS.read_bytes()
                with patch.object(s9.signal_eval, "load", side_effect=AssertionError("must not score")):
                    with self.assertRaises(SystemExit) as raised:
                        s9.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(before, s9.LOOKS.read_bytes())

    def test_empty_eia_page_rejected(self):
        with self.assertRaisesRegex(ValueError, "no settlement"):
            splice_check.parse_hist_page("<html>No observations</html>")

    def test_failed_market_never_replaces_report_or_prints_verdict(self):
        target = config.REPORTS / "candidates" / "SPLICE_CHECK.md"
        target.parent.mkdir()
        target.write_text("historical verdict fixture")
        stdout = io.StringIO()
        with patch.object(splice_check, "check_market", side_effect=FileNotFoundError("missing settlement")), \
             contextlib.redirect_stdout(stdout):
            with self.assertRaisesRegex(RuntimeError, "no verdict"):
                splice_check.main()
        self.assertNotIn("PREMISE", stdout.getvalue())
        self.assertEqual(target.read_text(), "historical verdict fixture")

    def test_no_eligible_expiries_rejected(self):
        index = pd.date_range("2024-01-01", periods=3)
        series = pd.Series([1.0, 2.0, 3.0], index=index)
        with patch.object(splice_check, "fetch_series", return_value=series), \
             patch.object(splice_check.pd, "read_parquet", return_value=series.to_frame("close")), \
             patch.object(splice_check.rolls, "expiries", return_value=[]):
            with self.assertRaisesRegex(ValueError, "no eligible expir"):
                splice_check.check_market("CL")


if __name__ == "__main__":
    unittest.main()
