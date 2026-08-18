"""滚动回测框架单元测试：时间不泄漏、决策点、指标、插件、确定性。"""

import unittest
from pathlib import Path

import pandas as pd

import backtest_engine as be
import backtest_rules as br
from collector import load_config
from schema import table_columns, validate_frame

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def frame(table: str, rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=table_columns(table))
    validate_frame(df, table)
    return df


def cfg() -> dict:
    return load_config(PROJECT_ROOT / "config.json")


def make_tables(with_unknown=True):
    """三个 run：a/s0=fail(0~100s)、a/s1=unknown(50~120s)、a/s2=pass(150~200s)。"""
    def snaps(task, seed, times):
        rows = []
        for i, t in enumerate(times):
            rows.append((float(t), task, seed, float(i * 200000),
                         50.0, 10.0, 50.0, 1.0, 1.0, 1.0,
                         1000.0, 2000.0, 0.0, 1000.0, 0.0))
        return rows

    def evals(task, seed):
        return [
            (task, seed, 0, 10.0, 0.1, 500.0),
            (task, seed, 200000, 50.0, 0.1, 500.0),
            (task, seed, 400000, 90.0, 0.1, 500.0),
        ]

    def tbs(task, seed):
        return [
            (task, seed, 0, 10.0, 500.0, 0.5, 0.1, 0.02, 0.5, 0.0003, None),
            (task, seed, 200000, 50.0, 500.0, 0.5, 0.1, 0.02, 0.5, 0.0003, None),
            (task, seed, 400000, 90.0, 500.0, 0.5, 0.1, 0.02, 0.5, 0.0003, None),
        ]

    run_rows = [
        ("a", "s0", "local", "completed", 0, True, 400000, 4,
         None, None, None, "fail", None, 100.0),
        ("a", "s1", "local", "running", 0, False, 400000, 4,
         None, None, None, None, None, None),
        ("a", "s2", "local", "completed", 0, True, 400000, 4,
         None, None, None, "pass", None, 50.0),
    ]
    tables = {
        "runs": frame("runs", run_rows),
        "eval_points": frame("eval_points",
                             evals("a", "s0") + evals("a", "s1") + evals("a", "s2")),
        "tb_points": frame("tb_points",
                           tbs("a", "s0") + tbs("a", "s1") + tbs("a", "s2")),
        "snapshots": frame("snapshots",
                           snaps("a", "s0", [0.0, 50.0, 100.0])
                           + snaps("a", "s1", [50.0, 85.0, 120.0])
                           + snaps("a", "s2", [150.0, 175.0, 200.0])),
    }
    return tables


class RollingTest(unittest.TestCase):
    def test_no_time_leakage(self):
        tables = make_tables()
        rows = be.run_backtest(tables, cfg(), be.always_continue, decision_progress=0.5)
        by_run = {r["seed"]: r for r in rows}
        # B 开始于 50，A 结束于 100 -> A 不泄漏进 B 的训练集
        self.assertEqual(by_run["s1"]["train_size"], 0)
        # C 开始于 150，A 结束于 100 -> A 可训练；B 无标签排除
        self.assertEqual(by_run["s2"]["train_size"], 1)

    def test_decision_time(self):
        tables = make_tables()
        self.assertEqual(be.decision_time(tables, "a", "s0", 0.5), 50.0)
        self.assertEqual(be.decision_time(tables, "a", "s0", 0.9), 100.0)
        self.assertIsNone(be.decision_time(tables, "a", "s0", 1.5))

    def test_decision_progress_rows(self):
        tables = make_tables()
        rows30 = be.run_backtest(tables, cfg(), be.always_stop, decision_progress=0.3)
        rows70 = be.run_backtest(tables, cfg(), be.always_stop, decision_progress=0.7)
        r30 = next(r for r in rows30 if r["seed"] == "s0")
        r70 = next(r for r in rows70 if r["seed"] == "s0")
        self.assertLess(r30["t_decision"], r70["t_decision"])

    def test_metrics_always_stop(self):
        tables = make_tables()
        rows = be.run_backtest(tables, cfg(), be.always_stop, decision_progress=0.5)
        agg = be.aggregate_rows(rows)
        self.assertEqual(agg["n_labeled"], 2)   # s0=fail, s2=pass（s1 unknown 不计）
        self.assertEqual(agg["n_stop"], 2)
        self.assertEqual(agg["n_pass"], 1)
        self.assertEqual(agg["n_fail"], 1)
        self.assertAlmostEqual(agg["stop_accuracy"], 0.5)   # 1 hit + 0 continue_ok
        self.assertAlmostEqual(agg["early_stop_precision"], 0.5)
        self.assertAlmostEqual(agg["recall"], 1.0)
        self.assertAlmostEqual(agg["false_kill_rate"], 0.5)
        self.assertGreater(agg["minutes_saved"], 0.0)
        # s0 决策于 t=50，结束于 100 -> 节省 50s
        r0 = next(r for r in rows if r["seed"] == "s0")
        self.assertAlmostEqual(r0["minutes_saved"], round(50.0 / 60.0, 1), places=1)
        self.assertTrue(r0["hit"])
        r2 = next(r for r in rows if r["seed"] == "s2")
        self.assertTrue(r2["false_kill"])

    def test_custom_plugin(self):
        tables = make_tables()

        def custom(train_info, target_online, cfg):
            return {"stop": True, "confidence": 0.9, "reason": "custom decision"}

        rows = be.run_backtest(tables, cfg(), custom, decision_progress=0.5)
        for r in rows:
            if not r["skipped"]:
                self.assertTrue(r["stop"])
                self.assertEqual(r["confidence"], 0.9)
                self.assertEqual(r["reason"], "custom decision")

    def test_rule_plugin_matches_backtest_rules(self):
        tables = make_tables()
        rows = be.run_backtest(tables, cfg(), be.rule_predictor, decision_progress=0.5)
        r0 = next(r for r in rows if r["seed"] == "s0")
        # 奖励 10->50->90 平稳，无 drawdown/stall -> 规则插件应 continue
        self.assertFalse(r0["stop"])

    def test_determinism(self):
        tables = make_tables()
        rows1 = be.run_backtest(tables, cfg(), be.always_stop, decision_progress=0.5)
        rows2 = be.run_backtest(tables, cfg(), be.always_stop, decision_progress=0.5)
        self.assertEqual(rows1, rows2)


if __name__ == "__main__":
    unittest.main()