"""数据筛选单元测试：4 条规则、分类优先级、清洗值使用、无未来信息。"""

import unittest
from pathlib import Path

import pandas as pd

import data_screening as ds
from collector import load_config
from schema import table_columns, validate_frame

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def frame(table: str, rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=table_columns(table))
    validate_frame(df, table)
    return df


def cfg() -> dict:
    return load_config(PROJECT_ROOT / "config.json")


def evals(rows: list) -> pd.DataFrame:
    return frame("eval_points", [
        ("t", "s", ts, rw, 0.1, 500.0) for ts, rw in rows
    ])


def tbs(kl_values: list[float] | None = None) -> pd.DataFrame:
    kl_values = kl_values if kl_values is not None else [0.02, 0.03]
    return frame("tb_points", [
        ("t", "s", 100000 * (i + 1), 50.0, 500.0, 0.5, 0.1, kl, 0.5, 0.0003, None)
        for i, kl in enumerate(kl_values)
    ])


def run_row(total=8000000, **extra):
    row = {"task": "t", "seed": "s", "completed": False, "total_steps": total}
    row.update(extra)
    return row


def clean_evals() -> pd.DataFrame:
    return evals([(i * 100000, 10.0 + i * 9.0) for i in range(10)])  # 10 点上升


class ScreeningRuleTest(unittest.TestCase):
    def test_rule1_insufficient(self):
        e = evals([(i * 100000, 10.0 + i * 9.0) for i in range(5)])  # 5 点
        passed, reasons = ds.screening_checks(
            e, tbs(), run_row(), cfg(), factors_f={"approx_kl_last": 0.05})
        self.assertFalse(passed["rule1"])
        self.assertTrue(passed["rule3"])
        self.assertTrue(passed["rule4"])
        self.assertEqual(ds.classify(passed), "insufficient")

    def test_rule3_uses_cleaned_kl(self):
        # 原始 tb_points 有 100（脏值），但 factors 清洗后为 0.05 -> rule3 PASS
        raw_tb = tbs([0.02, 100.0, 0.05])
        passed, _ = ds.screening_checks(
            clean_evals(), raw_tb, run_row(), cfg(),
            factors_f={"approx_kl_last": 0.05})
        self.assertTrue(passed["rule3"])
        self.assertEqual(ds.classify(passed), "good")

    def test_rule3_anomalous_priority(self):
        # 清洗后仍 >=1 -> rule3 fail -> anomalous（即使 rule1 也失败）
        e = evals([(i * 100000, 10.0 + i * 9.0) for i in range(5)])  # rule1 fail
        passed, _ = ds.screening_checks(
            e, tbs(), run_row(), cfg(), factors_f={"approx_kl_last": 100.0})
        self.assertFalse(passed["rule3"])
        self.assertFalse(passed["rule1"])
        self.assertEqual(ds.classify(passed), "anomalous")

    def test_rule1_rule3_both_fail_anomalous(self):
        passed, _ = ds.screening_checks(
            clean_evals(), tbs(), run_row(), cfg(),
            factors_f={"approx_kl_last": 5.0})
        self.assertFalse(passed["rule3"])
        self.assertEqual(ds.classify(passed), "anomalous")

    def test_clean_run_good(self):
        passed, reasons = ds.screening_checks(
            clean_evals(), tbs(), run_row(), cfg(),
            factors_f={"approx_kl_last": 0.05})
        for rule in ("rule1", "rule2", "rule3", "rule4"):
            self.assertTrue(passed[rule], rule)
        self.assertEqual(reasons, [])
        self.assertEqual(ds.classify(passed), "good")

    def test_eval_nan_rule3_fail(self):
        e = frame("eval_points", [
            ("t", "s", 100000, 50.0, 0.1, 500.0),
            ("t", "s", 200000, None, 0.1, 500.0),
            ("t", "s", 300000, 90.0, 0.1, 500.0),
        ] + [("t", "s", 400000 + i * 100000, 95.0, 0.1, 500.0) for i in range(7)])
        passed, _ = ds.screening_checks(
            e, tbs(), run_row(), cfg(), factors_f={"approx_kl_last": 0.05})
        self.assertFalse(passed["rule3"])
        self.assertEqual(ds.classify(passed), "anomalous")

    def test_flat_curve_rule4_fail(self):
        e = evals([(i * 100000, 50.0) for i in range(10)])  # 平线 std=0
        passed, _ = ds.screening_checks(
            e, tbs(), run_row(), cfg(), factors_f={"approx_kl_last": 0.05})
        self.assertFalse(passed["rule4"])
        self.assertEqual(ds.classify(passed), "anomalous")

    def test_no_future_info(self):
        # runs_row 只含 total_steps（无 verdict/reports 列）-> 结果不变
        row_min = {"total_steps": 8000000}
        passed_a, reasons_a = ds.screening_checks(
            clean_evals(), tbs(), row_min, cfg(),
            factors_f={"approx_kl_last": 0.05})
        passed_b, reasons_b = ds.screening_checks(
            clean_evals(), tbs(), run_row(verdict="fail"), cfg(),
            factors_f={"approx_kl_last": 0.05})
        self.assertEqual(passed_a, passed_b)
        self.assertEqual(reasons_a, reasons_b)
        self.assertEqual(ds.classify(passed_a), "good")


class ScreenRunTest(unittest.TestCase):
    def test_screen_run_end_to_end(self):
        tables = {
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, 8000000, 4,
                 None, None, None, None, None, None),
            ]),
            "eval_points": clean_evals(),
            "tb_points": tbs(),
        }
        out = ds.screen_run(tables, "t", "s", cfg())
        self.assertEqual(out["data_quality"], "good")
        self.assertEqual(out["eval_point_count"], 10)
        self.assertEqual(out["fail_reasons"], "")

    def test_screen_run_missing_eval(self):
        tables = {
            "runs": frame("runs", [
                ("t", "s", "local", "running", 0, False, 8000000, 4,
                 None, None, None, None, None, None),
            ]),
            "tb_points": tbs(),
        }
        out = ds.screen_run(tables, "t", "s", cfg())
        self.assertEqual(out["data_quality"], "insufficient")
        self.assertIn("rule1", out["fail_reasons"])


if __name__ == "__main__":
    unittest.main()