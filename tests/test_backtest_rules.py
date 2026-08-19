"""规则止损回测单元测试：重放截断、首次触发、节省估算、三层标签、赔率表。"""

import unittest
from pathlib import Path

import pandas as pd

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


def snaps_rows(times, steps, task="t", seed="s", cpu=10.0):
    """构造 snapshots 行：time/task/seed/timesteps/reward/cpu 等。"""
    return [
        (t, task, seed, float(step), 50.0, cpu, 50.0, 1.0, 1.0, 1.0,
         1000.0, 2000.0, 0.0, 1000.0, 0.0)
        for t, step in zip(times, steps)
    ]


def tb_rows(steps, task="t", seed="s"):
    return [
        (task, seed, step, 50.0, 500.0, 0.5, 0.1, 0.02, 0.5, 0.0003, None)
        for step in steps
    ]


class ProgressTest(unittest.TestCase):
    def test_progress_at(self):
        snaps = frame("snapshots", snaps_rows([1000.0, 2000.0], [100000.0, 200000.0]))
        self.assertEqual(br.progress_at(snaps, 1500.0), 100000.0)
        self.assertEqual(br.progress_at(snaps, 2000.0), 200000.0)
        self.assertIsNone(br.progress_at(snaps, 500.0))

    def test_online_view_truncation(self):
        tables = {
            "eval_points": frame("eval_points", [
                ("t", "s", 100000, 10.0, 0.1, 500.0),
                ("t", "s", 200000, 20.0, 0.1, 500.0),
                ("t", "s", 300000, 30.0, 0.1, 500.0),
            ]),
            "tb_points": frame("tb_points", tb_rows([100000, 200000, 300000])),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 3000.0], [100000.0, 200000.0, 300000.0])),
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, 400000, 4,
                 None, None, None, None, None, None),
            ]),
        }
        view = br.online_view(tables, "t", "s", 1500.0)
        self.assertEqual(len(view["snapshots"]), 1)
        self.assertEqual(len(view["eval_points"]), 1)
        self.assertEqual(len(view["tb_points"]), 1)
        view2 = br.online_view(tables, "t", "s", 2500.0)
        self.assertEqual(len(view2["eval_points"]), 2)
        self.assertEqual(len(view2["tb_points"]), 2)

    def test_online_view_completed_forced_false(self):
        tables = {
            "snapshots": frame("snapshots", snaps_rows([1000.0], [100000.0])),
            "runs": frame("runs", [
                ("t", "s", "local", "completed", 0, True, 400000, 4,
                 None, None, None, None, None, 6000.0),
            ]),
        }
        view = br.online_view(tables, "t", "s", 1500.0)
        self.assertFalse(bool(view["runs"]["completed"].iloc[0]))
        self.assertNotIn("reports", view)


class ReplayTest(unittest.TestCase):
    def test_first_stop_trigger_time(self):
        tables = {
            "eval_points": frame("eval_points", [
                ("t", "s", 100000, 100.0, 0.1, 500.0),
                ("t", "s", 200000, 110.0, 0.1, 500.0),
                ("t", "s", 300000, 70.0, 0.1, 500.0),  # 回撤 36%>30%
            ]),
            "tb_points": frame("tb_points", tb_rows([100000, 200000, 300000])),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 3000.0], [100000.0, 200000.0, 300000.0])),
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, 400000, 4,
                 None, None, None, None, None, None),
            ]),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        # first_r2 与 first_stop 是同一触发的两条记录，按时刻去重
        stops = sorted({e.trigger_time for e in events if e.decision == "stop"})
        self.assertEqual(stops, [3000.0])  # 末快照时刻补扫
        first = next(e for e in events if e.decision == "stop")
        self.assertIn("drawdown", first.factors)
        self.assertEqual(first.level, "R2")

    def test_reports_not_in_trigger(self):
        # 奖励平稳无回撤；验收含失败场景但不参与在线触发
        tables = {
            "eval_points": frame("eval_points", [
                ("t", "s", 100000, 100.0, 0.1, 500.0),
                ("t", "s", 200000, 105.0, 0.1, 500.0),
                ("t", "s", 300000, 110.0, 0.1, 500.0),
            ]),
            "tb_points": frame("tb_points", tb_rows([100000, 200000, 300000])),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 3000.0], [100000.0, 200000.0, 300000.0])),
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, 400000, 4,
                 None, None, None, None, None, None),
            ]),
            "reports": frame("reports", [
                ("t", "s", "scenario", "fail", False, 0.0, 0.2, None,
                 None, None, None, None, None, None, None, None, False),
            ]),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        self.assertEqual(events, [])
        self.assertEqual(br.ground_truth(tables["runs"], tables["reports"], "t", "s"), "fail")
class LabelTest(unittest.TestCase):
    def test_ground_truth_three_labels(self):
        runs = frame("runs", [
            ("a", "s0", "local", "completed", 0, True, 400000, 4,
             None, None, None, "pass", None, 6000.0),
            ("a", "s1", "local", "completed", 0, True, 400000, 4,
             None, None, None, "fail", None, 6000.0),
            ("a", "s2", "local", "completed", 0, True, 400000, 4,
             None, None, None, None, None, 6000.0),
            ("a", "s3", "local", "running", 0, False, 400000, 4,
             None, None, None, None, None, None),
        ])
        reports = frame("reports", [
            ("a", "s2", "scenario", None, True, 1.0, 0.05, 0.4,
             None, None, None, None, None, None, None, None, False),
            ("a", "s3", "scenario", None, False, 0.0, 0.2, None,
             None, None, None, None, None, None, None, None, False),
        ])
        self.assertEqual(br.ground_truth(runs, reports, "a", "s0"), "pass")
        self.assertEqual(br.ground_truth(runs, reports, "a", "s1"), "fail")
        # completed=True 但 verdict 缺失：不构成 pass（未知）
        self.assertEqual(br.ground_truth(runs, reports, "a", "s2"), "unknown")
        # reports 含失败场景 -> fail
        self.assertEqual(br.ground_truth(runs, reports, "a", "s3"), "fail")

    def test_fail_score_formula(self):
        # 完成且 pass：低分
        f_ok = {"progress_ratio": 1.0, "reward_peak_ratio": 0.95,
                "approx_kl_last": 0.02, "value_loss_divergent": False,
                "std_last": 0.5, "eval_last_reward": 95.0}
        row_ok = {"completed": True, "verdict": "pass"}
        score_ok = br.fail_score(f_ok, row_ok, [90.0, 95.0, 80.0])
        self.assertLess(score_ok, 0.2)
        # 未完成、fail、停滞+发散：高分
        f_bad = {"progress_ratio": 0.8, "reward_peak_ratio": 0.3,
                 "approx_kl_last": 0.5, "value_loss_divergent": True,
                 "std_last": 0.005, "eval_last_reward": 10.0}
        row_bad = {"completed": False, "verdict": "fail"}
        score_bad = br.fail_score(f_bad, row_bad, [90.0, 95.0, 80.0])
        self.assertGreater(score_bad, 0.7)

    def test_stagnation_score(self):
        self.assertEqual(br.stagnation_score(0.8, 0.3), 1.0)   # 明确停滞
        self.assertEqual(br.stagnation_score(0.2, 0.9), 0.0)    # 早期无停滞
        self.assertGreater(br.stagnation_score(0.8, 0.5), 0.0)  # 线性区
        self.assertEqual(br.stagnation_score(None, 0.5), 0.0)

    def test_divergence_and_rank(self):
        f = {"approx_kl_last": 0.2, "value_loss_divergent": False, "std_last": 0.5}
        self.assertEqual(br.divergence_score(f), 1.0)  # kl/0.1 归一化封顶
        f2 = {"approx_kl_last": 0.02, "value_loss_divergent": True, "std_last": 0.5}
        self.assertEqual(br.divergence_score(f2), 1.0)
        f3 = {"approx_kl_last": 0.02, "value_loss_divergent": False, "std_last": 0.005}
        self.assertEqual(br.divergence_score(f3), 1.0)  # std 塌缩
        self.assertEqual(br.reward_rank(90.0, [80.0, 90.0, 100.0]), 2 / 3)


class SavingsTest(unittest.TestCase):
    def _tables(self, run_row, times, steps):
        return {
            "snapshots": frame("snapshots", snaps_rows(times, steps)),
            "runs": frame("runs", [run_row]),
        }

    def test_estimate_t_end_actual(self):
        tables = self._tables(
            ("t", "s", "local", "completed", 0, True, 400000, 4,
             None, None, None, None, None, 6000.0),
            [1000.0, 3000.0], [100000.0, 300000.0])
        t_end, method = br.estimate_t_end(tables, "t", "s", 3000.0)
        self.assertEqual((t_end, method), (7000.0, "actual"))

    def test_estimate_t_end_step_rate(self):
        tables = self._tables(
            ("t", "s", "local", "running", 0, False, 600000, 4,
             None, None, None, None, None, None),
            [1000.0, 3000.0], [100000.0, 300000.0])
        t_end, method = br.estimate_t_end(tables, "t", "s", 3000.0)
        # elapsed=2000s，进度 300k/600k -> 预期总时长 4000s
        self.assertEqual(method, "step_rate")
        self.assertAlmostEqual(t_end, 5000.0, places=3)

    def test_estimate_t_end_task_mean_fallback(self):
        tables = {
            "snapshots": frame("snapshots", snaps_rows([1000.0, 3000.0], [100000.0, 300000.0])),
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, None, 4,
                 None, None, None, None, None, None),
                ("t", "s_old", "local", "completed", 0, True, 400000, 4,
                 None, None, None, None, None, 7200.0),
            ]),
        }
        t_end, method = br.estimate_t_end(tables, "t", "s", 3000.0)
        self.assertEqual(method, "task_mean")
        self.assertAlmostEqual(t_end, 8200.0, places=3)


class OddsTableTest(unittest.TestCase):
    def test_zero_pass_false_kill_na(self):
        rows = [
            {"task": "a", "seed": "s0", "level": "R2", "trigger_time": 1.0,
             "factors": "drawdown", "progress_ratio": 0.5, "label": "fail",
             "fail_score": 0.8, "proxy_pass": False, "t_end": 100.0,
             "t_end_method": "actual", "saved_minutes": 60.0,
             "saved_yuan_compute": 2.5, "messages": "x"},
            {"task": "a", "seed": "s1", "level": "R2", "trigger_time": 1.0,
             "factors": "drawdown", "progress_ratio": 0.5, "label": "unknown",
             "fail_score": 0.2, "proxy_pass": False, "t_end": 100.0,
             "t_end_method": "step_rate", "saved_minutes": 30.0,
             "saved_yuan_compute": 1.25, "messages": "x"},
        ]
        odds = br.build_odds_table(rows, cfg())
        self.assertEqual(odds.iloc[0]["false_kill_rate"], "N/A (no pass samples)")
        self.assertEqual(int(odds.iloc[0]["n_pass"]), 0)
        self.assertEqual(int(odds.iloc[0]["n_fail"]), 1)

    def test_expected_net_saving_with_penalty(self):
        rows = [
            {"task": "a", "seed": "s0", "level": "R2", "trigger_time": 1.0,
             "factors": "drawdown", "progress_ratio": 0.5, "label": "fail",
             "fail_score": 0.8, "proxy_pass": False, "t_end": 100.0,
             "t_end_method": "actual", "saved_minutes": 100.0,
             "saved_yuan_compute": 4.0, "messages": "x"},
            {"task": "a", "seed": "s1", "level": "R2", "trigger_time": 1.0,
             "factors": "drawdown", "progress_ratio": 0.5, "label": "pass",
             "fail_score": 0.1, "proxy_pass": True, "t_end": 100.0,
             "t_end_method": "actual", "saved_minutes": 50.0,
             "saved_yuan_compute": 2.0, "messages": "x"},
        ]
        odds = br.build_odds_table(rows, cfg())
        row = odds.iloc[0]
        self.assertEqual(int(row["trigger_count"]), 2)
        self.assertEqual(row["hit_rate"], 0.5)
        self.assertEqual(row["false_kill_rate"], 0.5)
        # 期望净节省 = 0.5*100 - 0.5*50 = 25
        self.assertAlmostEqual(row["expected_net_saving_minutes"], 25.0, places=3)
        self.assertEqual(row["t_end_method_dist"], "actual:2")

    def test_t_end_method_column(self):
        rows = [
            {"task": "a", "seed": "s0", "level": "R2", "trigger_time": 1.0,
             "factors": "stall", "progress_ratio": 0.5, "label": "unknown",
             "fail_score": 0.5, "proxy_pass": False, "t_end": 100.0,
             "t_end_method": "step_rate", "saved_minutes": 30.0,
             "saved_yuan_compute": 1.0, "messages": "x"},
            {"task": "a", "seed": "s1", "level": "R2", "trigger_time": 1.0,
             "factors": "stall", "progress_ratio": 0.5, "label": "unknown",
             "fail_score": 0.5, "proxy_pass": False, "t_end": 100.0,
             "t_end_method": "task_mean", "saved_minutes": 30.0,
             "saved_yuan_compute": 1.0, "messages": "x"},
        ]
        odds = br.build_odds_table(rows, cfg())
        self.assertEqual(odds.iloc[0]["t_end_method_dist"], "step_rate:1;task_mean:1")

class EarlyLowRewardReplayTest(unittest.TestCase):
    """early_low_reward 回放与归因：以全量窗口因子为准，窗口闭合步长触发。"""

    def _runs(self, task="t", seed="s", total_steps=600000):
        return frame("runs", [
            (task, seed, "local", "running", 0, False, total_steps, 4,
             None, None, None, None, None, None),
        ])

    def _evals(self, rows, task="t", seed="s"):
        return frame("eval_points", [
            (task, seed, ts, rew, 0.1, 500.0) for ts, rew in rows
        ])

    def _tb(self, steps, task="t", seed="s"):
        return frame("tb_points", tb_rows(steps, task, seed))

    def test_no_snapshot_low_reward_triggers_at_window_close(self):
        tables = {
            "eval_points": self._evals([(50000, 10.0), (100000, -5.0), (150000, -8.0)]),
            "tb_points": self._tb([50000, 100000, 150000]),
            "runs": self._runs(),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.level, "R2")
        self.assertEqual(ev.decision, "stop")
        self.assertEqual(ev.trigger_time, 150000.0)  # 600000*0.25 窗口闭合步长
        self.assertEqual(ev.factors, ("early_low_reward",))
        self.assertEqual(ev.progress_ratio, 0.25)

    def test_no_snapshot_high_reward_no_event(self):
        tables = {
            "eval_points": self._evals([(50000, 100.0), (100000, 110.0), (150000, 120.0)]),
            "tb_points": self._tb([50000, 100000, 150000]),
            "runs": self._runs(),
        }
        self.assertEqual(br.replay_run(tables, "t", "s", cfg(), step_minutes=10), [])

    def test_no_snapshot_late_early_point_invalidates(self):
        # 窗口内第 4 点 reward=35 >= 阈值 30：全量因子 False，前缀首真不作数
        tables = {
            "eval_points": self._evals([
                (50000, 10.0), (100000, 5.0), (140000, 8.0), (150000, 35.0)]),
            "tb_points": self._tb([50000, 100000, 140000, 150000]),
            "runs": self._runs(),
        }
        self.assertEqual(br.replay_run(tables, "t", "s", cfg(), step_minutes=10), [])

    def test_early_attributed_to_later_stop(self):
        # 首次 stop 在窗口闭合前（2 点回撤 50%），early 事后归因并入
        tables = {
            "eval_points": self._evals([
                (50000, 20.0), (100000, 10.0), (150000, 5.0)]),
            "tb_points": self._tb([50000, 100000, 150000]),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 3000.0], [50000.0, 100000.0, 150000.0])),
            "runs": self._runs(),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        stops = [e for e in events if e.decision == "stop"]
        self.assertTrue(stops)
        self.assertNotIn("early_low_reward", stops[0].factors)
        rows = br.enrich_stop_events(stops, tables, cfg())
        self.assertIn("early_low_reward", rows[0]["factors"].split(";"))

    def test_early_included_directly_when_window_complete(self):
        # stop 时窗口已闭合（3 点均 < 阈值）：early 直接进入 stop 因子集
        tables = {
            "eval_points": self._evals([
                (50000, 20.0), (100000, 15.0), (150000, 4.0), (200000, 4.0)]),
            "tb_points": self._tb([50000, 100000, 150000, 200000]),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 3000.0, 4000.0],
                [50000.0, 100000.0, 150000.0, 200000.0])),
            "runs": self._runs(),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        stops = [e for e in events if e.decision == "stop"]
        self.assertTrue(stops)
        self.assertIn("early_low_reward", stops[0].factors)

    def test_early_removed_when_final_factor_false(self):
        # stop 时前缀含 early（3 点 < 30），但窗口内后续点 35 >= 30：守卫移除
        tables = {
            "eval_points": self._evals([
                (50000, 5.0), (100000, 10.0), (140000, 12.0), (150000, 35.0)]),
            "tb_points": self._tb([50000, 100000, 140000, 150000]),
            "snapshots": frame("snapshots", snaps_rows(
                [1000.0, 2000.0, 2800.0, 3000.0, 4000.0],
                [50000.0, 100000.0, 140000.0, 150000.0, 200000.0])),
            "runs": self._runs(),
        }
        events = br.replay_run(tables, "t", "s", cfg(), step_minutes=10)
        stops = [e for e in events if e.decision == "stop"]
        self.assertTrue(stops)
        self.assertIn("early_low_reward", stops[0].factors)
        rows = br.enrich_stop_events(stops, tables, cfg())
        self.assertNotIn("early_low_reward", rows[0]["factors"].split(";"))

    def test_estimate_t_end_no_snapshot(self):
        tables = {
            "eval_points": self._evals([(50000, 10.0), (100000, -5.0), (150000, -8.0)]),
            "runs": self._runs(),
        }
        t_end, method = br.estimate_t_end(tables, "t", "s", 150000.0)
        self.assertEqual(method, "no_snapshot")
        self.assertEqual(t_end, 150000.0)



if __name__ == "__main__":
    unittest.main()