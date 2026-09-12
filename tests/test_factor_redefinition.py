"""P0 修复后新因子（kl_divergent / current_stall_minutes / restart_count / neg_ratio_current）单元测试。

覆盖：离线 4 因子计算、规则阈值与 decide 映射、实时状态机口径、mini 双路径一致性。
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import consistency_check as cc
import factors
from collector import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_cfg() -> dict:
    cfg = load_config(PROJECT_ROOT / "config.json")
    cfg["monitor"] = {
        "webpanel_url": "http://test.local:8787",
        "poll_interval_seconds": 5,
        "log_csv": "data/monitor/realtime_log.csv",
        "enable_log": False,
        "total_steps_default": 8000000,
        "total_steps": {},
    }
    return cfg


def make_evals(rewards, ts=None, task="t", seed="s"):
    n = len(rewards)
    ts = ts or [100000 * (i + 1) for i in range(n)]
    return pd.DataFrame({
        "task": [task] * n, "seed": [seed] * n,
        "timesteps": list(ts),
        "mean_reward": list(rewards),
        "std_reward": [0.5] * n,
        "mean_ep_len": [1000.0] * n,
    })


def make_tbs(kl_values, steps=None, task="t", seed="s"):
    n = len(kl_values)
    steps = steps or [50000 * (i + 1) for i in range(n)]
    return pd.DataFrame({
        "task": [task] * n, "seed": [seed] * n,
        "step": list(steps),
        "ep_rew_mean": [10.0] * n, "ep_len_mean": [1000.0] * n,
        "std": [0.8] * n, "value_loss": [0.1] * n,
        "approx_kl": kl_values, "explained_variance": [0.5] * n,
        "learning_rate": [3e-4] * n, "n_updates": [1] * n,
    })


def make_snaps(times, ts_values, task="t", seed="s"):
    n = len(times)
    return pd.DataFrame({
        "time": list(times),
        "task": [task] * n, "seed": [seed] * n,
        "timesteps": list(ts_values),
        "reward": [10.0] * n,
        "cpu_percent": [50.0] * n, "mem_percent": [60.0] * n,
        "swap_percent": [0.0] * n,
    })


def make_runs(completed=True, task="t", seed="s"):
    return pd.DataFrame({
        "task": [task], "seed": [seed], "owner": ["t"],
        "status": ["completed" if completed else "running"],
        "attempts": [0.0], "completed": [completed], "total_steps": [8000000.0],
        "envs": [4.0], "curriculum_steps": [None], "terrain": [None],
        "init_from": [None], "verdict": ["pass"], "success_rate": [None],
        "duration_seconds": [3600.0],
    })


def run_tables(task="t", seed="s"):
    return {
        "eval_points": make_evals([10.0, -5.0, -5.0], task=task, seed=seed),
        "tb_points": make_tbs([0.02, 0.03, 5.0], steps=[50000.0, 150000.0, 250000.0],
                              task=task, seed=seed),
        "snapshots": make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0],
            [100000.0, 100000.0, 100000.0, 300000.0, 8000.0],
            task=task, seed=seed,
        ),
        "runs": make_runs(task=task, seed=seed),
    }


class KlDivergentTest(unittest.TestCase):
    """kl_divergent / kl_divergent_streak 离线计算（按 eval 点对齐）。"""

    def test_trailing_invalid_counts(self):
        tbs = make_tbs([0.02, 0.03, 5.0], steps=[50000.0, 150000.0, 250000.0])
        f = factors.tb_factors(tbs, make_cfg()["risk"]["value_loss"],
                               eval_timesteps=[100000.0, 200000.0, 300000.0])
        self.assertEqual(f["approx_kl_last"], 0.03)
        self.assertTrue(f["kl_divergent"])
        self.assertEqual(f["kl_divergent_streak"], 1)

    def test_all_valid_no_divergence(self):
        tbs = make_tbs([0.02, 0.03, 0.04])
        f = factors.tb_factors(tbs, make_cfg()["risk"]["value_loss"],
                               eval_timesteps=[100000.0, 200000.0, 300000.0])
        self.assertFalse(f["kl_divergent"])
        self.assertEqual(f["kl_divergent_streak"], 0)

    def test_nan_counts_as_divergent(self):
        tbs = make_tbs([0.02, float("nan"), 5.0], steps=[50000.0, 150000.0, 250000.0])
        f = factors.tb_factors(tbs, make_cfg()["risk"]["value_loss"],
                               eval_timesteps=[100000.0, 200000.0, 300000.0])
        self.assertTrue(f["kl_divergent"])
        self.assertEqual(f["kl_divergent_streak"], 2)  # NaN 与 5.0 均计发散

    def test_raw_row_streak_without_alignment(self):
        tbs = make_tbs([0.02, 5.0, 5.0])
        f = factors.tb_factors(tbs, make_cfg()["risk"]["value_loss"])
        self.assertTrue(f["kl_divergent"])
        self.assertEqual(f["kl_divergent_streak"], 2)


class StallRestartTest(unittest.TestCase):
    """current_stall_minutes / restart_count 离线计算。"""

    def test_current_stall_vs_max_so_far(self):
        snaps = make_snaps(
            [0.0, 1800.0, 3600.0, 5400.0, 7200.0],
            [1000.0, 1000.0, 1000.0, 2000.0, 2000.0],
        )
        f = factors.snapshot_factors(snaps, make_cfg()["risk"]["resources"]["idle"])
        self.assertEqual(f["stall_minutes"], 60.0)  # max-so-far 持久
        self.assertEqual(f["current_stall_minutes"], 30.0)  # 尾部段 (7200-5400)/60

    def test_current_stall_resets_on_change(self):
        snaps = make_snaps(
            [0.0, 1800.0, 3600.0, 5400.0],
            [1000.0, 1000.0, 1000.0, 2000.0],
        )
        f = factors.snapshot_factors(snaps, make_cfg()["risk"]["resources"]["idle"])
        self.assertEqual(f["stall_minutes"], 60.0)
        self.assertEqual(f["current_stall_minutes"], 0.0)  # 末点步长变化

    def test_restart_count_spec_definition(self):
        self.assertEqual(
            factors._spec_fall_times(make_snaps([0.0, 30.0], [100000.0, 8000.0])), [])
        self.assertEqual(
            factors._spec_fall_times(make_snaps([0.0, 30.0], [1384448.0, 12288.0])), [])
        self.assertEqual(
            factors._spec_fall_times(make_snaps(
                [0.0, 30.0, 60.0, 90.0], [100000.0, 8000.0, 200000.0, 8000.0])),
            [90.0])
        falls = factors._spec_fall_times(make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0, 150.0],
            [294912.0, 8192.0, 573440.0, 8192.0, 102400.0, 8192.0],
        ))
        self.assertEqual(len(falls), 3)
        self.assertEqual(falls, [30.0, 90.0, 150.0])


class NegRatioCurrentTest(unittest.TestCase):
    """neg_ratio_current 离线分段。"""

    def test_segmented_by_last_restart(self):
        evals = make_evals([1.0, -1.0, -1.0, -1.0], ts=[100000.0, 200000.0, 300000.0, 400000.0])
        snaps = make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0],
            [100000.0, 100000.0, 100000.0, 200000.0, 200000.0,
             8000.0, 8000.0, 200000.0, 300000.0, 400000.0],
        )
        # 回退 200k@120 -> 8000@150；边界截面 = 首个 T>=150 的 eval（300k，T=240）
        self.assertEqual(factors._neg_ratio_current(evals, snaps), 1.0)

    def test_no_falls_falls_back_to_overall(self):
        tables = run_tables()
        del tables["snapshots"]
        f = factors.run_factors("t", "s", tables, make_cfg())
        self.assertAlmostEqual(f["eval_neg_ratio"], 2 / 3, places=4)
        self.assertAlmostEqual(f["neg_ratio_current"], 2 / 3, places=4)  # 无快照 -> 全部尝试口径
        self.assertNotIn("restart_count", f)

    def test_no_falls_equals_overall(self):
        tables = run_tables()
        tables["snapshots"] = make_snaps(
            [0.0, 30.0, 60.0], [100000.0, 200000.0, 300000.0])
        f = factors.run_factors("t", "s", tables, make_cfg())
        self.assertEqual(f["neg_ratio_current"], f["eval_neg_ratio"])

    def test_run_factors_integration(self):
        tables = run_tables()
        f = factors.run_factors("t", "s", tables, make_cfg())
        self.assertEqual(f["restart_count"], 1)  # 300k@90 -> 8000@120
        self.assertEqual(f["current_stall_minutes"], 0.0)
        self.assertEqual(f["stall_minutes"], 1.0)  # 100k 段 60s
        self.assertTrue(f["kl_divergent"])
        self.assertEqual(f["kl_divergent_streak"], 1)
        # 回退（300k@90 -> 8000@120）发生在最后 eval 截面之后：当前尝试为空 -> 全部尝试口径
        self.assertAlmostEqual(f["neg_ratio_current"], 2 / 3, places=4)


class RuleTest(unittest.TestCase):
    """新因子规则阈值与 decide 映射。"""

    def test_kl_divergent_levels(self):
        cfg = make_cfg()
        self.assertEqual(factors.run_risk_items({"kl_divergent_streak": 2}, cfg), [])
        items = factors.run_risk_items({"kl_divergent_streak": 3}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "kl_divergent")])
        items = factors.run_risk_items({"kl_divergent_streak": 5}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R3", "kl_divergent")])

    def test_restart_count_levels(self):
        cfg = make_cfg()
        self.assertEqual(factors.run_risk_items({"restart_count": 1}, cfg), [])
        items = factors.run_risk_items({"restart_count": 2}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "restart")])
        items = factors.run_risk_items({"restart_count": 4}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R3", "restart")])

    def test_neg_ratio_current_levels(self):
        cfg = make_cfg()
        self.assertEqual(factors.run_risk_items({"neg_ratio_current": 0.2}, cfg), [])
        items = factors.run_risk_items({"neg_ratio_current": 0.4}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "neg_ratio_current")])
        items = factors.run_risk_items({"neg_ratio_current": 0.6}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "neg_ratio_current")])

    def test_stall_current_levels(self):
        cfg = make_cfg()
        self.assertEqual(factors.run_risk_items({"current_stall_minutes": 20.0}, cfg), [])
        items = factors.run_risk_items({"current_stall_minutes": 40.0}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "stall_current")])
        items = factors.run_risk_items({"current_stall_minutes": 65.0}, cfg)
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "stall_current")])
        # 已完成 run 不触发当前停滞
        self.assertEqual(
            factors.run_risk_items({"current_stall_minutes": 65.0, "completed": True}, cfg), [])

    def test_decide_mappings(self):
        cfg = make_cfg()
        def decide_for(factor):
            risks = [factors.RiskItem("R2", "x", factor, "msg")]
            return factors.decide({}, risks, cfg)[0]
        self.assertEqual(decide_for("kl_divergent"), "tune")
        self.assertEqual(decide_for("stall_current"), "resize")
        self.assertEqual(decide_for("restart"), "stop")
        self.assertEqual(decide_for("neg_ratio_current"), "stop")


class MiniReplayTest(unittest.TestCase):
    """mini run 双路径一致性（含重启 + KL 发散尾段）。"""

    def test_mini_replay_all_aligned(self):
        tables = {
            "eval_points": make_evals(
                [10.0, 10.0, 10.0, -5.0, -5.0, -5.0],
                ts=[100000.0, 200000.0, 300000.0, 400000.0, 500000.0, 600000.0],
                task="balance", seed="seed00"),
            "tb_points": make_tbs(
                [0.02, 0.02, 5.0, 5.0, 5.0, 5.0],
                steps=[50000.0, 150000.0, 250000.0, 350000.0, 450000.0, 550000.0],
                task="balance", seed="seed00"),
            "snapshots": make_snaps(
                [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0],
                [100000.0, 100000.0, 100000.0, 200000.0, 200000.0,
                 8000.0, 8000.0, 200000.0, 400000.0, 600000.0],
                task="balance", seed="seed00"),
            "runs": make_runs(task="balance", seed="seed00"),
        }
        out = Path(tempfile.gettempdir()) / "factor_redef_replay.csv"
        summary = cc.run_check("balance", "seed00", make_cfg(), out, verbose=False, tables=tables)
        self.assertEqual(summary["total_sections"], 6)
        self.assertEqual(summary["restart_count"], 1)
        aligned = ("eval_drawdown", "eval_neg_ratio", "eval_neg_ratio_recent",
                   "neg_ratio_current", "stall_minutes", "current_stall_minutes",
                   "restart_count", "approx_kl_last", "kl_divergent", "kl_divergent_streak")
        for factor in aligned:
            st = summary["factor_stats"][factor]
            self.assertEqual(st["passed"], 6, factor)
            self.assertEqual(st["failed"], 0, factor)
        self.assertEqual(len(summary["failed_sections"]), 0)
        rows = pd.read_csv(out, encoding="utf-8-sig")
        self.assertEqual(rows["restart_count_offline"].tolist(), [0, 0, 1, 1, 1, 1])
        self.assertEqual(rows["restart_count_online"].tolist(), [0, 0, 1, 1, 1, 1])
        self.assertEqual(rows["kl_divergent_streak_offline"].tolist(), [0, 0, 1, 2, 3, 4])
        self.assertEqual(rows["kl_divergent_streak_online"].tolist(), [0, 0, 1, 2, 3, 4])
        # 边界截面=idx2（300k，奖励 10 属新尝试）：各截面两侧一致
        # 期望序列：前 3 截面无/仅 1 点 -> 0.0，随后 0.5 / 2/3 / 0.75
        for col in ("neg_ratio_current_offline", "neg_ratio_current_online"):
            vals = rows[col].tolist()
            self.assertAlmostEqual(vals[0], 0.0, places=4)
            self.assertAlmostEqual(vals[2], 0.0, places=4)
            self.assertAlmostEqual(vals[3], 0.5, places=4)
            self.assertAlmostEqual(vals[4], 2 / 3, places=4)
            self.assertAlmostEqual(vals[5], 0.75, places=4)


if __name__ == "__main__":
    unittest.main()