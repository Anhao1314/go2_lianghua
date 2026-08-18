"""量化因子与风控规则单元测试：构造小样本覆盖各规则与分级边界。"""

import json
import unittest
from pathlib import Path

import pandas as pd

import factors
from collector import load_config
from schema import table_columns, validate_frame

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def frame(table: str, rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=table_columns(table))
    validate_frame(df, table)
    return df


def cfg() -> dict:
    return load_config(PROJECT_ROOT / "config.json")


class FactorComputeTest(unittest.TestCase):
    """因子计算正确性。"""

    def test_eval_factors_drawdown(self):
        df = frame("eval_points", [
            ("balance", "seed00", 100000, 100.0, 0.1, 500.0),
            ("balance", "seed00", 200000, 110.0, 0.2, 500.0),
            ("balance", "seed00", 300000, 90.0, 0.3, 500.0),
        ])
        f = factors.eval_factors(df)
        self.assertEqual(f["eval_peak_reward"], 110.0)
        self.assertEqual(f["eval_last_reward"], 90.0)
        self.assertAlmostEqual(f["eval_drawdown"], 0.1818, places=3)
        self.assertAlmostEqual(f["reward_peak_ratio"], 90.0 / 110.0, places=4)
        self.assertAlmostEqual(f["eval_std_recent"], 0.2, places=4)

    def test_eval_slope(self):
        df = frame("eval_points", [
            ("t", "s", 100000, 10.0, 0.0, 100.0),
            ("t", "s", 200000, 20.0, 0.0, 100.0),
            ("t", "s", 300000, 30.0, 0.0, 100.0),
        ])
        f = factors.eval_factors(df)
        self.assertAlmostEqual(f["eval_slope_per_1e6"], 100.0, places=2)

    def test_eval_neg_ratio_basic(self):
        df = frame("eval_points", [
            ("t", "s", 100000, 10.0, 0.1, 100.0),
            ("t", "s", 200000, 20.0, 0.1, 100.0),
            ("t", "s", 300000, -5.0, 0.1, 100.0),
            ("t", "s", 400000, -10.0, 0.1, 100.0),
            ("t", "s", 500000, 15.0, 0.1, 100.0),
        ])
        f = factors.eval_factors(df)
        self.assertAlmostEqual(f["eval_neg_ratio"], 0.4, places=4)
        self.assertAlmostEqual(f["eval_neg_ratio_recent"], 0.4, places=4)

    def test_eval_neg_ratio_all_positive(self):
        df = frame("eval_points", [
            ("t", "s", 100000 + i * 100000, float(10 + i), 0.1, 100.0)
            for i in range(5)
        ])
        f = factors.eval_factors(df)
        self.assertEqual(f["eval_neg_ratio"], 0.0)
        self.assertEqual(f["eval_neg_ratio_recent"], 0.0)

    def test_eval_neg_ratio_all_negative(self):
        df = frame("eval_points", [
            ("t", "s", 100000 + i * 100000, float(-(i + 1)), 0.1, 100.0)
            for i in range(5)
        ])
        f = factors.eval_factors(df)
        self.assertEqual(f["eval_neg_ratio"], 1.0)
        self.assertEqual(f["eval_neg_ratio_recent"], 1.0)

    def test_eval_slope_ls_linear(self):
        df = frame("eval_points", [
            ("t", "s", i, float(10 + 10 * i), 0.1, 100.0) for i in range(5)
        ])
        f = factors.eval_factors(df)
        # 每步 +10，最小二乘斜率 x1e6 = 10*1e6
        self.assertAlmostEqual(f["eval_slope_per_1e6"], 10000000.0, places=0)

    def test_eval_slope_noisy_less_extreme_than_first_last(self):
        df = frame("eval_points", [
            ("t", "s", 0, 10.0, 0.1, 100.0),
            ("t", "s", 1, 100.0, 0.1, 100.0),
            ("t", "s", 2, 20.0, 0.1, 100.0),
            ("t", "s", 3, 30.0, 0.1, 100.0),
            ("t", "s", 4, 40.0, 0.1, 100.0),
        ])
        f = factors.eval_factors(df)
        ls = abs(f["eval_slope_per_1e6"])
        first_last = abs((40.0 - 10.0) / 4.0 * 1e6)
        self.assertLess(ls, first_last)

    def test_eval_drawdown_clipped_when_negative_tail(self):
        # 末值为负：旧实现会给出 (110-(-18.8))/110=1.17 这类 >1 的伪回撤
        df = frame("eval_points", [
            ("t", "s", 100000, 100.0, 0.1, 500.0),
            ("t", "s", 200000, 110.0, 0.2, 500.0),
            ("t", "s", 300000, -18.8, 0.3, 500.0),
        ])
        f = factors.eval_factors(df)
        self.assertEqual(f["eval_drawdown"], 1.0)
        self.assertAlmostEqual(f["reward_peak_ratio"], -18.8 / 110.0, places=4)

    def test_eval_drawdown_zero_when_peak_nonpositive(self):
        df = frame("eval_points", [
            ("t", "s", 100000, -1.0, 0.1, 500.0),
            ("t", "s", 200000, -0.5, 0.2, 500.0),
        ])
        f = factors.eval_factors(df)
        self.assertEqual(f["eval_drawdown"], 0.0)

    def test_eval_drawdown_absent_when_last_nan(self):
        df = frame("eval_points", [
            ("t", "s", 100000, 100.0, 0.1, 500.0),
            ("t", "s", 200000, None, 0.2, 500.0),
        ])
        f = factors.eval_factors(df)
        self.assertNotIn("eval_drawdown", f)

    def test_approx_kl_filters_implausible_tail(self):
        # 末点脏值 122376 被过滤，回退到最近有效值 0.02
        rows = [
            ("t", "s", 4096, 1.0, 500.0, 0.9, 1.0, 0.02, 0.5, 0.0003, 1),
            ("t", "s", 8192, 1.0, 500.0, 0.9, 1.0, 122376.375, 0.5, 0.0003, 2),
        ]
        f = factors.tb_factors(frame("tb_points", rows), cfg()["risk"]["value_loss"])
        self.assertEqual(f["approx_kl_last"], 0.02)

    def test_approx_kl_all_implausible_absent(self):
        rows = [
            ("t", "s", 4096, 1.0, 500.0, 0.9, 1.0, 0.0, 0.5, 0.0003, 1),
            ("t", "s", 8192, 1.0, 500.0, 0.9, 1.0, 122376.375, 0.5, 0.0003, 2),
        ]
        f = factors.tb_factors(frame("tb_points", rows), cfg()["risk"]["value_loss"])
        self.assertNotIn("approx_kl_last", f)

    def test_tb_factors(self):
        rows = [("t", "s", 4096 * (i + 1), 1.0, 500.0, 0.9, 1.0, 0.02, 0.5, 0.0003, 1)
                for i in range(3)]
        f = factors.tb_factors(frame("tb_points", rows), cfg()["risk"]["value_loss"])
        self.assertEqual(f["approx_kl_last"], 0.02)
        self.assertEqual(f["std_last"], 0.9)
        self.assertEqual(f["ev_neg_streak"], 0)
        self.assertFalse(f["value_loss_divergent"])

    def test_acceptance_factors(self):
        rows = [
            ("t", "s", "a", "pass", True, 1.0, 0.05, 0.3, 10.0, False, 2.0, 0.0, 0.0, 0.0, 100.0, 0.9, False),
            ("t", "s", "b", "fail", False, 0.0, 0.2, 0.02, 0.0, False, 0.0, 0.0, 0.0, 3.0, 10.0, 0.1, True),
        ]
        f = factors.acceptance_factors(frame("reports", rows))
        self.assertEqual(f["report_rows"], 2)
        self.assertEqual(f["verdict_fail_ratio"], 0.5)
        self.assertEqual(f["nan_count"], 1)
        self.assertAlmostEqual(f["max_dev_max"], 0.2)
        self.assertAlmostEqual(f["min_clear_min"], 0.02)

    def test_snapshot_stall_and_span(self):
        rows = [
            (0.0, "t", "s", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
            (1800.0, "t", "s", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
            (3600.0, "t", "s", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
            (5400.0, "t", "s", 2000.0, 2.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
        ]
        f = factors.snapshot_factors(frame("snapshots", rows), cfg()["risk"]["resources"]["idle"])
        self.assertEqual(f["stall_minutes"], 60.0)
        self.assertEqual(f["time_span_minutes"], 90.0)
        self.assertEqual(f["cpu_percent_max"], 50.0)


class RiskRuleTest(unittest.TestCase):
    """风控规则触发与分级边界（R1/R2/R3）。"""

    def test_drawdown_none_watch_warn(self):
        for dd, expected in ((0.10, []), (0.20, ["R1"]), (0.40, ["R2"])):
            items = factors.run_risk_items({"eval_drawdown": dd}, cfg())
            self.assertEqual([i.level for i in items], expected, msg=f"dd={dd}")
            if expected:
                self.assertEqual(items[0].factor, "drawdown")

    def test_kl_none_watch_warn(self):
        for kl, expected in ((0.02, []), (0.07, ["R1"]), (0.20, ["R2"])):
            items = factors.run_risk_items({"approx_kl_last": kl}, cfg())
            self.assertEqual([i.level for i in items], expected, msg=f"kl={kl}")

    def test_ev_neg_streak(self):
        self.assertEqual(factors.run_risk_items({"ev_neg_streak": 5}, cfg()), [])
        items = factors.run_risk_items({"ev_neg_streak": 12}, cfg())
        self.assertEqual([i.level for i in items], ["R2"])
        self.assertEqual(items[0].factor, "explained_variance")

    def test_std_collapse_and_explode(self):
        self.assertEqual(factors.run_risk_items({"std_last": 0.01}, cfg())[0].level, "R1")
        self.assertEqual(factors.run_risk_items({"std_last": 0.9}, cfg()), [])
        self.assertEqual(factors.run_risk_items({"std_last": 2.0}, cfg())[0].level, "R2")

    def test_neg_ratio_rules(self):
        # 整体 >0.3 -> R1；recent >0.5 -> R2（优先）
        items = factors.run_risk_items(
            {"eval_neg_ratio": 0.4, "eval_neg_ratio_recent": 0.2}, cfg())
        self.assertEqual([i.level for i in items], ["R1"])
        self.assertEqual(items[0].factor, "neg_ratio")
        items = factors.run_risk_items(
            {"eval_neg_ratio": 0.2, "eval_neg_ratio_recent": 0.6}, cfg())
        self.assertEqual([i.level for i in items], ["R2"])
        self.assertEqual(items[0].factor, "neg_ratio")
        items = factors.run_risk_items(
            {"eval_neg_ratio": 0.2, "eval_neg_ratio_recent": 0.4}, cfg())
        self.assertEqual(items, [])
        items = factors.run_risk_items(
            {"eval_neg_ratio": 0.6, "eval_neg_ratio_recent": 0.6}, cfg())
        self.assertEqual(items[0].level, "R2")

    def test_std_reward_collapse_rule(self):
        items = factors.run_risk_items(
            {"eval_points": 5, "eval_std_recent": 0.005}, cfg())
        self.assertEqual([i.level for i in items], ["R1"])
        self.assertEqual(items[0].factor, "std_reward_collapse")
        self.assertEqual(factors.run_risk_items(
            {"eval_points": 5, "eval_std_recent": 0.1}, cfg()), [])
        # 评估点数不足 5 不判
        self.assertEqual(factors.run_risk_items(
            {"eval_points": 4, "eval_std_recent": 0.005}, cfg()), [])

    def test_decide_neg_ratio_stop(self):
        items = [factors.RiskItem("R2", "eval_points", "neg_ratio", "neg")]
        decision, msgs = factors.decide({"eval_drawdown": 0.0}, items, cfg())
        self.assertEqual(decision, "stop")
        self.assertEqual(msgs, ["neg"])

    def test_value_loss_divergence(self):
        vl_cfg = cfg()["risk"]["value_loss"]
        flat = frame("tb_points", [
            ("t", "s", 4096 * (i + 1), 1.0, 500.0, 0.9, 1.0, 0.01, 0.5, 0.0003, 1)
            for i in range(15)
        ])
        self.assertFalse(factors.tb_factors(flat, vl_cfg)["value_loss_divergent"])
        rows = [("t", "s", 4096 * (i + 1), 1.0, 500.0, 0.9, val, 0.01, 0.5, 0.0003, 1)
                for i, val in enumerate([1.0] * 5 + [10, 20, 30, 40, 50, 60, 70, 80, 90, 100])]
        f = factors.tb_factors(frame("tb_points", rows), vl_cfg)
        self.assertTrue(f["value_loss_divergent"])
        items = factors.run_risk_items(f, cfg())
        self.assertIn("value_loss", {i.factor for i in items})
        self.assertEqual(max(i.level for i in items), "R2")

    def test_stagnation_triggered(self):
        tables = {
            "eval_points": frame("eval_points", [
                ("t", "s", 500000, 50.0, 0.0, 100.0),
                ("t", "s", 3000000, 100.0, 0.0, 100.0),
                ("t", "s", 6000000, 50.0, 0.0, 100.0),
            ]),
            "runs": frame("runs", [
                ("t", "s", "cloud", "running", 1, False, 8000000, 8, 0, "hfield", "", None, None, None),
            ]),
        }
        f = factors.run_factors("t", "s", tables, cfg())
        self.assertEqual(f["progress_ratio"], 0.75)
        items = factors.run_risk_items(f, cfg())
        self.assertIn("stagnation", {i.factor for i in items})

    def test_stagnation_not_triggered_when_climbing(self):
        tables = {
            "eval_points": frame("eval_points", [
                ("t", "s", 100000, 10.0, 0.0, 100.0),
                ("t", "s", 200000, 20.0, 0.0, 100.0),
                ("t", "s", 6000000, 30.0, 0.0, 100.0),
            ]),
            "runs": frame("runs", [
                ("t", "s", "cloud", "running", 1, False, 8000000, 8, 0, "hfield", "", None, None, None),
            ]),
        }
        f = factors.run_factors("t", "s", tables, cfg())
        items = factors.run_risk_items(f, cfg())
        self.assertNotIn("stagnation", {i.factor for i in items})

    def test_nan_warn_and_severe(self):
        def items_with(nan_count: int):
            rows = [
                ("t", "s", f"sc{i}", "fail", False, 0.0, 0.1, 0.3, 0.0, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, i < nan_count)
                for i in range(4)
            ]
            f = factors.acceptance_factors(frame("reports", rows))
            return factors.run_risk_items(f, cfg())

        items1 = items_with(1)
        self.assertEqual(max(i.level for i in items1), "R2")
        self.assertIn("nan", {i.factor for i in items1 if i.level == "R2"})
        items4 = items_with(4)
        self.assertEqual(max(i.level for i in items4), "R3")

    def test_swap_mem_cpu_levels(self):
        items = factors.run_risk_items({"swap_percent_max": 60.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "swap")])
        items = factors.run_risk_items({"swap_percent_max": 90.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "swap")])
        items = factors.run_risk_items({"mem_percent_max": 97.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "mem")])
        items = factors.run_risk_items({"cpu_percent_max": 98.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "cpu")])

    def test_stall_minutes_levels(self):
        self.assertEqual(factors.run_risk_items({"stall_minutes": 20.0}, cfg()), [])
        items = factors.run_risk_items({"stall_minutes": 40.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "stall")])
        items = factors.run_risk_items({"stall_minutes": 65.0}, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R2", "stall")])

    def test_stall_skipped_when_completed(self):
        tables = {
            "snapshots": frame("snapshots", [
                (0.0, "t", "s", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
                (7200.0, "t", "s", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0),
            ]),
            "runs": frame("runs", [
                ("t", "s", "local", "completed", 1, True, 1000000, 4, 0, "hfield", "", None, None, None),
            ]),
        }
        f = factors.run_factors("t", "s", tables, cfg())
        self.assertEqual(f["stall_minutes"], 120.0)
        items = factors.run_risk_items(f, cfg())
        self.assertNotIn("stall", {i.factor for i in items})

    def test_idle_requires_uncompleted(self):
        snaps = frame("snapshots", [
            (0.0, "t", "s", 1000.0, 1.0, 10.0, 50.0, 0.5, 0.5, 0.5, 4096.0, 8192.0, 0.0, 1000.0, 0.0),
            (3600.0, "t", "s", 1000.0, 1.0, 10.0, 50.0, 0.5, 0.5, 0.5, 4096.0, 8192.0, 0.0, 1000.0, 0.0),
        ])
        tables_running = {"snapshots": snaps, "runs": frame("runs", [
            ("t", "s", "local", "running", 1, False, 1000000, 4, 0, "hfield", "", None, None, None)])}
        f = factors.run_factors("t", "s", tables_running, cfg())
        self.assertFalse(f["completed"])
        items = factors.run_risk_items(f, cfg())
        self.assertIn("idle", {i.factor for i in items})
        self.assertEqual(max(i.level for i in items), "R2")

        tables_done = {"snapshots": snaps, "runs": frame("runs", [
            ("t", "s", "local", "completed", 1, True, 1000000, 4, 0, "hfield", "", None, None, None)])}
        f2 = factors.run_factors("t", "s", tables_done, cfg())
        items2 = factors.run_risk_items(f2, cfg())
        self.assertNotIn("idle", {i.factor for i in items2})


class DecisionTest(unittest.TestCase):
    """决策矩阵：R0/R1/R2/R3 映射。"""

    def test_continue_when_r0(self):
        decision, reasons = factors.decide({}, [], cfg())
        self.assertEqual(decision, "continue")
        self.assertEqual(reasons, [])

    def test_watch_when_r1(self):
        risks = [factors.RiskItem("R1", "tb_points", "approx_kl", "x")]
        self.assertEqual(factors.decide({}, risks, cfg())[0], "watch")

    def test_tune_when_kl_r2(self):
        risks = [factors.RiskItem("R2", "tb_points", "approx_kl", "x")]
        self.assertEqual(factors.decide({}, risks, cfg())[0], "tune")

    def test_resize_when_swap_r2(self):
        risks = [factors.RiskItem("R2", "snapshots", "swap", "x")]
        self.assertEqual(factors.decide({}, risks, cfg())[0], "resize")

    def test_stop_when_drawdown_r2(self):
        risks = [factors.RiskItem("R2", "eval_points", "drawdown", "x")]
        self.assertEqual(factors.decide({"eval_drawdown": 0.35}, risks, cfg())[0], "stop")

    def test_stop_when_r3(self):
        risks = [factors.RiskItem("R3", "reports", "nan", "x")]
        self.assertEqual(factors.decide({}, risks, cfg())[0], "stop")

    def test_pipeline_drawdown_stop(self):
        tables = {"eval_points": frame("eval_points", [
            ("t", "s", 100000, 100.0, 0.0, 100.0),
            ("t", "s", 200000, 60.0, 0.0, 100.0),
        ])}
        f = factors.run_factors("t", "s", tables, cfg())
        risks = factors.run_risk_items(f, cfg())
        self.assertEqual(factors.decide(f, risks, cfg())[0], "stop")


class CostRiskTest(unittest.TestCase):
    """成本风控：预算占比与缓存率。"""

    def test_daily_cost_levels(self):
        def items_with(daily: float):
            rows = [("2026-08-17", "t1", 5, "m", 100, 100, 10, 0, 210, daily)]
            cost = factors.cost_factors(frame("costs", rows), "2026-08-17", cfg())
            return factors.cost_risk_items(cost, cfg())

        for daily, expected in ((2.0, []), (4.5, ["R1"]), (5.5, ["R2"]), (8.0, ["R3"])):
            items = items_with(daily)
            self.assertEqual([i.level for i in items], expected, msg=f"daily={daily}")

    def test_weekly_cost_watch(self):
        rows = [("2026-08-11", "t1", 5, "m", 100, 100, 10, 0, 210, 29.0)]
        cost = factors.cost_factors(frame("costs", rows), "2026-08-17", cfg())
        self.assertEqual(cost["daily_cost"], 0.0)
        self.assertEqual(cost["weekly_cost"], 29.0)
        items = factors.cost_risk_items(cost, cfg())
        self.assertEqual([(i.level, i.factor) for i in items], [("R1", "cost_weekly")])

    def test_cache_rate_watch(self):
        rows = [("2026-08-17", "t1", 5, "m", 100, 10, 10, 0, 120, 1.0)]
        cost = factors.cost_factors(frame("costs", rows), "2026-08-17", cfg())
        items = factors.cost_risk_items(cost, cfg())
        self.assertIn("cache_rate", {i.factor for i in items})
        self.assertEqual(max(i.level for i in items), "R1")

    def test_no_costs(self):
        cost = factors.cost_factors(None, "2026-08-17", cfg())
        self.assertFalse(cost["present"])
        self.assertEqual(factors.cost_risk_items(cost, cfg()), [])


class ComputeAllTest(unittest.TestCase):
    """compute_all 端到端：覆盖、排序、序列化、无数据分支。"""

    def test_end_to_end(self):
        tables = {
            "runs": frame("runs", [
                ("balance", "seed00", "cloud", "completed", 1, True, 8000000, 8, 0, "hfield", "", None, None, None)]),
            "eval_points": frame("eval_points", [("balance", "seed00", 100000, 100.0, 0.1, 500.0)]),
            "tb_points": frame("tb_points", [("balance", "seed00", 4096, 39.0, 900.0, 0.9, 0.08, 0.01, 0.5, 0.0003, 1)]),
            "reports": frame("reports", [
                ("balance", "seed00", "RL PPO", "pass", True, 1.0, 0.05, 0.3, 10.0, False, 2.0, 0.0, 0.0, 0.0, 100.0, 0.9, False)]),
            "snapshots": frame("snapshots", [
                (0.0, "balance", "seed00", 1000.0, 1.0, 50.0, 60.0, 1.0, 2.0, 3.0, 4096.0, 8192.0, 10.0, 1000.0, 1.0)]),
            "costs": frame("costs", [("2026-08-17", "t1", 5, "m", 100, 100, 10, 0, 210, 1.0)]),
        }
        result = factors.compute_all(cfg(), tables, today="2026-08-17")
        self.assertEqual(result.coverage["runs"], 1)
        self.assertEqual(len(result.runs), 1)
        run = result.runs[0]
        self.assertEqual((run.task, run.seed), ("balance", "seed00"))
        self.assertEqual(run.level, "R0")
        self.assertEqual(run.decision, "continue")
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertIn("balance", payload)
        self.assertIn("cost", payload)

    def test_no_data_run_continue(self):
        tables = {"runs": frame("runs", [
            ("balance_v1", "seed00", "", "", 0, False, None, None, None, "", "", None, None, None)])}
        result = factors.compute_all(cfg(), tables, today="2026-08-17")
        self.assertEqual(result.runs[0].decision, "continue")
        self.assertEqual(result.runs[0].reasons, ["暂无可用数据（未开始或已归档）"])

    def test_sort_high_risk_first(self):
        tables = {
            "runs": frame("runs", [
                ("a", "s00", "", "", 0, False, None, None, None, "", "", None, None, None),
                ("b", "s00", "", "", 0, False, None, None, None, "", "", None, None, None),
            ]),
            "tb_points": frame("tb_points", [("b", "s00", 4096, 1.0, 500.0, 0.9, 1.0, 0.2, 0.5, 0.0003, 1)]),
        }
        result = factors.compute_all(cfg(), tables, today="2026-08-17")
        self.assertEqual(result.runs[0].task, "b")
        self.assertEqual(result.runs[0].level, "R2")
        self.assertEqual(result.runs[0].decision, "tune")
        self.assertEqual(result.runs[-1].task, "a")


class BalanceFactorsIntegrationTest(unittest.TestCase):
    """balance/seed00 真实数据集成：负奖励占比/斜率/风险项（数据随仓库入库，稳定）。"""

    def test_balance_seed00_factors(self):
        import quant
        tables = quant.load_tables(cfg())
        f = factors.run_factors("balance", "seed00", tables, cfg())
        self.assertAlmostEqual(f["eval_neg_ratio"], 0.4625, places=3)
        self.assertEqual(f["eval_neg_ratio_recent"], 1.0)
        self.assertGreater(f["eval_std_recent"], 0.01)  # 0.0219，不触发塌缩
        self.assertLess(f["eval_slope_per_1e6"], 0.0)
        risks = factors.run_risk_items(f, cfg())
        neg = [i for i in risks if i.factor == "neg_ratio"]
        self.assertTrue(any(i.level == "R2" for i in neg), neg)
        decision, _ = factors.decide(f, risks, cfg())
        self.assertEqual(decision, "stop")


if __name__ == "__main__":
    unittest.main()