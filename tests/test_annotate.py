"""告警标注纯函数测试。"""

import os
import pathlib
import tempfile
import time
import unittest

import pandas as pd

from annotate_alerts import build_annotations, classify_local, classify_run


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

class ClassifyLocalTest(unittest.TestCase):
    """classify_local：基于本地 data/datasets 判定崩溃（不依赖 Linux run 目录）。"""

    def _tables(self, completed=None, verdict=None, snaps_ts=None, rewards=None):
        runs = pd.DataFrame({
            "task": ["balance"], "seed": ["seed00"],
            "completed": [completed], "verdict": [verdict],
        })
        snaps = pd.DataFrame({
            "time": [0.0, 60.0, 120.0, 2400.0, 2460.0],
            "task": ["balance"] * 5, "seed": ["seed00"] * 5,
            "timesteps": snaps_ts or [100000.0] * 5,
        })
        evals = pd.DataFrame({
            "timesteps": [100000.0 * (i + 1) for i in range(len(rewards or []))],
            "task": ["balance"] * len(rewards or []),
            "seed": ["seed00"] * len(rewards or []),
            "mean_reward": rewards or [],
        })
        return {"runs": runs, "snapshots": snaps, "eval_points": evals}

    def test_completed_fail(self):
        crash, note = classify_local(
            "balance", "seed00", self._tables(True, "fail"), {})
        self.assertTrue(crash)
        self.assertEqual(note, "completed+fail")

    def test_completed_pass(self):
        crash, note = classify_local(
            "balance", "seed00", self._tables(True, "pass"), {})
        self.assertFalse(crash)
        self.assertEqual(note, "completed+pass")

    def test_completed_no_verdict(self):
        crash, note = classify_local(
            "balance", "seed00", self._tables(True, None), {})
        self.assertIsNone(crash)
        self.assertEqual(note, "completed_no_verdict")

    def test_unfinished_stall_neg(self):
        # 未完成 + 停滞 >= 30 分钟 + 最近 eval 持续为负 -> True
        snaps_ts = [100000.0, 100000.0, 100000.0, 100000.0, 100000.0]
        crash, note = classify_local(
            "balance", "seed00",
            self._tables(False, None, snaps_ts, [-1.0, -2.0, -3.0, -4.0, -5.0]),
            {"risk": {"stall_minutes": {"watch": 30}}},
        )
        self.assertTrue(crash)
        self.assertIn("stall", note)
        self.assertIn("neg_reward", note)

    def test_unfinished_stall_no_neg(self):
        snaps_ts = [100000.0] * 5
        crash, note = classify_local(
            "balance", "seed00",
            self._tables(False, None, snaps_ts, [1.0, 2.0, 3.0, -1.0, 4.0]),
            {"risk": {"stall_minutes": {"watch": 30}}},
        )
        self.assertIsNone(crash)
        self.assertIn("no_neg", note)

    def test_unfinished_fresh(self):
        # 尾部无停滞段（timesteps 持续增长）-> 训练中
        snaps_ts = [100000.0, 150000.0, 200000.0, 250000.0, 300000.0]
        crash, note = classify_local(
            "balance", "seed00",
            self._tables(False, None, snaps_ts, [-1.0] * 5),
            {"risk": {"stall_minutes": {"watch": 30}}},
        )
        self.assertIsNone(crash)
        self.assertIn("fresh", note)

    def test_no_snapshots(self):
        tables = {"runs": self._tables(False, None)["runs"],
                  "eval_points": self._tables(False, None)["eval_points"]}
        crash, note = classify_local("balance", "seed00", tables, {})
        self.assertIsNone(crash)
        self.assertEqual(note, "no_snapshots")


if __name__ == "__main__":
    unittest.main()
