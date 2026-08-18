"""标签富化单元测试：塌缩检测、最佳步、早停合理性、集成期望。"""

import unittest
from pathlib import Path

import pandas as pd

import label_enrichment as le
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
    """rows: (timesteps, mean_reward)"""
    return frame("eval_points", [
        ("t", "s", ts, rw, 0.1, 500.0) for ts, rw in rows
    ])


def run_row(verdict=None, total=8000000, completed=True):
    return {
        "task": "t", "seed": "s", "completed": completed, "total_steps": total,
        "verdict": verdict, "success_rate": None, "duration_seconds": 6000.0,
    }


class CollapseTest(unittest.TestCase):
    def test_rise_then_crash(self):
        e = evals([
            (100000, 50.0), (500000, 90.0), (1000000, 99.0),
            (1500000, 99.5), (2000000, 99.8),   # 峰值
            (2500000, 30.0), (3000000, -40.0),  # 塌缩 < 0.5*peak
            (3500000, -50.0), (4000000, -20.0),
        ])
        out = le.enrich_one(e, None, run_row(), cfg())
        self.assertTrue(out["training_collapsed"])
        self.assertEqual(out["collapse_step"], 2500000.0)
        self.assertEqual(out["collapse_ratio"], 0.625)
        self.assertEqual(out["best_step"], 2000000.0)
        self.assertAlmostEqual(out["best_step_ratio"], 0.5, places=4)

    def test_monotonic_rise(self):
        e = evals([
            (100000, 10.0), (500000, 30.0), (1000000, 60.0),
            (1500000, 80.0), (2000000, 95.0), (2500000, 99.0),
            (3000000, 99.5), (3500000, 99.8), (4000000, 99.9),
        ])
        out = le.enrich_one(e, None, run_row(), cfg())
        self.assertFalse(out["training_collapsed"])
        self.assertIsNone(out["collapse_step"])
        self.assertIsNone(out["collapse_ratio"])

    def test_vshape_recovery(self):
        # 下跌后恢复到 0.8*peak 以上 -> 不算塌缩
        e = evals([
            (100000, 50.0), (500000, 90.0), (1000000, 99.0),
            (1500000, 99.8), (2000000, 99.9),   # 峰值
            (2500000, 30.0), (3000000, 40.0),   # 短暂下跌
            (3500000, 95.0), (4000000, 99.0),   # 恢复 > 0.8*peak
        ])
        out = le.enrich_one(e, None, run_row(), cfg())
        self.assertFalse(out["training_collapsed"])

    def test_window_fallback_no_eval(self):
        # timesteps 全缺失 -> 窗口回退 total_steps；无有效步进则 ratio=None（不崩溃）
        e = frame("eval_points", [
            ("t", "s", None, 50.0, 0.1, 500.0),
            ("t", "s", None, 90.0, 0.1, 500.0),
        ])
        out = le.enrich_one(e, None, run_row(total=1000000), cfg())
        self.assertIsNone(out["best_step_ratio"])
        self.assertIsNone(out["collapse_step"])
        self.assertFalse(out["training_collapsed"])


class StopJustifiedTest(unittest.TestCase):
    def _collapsed_curve(self, peak_pos, collapse_pos):
        """构造峰值在 peak_pos、塌缩在 collapse_pos 的曲线（占窗口比例）。"""
        n = 10
        rows = []
        for i in range(n):
            frac = (i + 1) / n
            if frac <= peak_pos:
                rw = 80.0 + frac / peak_pos * 19.0  # 升到 99
            elif frac <= collapse_pos:
                rw = 99.0 - (frac - peak_pos) / (collapse_pos - peak_pos) * 20.0
            else:
                rw = -40.0
            rows.append((int(frac * 8000000), rw))
        return evals(rows)

    def test_fail_verdict(self):
        out = le.enrich_one(self._collapsed_curve(0.3, 0.5),
                            None, run_row(verdict="fail"), cfg())
        self.assertTrue(out["stop_justified"])

    def test_pass_collapsed_early_enough(self):
        # 峰值 0.3、塌缩 0.5：早停窗口内 -> True
        out = le.enrich_one(self._collapsed_curve(0.3, 0.5),
                            None, run_row(verdict="pass"), cfg())
        self.assertTrue(out["training_collapsed"])
        self.assertLess(out["best_step_ratio"], 0.7)
        self.assertLess(out["collapse_ratio"], 0.8)
        self.assertTrue(out["stop_justified"])

    def test_pass_collapsed_too_late(self):
        # 边界：塌缩段跨度恰好 20%（collapse_ratio=0.8）-> collapsed=True
        # 但 stop_justified 要求 collapse_ratio<0.8 严格成立 -> False（太晚）
        e = evals([
            (100000, 50.0), (200000, 90.0), (300000, 99.0),  # 峰值 0.3
            (400000, 30.0),    # 首个 < 0.5*peak（0.4 处）
            (500000, -40.0),   # 末尾：跨度恰好 20%
        ])
        out = le.enrich_one(e, None, run_row(verdict="pass"), cfg())
        self.assertTrue(out["training_collapsed"])
        self.assertAlmostEqual(out["collapse_ratio"], 0.8, places=4)
        self.assertFalse(out["stop_justified"])

    def test_pass_no_collapse(self):
        e = evals([
            (100000, 10.0), (500000, 30.0), (1000000, 60.0),
            (1500000, 80.0), (2000000, 95.0), (2500000, 99.0),
            (3000000, 99.5), (3500000, 99.8), (4000000, 99.9),
        ])
        out = le.enrich_one(e, None, run_row(verdict="pass"), cfg())
        self.assertFalse(out["training_collapsed"])
        self.assertFalse(out["stop_justified"])


class BalanceIntegrationTest(unittest.TestCase):
    def test_balance_seed00(self):
        # balance/seed00 真实曲线要点：峰值 1.9M（99.98），2.1M 起 <0.5*peak，
        # 之后从未恢复到 0.8*peak；eval 观测窗口到 4M（total_steps=8M）
        e = evals([
            (500000, 50.0), (1000000, 90.0), (1500000, 95.0),
            (1900000, 99.9821), (2000000, 99.97),
            (2050000, 70.7014), (2100000, 10.08),   # 首个 < 0.5*peak
            (2150000, -23.8015), (2200000, -80.4551),
            (3000000, -40.0), (4000000, -18.8337),
        ])
        row = run_row(verdict="pass", total=8000000)
        out = le.enrich_one(e, None, row, cfg(),
                            factors_f={"approx_kl_last": 0.0212})
        self.assertTrue(out["training_collapsed"])
        self.assertEqual(out["best_step"], 1900000.0)
        # 分母 = 观测窗口 4M（规格集成期望 0.475）
        self.assertAlmostEqual(out["best_step_ratio"], 0.475, places=3)
        # 修正 4：collapse_step = 首个 <0.5*peak 的点（2.1M；规格中 ≈2.15M 为近似）
        self.assertEqual(out["collapse_step"], 2100000.0)
        self.assertAlmostEqual(out["collapse_ratio"], 0.525, places=3)
        self.assertTrue(out["stop_justified"])
        self.assertEqual(out["data_quality"], "good")
        self.assertEqual(out["eval_point_count"], 11)


if __name__ == "__main__":
    unittest.main()