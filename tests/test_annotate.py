"""告警标注纯函数测试。"""

import os
import pathlib
import tempfile
import time
import unittest

from annotate_alerts import build_annotations, classify_run


class ClassifyRunTest(unittest.TestCase):
    def _make_run(self, completed: bool, eval_age_h: float | None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run = pathlib.Path(tmp.name) / "seed00"
        run.mkdir(parents=True)
        if completed:
            (run / "final_model.zip").write_bytes(b"m")
            (run / ".completed").write_bytes(b"")
        if eval_age_h is not None:
            (run / "eval_log.csv").write_text("timesteps,r,s,l\n", encoding="utf-8")
            old = time.time() - eval_age_h * 3600
            os.utime(run / "eval_log.csv", (old, old))
        return run

    def test_completed(self):
        crash, note = classify_run(self._make_run(True, None))
        self.assertFalse(crash)
        self.assertEqual(note, "completed")

    def test_stale_unfinished(self):
        crash, note = classify_run(self._make_run(False, 5.0))
        self.assertTrue(crash)
        self.assertIn("stale", note)

    def test_fresh_unfinished(self):
        crash, note = classify_run(self._make_run(False, 0.1))
        self.assertIsNone(crash)


class BuildAnnotationsTest(unittest.TestCase):
    def test_only_r2_r3_and_dedupe(self):
        rows = [
            {"timestamp": "t1", "task": "b", "seed": "00", "level": "R1",
             "triggered_rules": "x"},
            {"timestamp": "t2", "task": "b", "seed": "00", "level": "R2",
             "triggered_rules": "drawdown"},
            {"timestamp": "t2", "task": "b", "seed": "00", "level": "R3",
             "triggered_rules": "kl"},
            {"timestamp": "t3", "task": "c", "seed": "01", "level": "R3",
             "triggered_rules": "neg_ratio"},
        ]
        out = build_annotations(rows, lambda task, seed: (True, "stale"))
        self.assertEqual(len(out), 2)
        self.assertEqual({o["level"] for o in out}, {"R2", "R3"})
        self.assertTrue(all(o["confirmed_crash"] for o in out))


if __name__ == "__main__":
    unittest.main()
