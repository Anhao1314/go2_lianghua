"""consistency_check 单元测试：本地构造数据回放，无网络。"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import consistency_check as cc
from collector import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_cfg() -> dict:
    cfg = load_config(PROJECT_ROOT / "config.json")
    cfg["monitor"] = {
        "webpanel_url": "http://test.local:8787",
        "poll_interval_seconds": 5,
        "feishu_webhook": "https://test.local/hook",
        "notify_min_level": "R2",
        "cooldown_minutes": 10,
        "log_csv": "data/monitor/realtime_log.csv",
        "enable_log": False,
        "total_steps_default": 8000000,
        "total_steps": {},
    }
    return cfg


def make_evals(rewards, ts=None):
    n = len(rewards)
    ts = ts or [100000 * (i + 1) for i in range(n)]
    return pd.DataFrame({
        "task": ["balance"] * n, "seed": ["seed00"] * n,
        "timesteps": list(ts),
        "mean_reward": list(rewards),
        "std_reward": [0.5] * n,
        "mean_ep_len": [1000.0] * n,
    })


def make_tbs(kl_values, steps=None, n=None):
    n = n if n is not None else len(kl_values)
    steps = steps or [50000 * (i + 1) for i in range(n)]
    kl = list(kl_values) + [0.02] * (n - len(kl_values))
    return pd.DataFrame({
        "task": ["balance"] * n, "seed": ["seed00"] * n,
        "step": list(steps),
        "ep_rew_mean": [10.0] * n, "ep_len_mean": [1000.0] * n,
        "std": [0.8] * n, "value_loss": [0.1] * n,
        "approx_kl": kl, "explained_variance": [0.5] * n,
        "learning_rate": [3e-4] * n, "n_updates": [1] * n,
    })


def make_snaps(times, ts_values):
    n = len(times)
    return pd.DataFrame({
        "time": list(times),
        "task": ["balance"] * n, "seed": ["seed00"] * n,
        "timesteps": list(ts_values),
        "reward": [10.0] * n,
        "cpu_percent": [50.0] * n, "mem_percent": [60.0] * n,
        "swap_percent": [0.0] * n,
    })


def make_runs():
    return pd.DataFrame({
        "task": ["balance"], "seed": ["seed00"], "owner": ["t"], "status": ["completed"],
        "attempts": [0.0], "completed": [True], "total_steps": [8000000.0],
        "envs": [4.0], "curriculum_steps": [None], "terrain": [None], "init_from": [None],
        "verdict": ["pass"], "success_rate": [None], "duration_seconds": [3600.0],
    })


def mini_tables():
    return {
        "eval_points": make_evals([10.0, 20.0, 30.0]),
        "tb_points": make_tbs([0.02, 0.03, 0.04]),
        "snapshots": make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0],
            [100000.0, 100000.0, 100000.0, 200000.0, 300000.0],
        ),
        "runs": make_runs(),
    }


class ConsistencyCheckTest(unittest.TestCase):

    def _run(self, tables, out=None):
        if out is None:
            out = Path(tempfile.gettempdir()) / "consistency_check_test.csv"
        return cc.run_check("balance", "seed00", make_cfg(), out, verbose=False, tables=tables)

    def test_sections_mapping(self):
        evals = make_evals([10.0, 20.0, 30.0])
        snaps = make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0],
            [100000.0, 100000.0, 100000.0, 200000.0, 300000.0],
        )
        secs = cc.build_sections(evals, snaps)
        self.assertEqual([s["timesteps"] for s in secs], [100000.0, 200000.0, 300000.0])
        self.assertEqual([s["section_time"] for s in secs], [0.0, 90.0, 120.0])
        # 回退: eval 步长超过最后快照步长 -> 取最后快照时间
        evals2 = make_evals([10.0], ts=[999999999.0])
        secs2 = cc.build_sections(evals2, snaps)
        self.assertEqual(secs2[0]["section_time"], 120.0)

    def test_clean_mini_run_all_match(self):
        summary = self._run(mini_tables())
        self.assertEqual(summary["total_sections"], 3)
        # 修复后：全部可对齐因子（含新增 4 因子）逐截面一致，stall 在容差内
        aligned = ("eval_drawdown", "eval_neg_ratio", "eval_neg_ratio_recent",
                   "neg_ratio_current", "approx_kl_last", "kl_divergent",
                   "kl_divergent_streak", "stall_minutes", "current_stall_minutes",
                   "restart_count")
        for factor in aligned:
            st = summary["factor_stats"][factor]
            self.assertEqual(st["passed"], 3, factor)
            self.assertEqual(st["failed"], 0, factor)
        self.assertEqual(len(summary["failed_sections"]), 0)

    def test_na_factors_excluded(self):
        summary = self._run(mini_tables())
        for factor in ("eval_std_recent", "eval_slope_per_1e6"):
            st = summary["factor_stats"][factor]
            self.assertEqual(st["na"], 3, factor)
            self.assertEqual(st["failed"], 0, factor)
            self.assertEqual(st["passed"], 0, factor)

    def test_neg_ratio_recent_window_aligned(self):
        # 修复后：实时取 history 尾 recent_window=5 点，与离线 last5 一致
        tables = mini_tables()
        tables["eval_points"] = make_evals([1.0, 1.0, 1.0, 1.0, -1.0, -1.0])
        tables["tb_points"] = make_tbs([0.02] * 6)
        tables["snapshots"] = make_snaps(
            [0.0, 30.0, 60.0, 90.0, 120.0, 150.0],
            [100000.0, 200000.0, 300000.0, 400000.0, 500000.0, 600000.0],
        )
        summary = self._run(tables)
        st = summary["factor_stats"]["eval_neg_ratio_recent"]
        self.assertEqual(st["passed"], 6)
        self.assertEqual(st["failed"], 0)
        self.assertEqual(len(summary["failed_sections"]), 0)
        last_row = pd.read_csv(summary["out_path"], encoding="utf-8-sig").iloc[-1]
        self.assertAlmostEqual(last_row["eval_neg_ratio_recent_offline"], 0.4, places=4)
        self.assertAlmostEqual(last_row["eval_neg_ratio_recent_online"], 0.4, places=4)

    def test_approx_kl_current_invalid(self):
        # 修复后：第 3 截面当前 tb 点 kl=5.0（损坏）: 离线回退 0.03，实时回退 last_valid_kl=0.03
        tables = mini_tables()
        tables["tb_points"] = make_tbs([0.02, 0.03, 5.0], steps=[50000, 150000, 250000])
        summary = self._run(tables)
        st = summary["factor_stats"]["approx_kl_last"]
        self.assertEqual(st["passed"], 3)
        self.assertEqual(st["failed"], 0)
        kd = summary["factor_stats"]["kl_divergent"]
        self.assertEqual(kd["passed"], 3)
        ks = summary["factor_stats"]["kl_divergent_streak"]
        self.assertEqual(ks["passed"], 3)
        rows = pd.read_csv(summary["out_path"], encoding="utf-8-sig")
        last = rows.iloc[-1]
        self.assertAlmostEqual(last["approx_kl_last_offline"], 0.03, places=4)
        self.assertAlmostEqual(last["approx_kl_last_online"], 0.03, places=4)
        self.assertEqual(last["kl_divergent_offline"], True)
        self.assertEqual(last["kl_divergent_online"], True)
        self.assertEqual(last["kl_divergent_streak_offline"], 1)
        self.assertEqual(last["kl_divergent_streak_online"], 1)

    def test_approx_kl_both_none(self):
        # 窗口无任何有效 kl: 离线缺键(视为 None)，实时过滤为 None -> 双 None 通过
        tables = mini_tables()
        tables["tb_points"] = make_tbs([5.0, 5.0, 5.0], steps=[50000, 150000, 250000])
        summary = self._run(tables)
        st = summary["factor_stats"]["approx_kl_last"]
        self.assertEqual(st["passed"], 3)
        self.assertEqual(st["failed"], 0)
        # 全部截面 kl 发散且 streak 逐截面递增（1/2/3），两侧一致
        ks = summary["factor_stats"]["kl_divergent_streak"]
        self.assertEqual(ks["passed"], 3)
        self.assertEqual(ks["failed"], 0)
        rows = pd.read_csv(summary["out_path"], encoding="utf-8-sig")
        self.assertEqual(rows["kl_divergent_streak_offline"].tolist(), [1, 2, 3])
        self.assertEqual(rows["kl_divergent_streak_online"].tolist(), [1, 2, 3])

    def test_stall_simulation_fake_clock(self):
        with cc.OnlineSimulator("balance", "seed00", make_cfg()) as sim:
            sim.poll_snapshot(100000.0, 0.0)
            sim.poll_snapshot(100000.0, 30.0)
            sim.poll_snapshot(100000.0, 60.0)
            f1 = sim.poll_eval(
                cc.build_eval_seed("balance", "seed00", 100000.0, 10.0, [10.0], 0.02, 0.8),
                {}, 120.0,
            )
            self.assertEqual(f1["stall_minutes"], 1.5)  # max-so-far：(120-30)/60
            self.assertEqual(f1["current_stall_minutes"], 1.5)
            sim.poll_snapshot(200000.0, 150.0)
            f2 = sim.poll_eval(
                cc.build_eval_seed("balance", "seed00", 200000.0, 20.0, [10.0, 20.0], 0.03, 0.8),
                {}, 150.0,
            )
            self.assertEqual(f2["stall_minutes"], 1.5)  # max-so-far 持久
            self.assertEqual(f2["current_stall_minutes"], 0.0)  # 当前停滞归零

    def test_current_stall_minutes(self):
        snaps = make_snaps([0.0, 30.0, 60.0], [100000.0, 100000.0, 100000.0])
        self.assertAlmostEqual(cc._current_stall_minutes(snaps), 1.0)
        snaps2 = make_snaps(
            [0.0, 30.0, 60.0, 90.0],
            [100000.0, 100000.0, 100000.0, 200000.0],
        )
        self.assertEqual(cc._current_stall_minutes(snaps2), 0.0)
        self.assertEqual(cc._current_stall_minutes(make_snaps([0.0], [100000.0])), 0.0)
        self.assertEqual(cc._current_stall_minutes(pd.DataFrame()), 0.0)

    def test_restart_count(self):
        self.assertEqual(cc._restart_count(make_snaps([0.0, 30.0, 60.0], [100000.0, 100000.0, 200000.0])), 0)
        # 规格定义：>100k -> <10k；100k->8k 不算（100k 不 >100k）
        self.assertEqual(
            cc._restart_count(make_snaps([0.0, 30.0, 60.0, 90.0], [100000.0, 8000.0, 200000.0, 8000.0])),
            1,
        )
        # 1384448->12288 不满足 <10k，不计
        self.assertEqual(
            cc._restart_count(make_snaps([0.0, 30.0], [1384448.0, 12288.0])), 0)
        # 迷你 run 无回退
        self.assertEqual(cc._restart_count(mini_tables()["snapshots"]), 0)
        # 真实数据存在规格回退（balance/seed00 快照流，3 次）
        cfg = make_cfg()
        snaps = cc._run_frame(pd.read_csv(PROJECT_ROOT / "data/datasets/snapshots.csv"),
                              "balance", "seed00", by="time")
        self.assertEqual(cc._restart_count(snaps), 3)

    def test_no_snapshots_raises(self):
        tables = mini_tables()
        tables["snapshots"] = pd.DataFrame(columns=["time", "task", "seed", "timesteps"])
        with self.assertRaises(ValueError):
            self._run(tables)

    def test_csv_output_and_determinism(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "a.csv"
            p2 = Path(td) / "b.csv"
            s1 = self._run(mini_tables(), out=p1)
            s2 = self._run(mini_tables(), out=p2)
            b1 = p1.read_bytes()
            b2 = p2.read_bytes()
            self.assertTrue(b1.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(b1, b2)
            self.assertEqual(s1["total_sections"], s2["total_sections"])
            cols = pd.read_csv(p1, encoding="utf-8-sig").columns.tolist()
            expected = ["timesteps", "section_time"]
            for f in cc.COMPARE_SPECS:
                expected += [f"{f}_offline", f"{f}_online", f"{f}_abs_diff", f"{f}_passed"]
            self.assertEqual(cols, expected)
            self.assertEqual(len(pd.read_csv(p1, encoding="utf-8-sig")), 3)


if __name__ == "__main__":
    unittest.main()