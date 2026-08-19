"""data_utils 合并函数单元测试：manual_labels.csv 人工标注层覆盖逻辑。"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data_utils import load_labels_merged, load_runs_merged

# runs.csv 风格：无 label_source/label_updated_at 列（runs schema）
BASE_RUNS = [
    {"task": "balance", "seed": "seed00", "verdict": "pass", "success_rate": 1.0},
    {"task": "traverse_curve_v2", "seed": "seed00", "verdict": "pass", "success_rate": 1.0},
    {"task": "traverse_v1", "seed": "seed00", "verdict": None, "success_rate": None},
]

# labels.csv 风格：含 label_source/label_updated_at（labels schema）
BASE_LABELS = [
    {"task": "balance", "seed": "seed00", "verdict": "pass", "success_rate": 1.0,
     "label_source": "auto", "label_updated_at": "2026-08-17 10:00:00"},
    {"task": "traverse_curve_v2", "seed": "seed00", "verdict": "pass", "success_rate": 1.0,
     "label_source": "auto", "label_updated_at": "2026-08-17 10:00:00"},
    {"task": "traverse_v1", "seed": "seed00", "verdict": None, "success_rate": None,
     "label_source": None, "label_updated_at": None},
]

MANUAL_ROWS = [
    {"task": "balance", "seed": "seed00", "verdict": "fail", "success_rate": 0.0,
     "label_source": "manual", "label_updated_at": "2026-08-18 09:00:00"},
    {"task": "traverse_curve_v2", "seed": "seed00", "verdict": "fail", "success_rate": 0.0,
     "label_source": "manual_cheating_exposed", "label_updated_at": "2026-08-18 09:00:00"},
]


def _write_csv(path: Path, rows: list) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _row(df: pd.DataFrame, task: str, seed: str) -> pd.Series:
    hit = df[(df["task"] == task) & (df["seed"] == seed)]
    return hit.iloc[0]


class LoadRunsMergedTest(unittest.TestCase):
    """load_runs_merged：runs.csv 人工字段被 manual_labels.csv 非空值覆盖。"""

    def test_override_by_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "runs.csv", BASE_RUNS)
            _write_csv(out / "manual_labels.csv", MANUAL_ROWS)
            df = load_runs_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        bal = _row(df, "balance", "seed00")
        self.assertEqual(bal["verdict"], "fail")
        self.assertEqual(bal["success_rate"], 0.0)
        cv2 = _row(df, "traverse_curve_v2", "seed00")
        self.assertEqual(cv2["verdict"], "fail")
        self.assertNotIn("verdict_manual", df.columns)

    def test_runs_merge_keeps_schema_columns(self):
        # runs schema 无 label_source/label_updated_at，合并后不得引入多余列
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "runs.csv", BASE_RUNS)
            _write_csv(out / "manual_labels.csv", MANUAL_ROWS)
            df = load_runs_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        self.assertEqual(list(df.columns), list(pd.DataFrame(BASE_RUNS).columns))
        self.assertNotIn("label_source", df.columns)
        self.assertNotIn("label_updated_at", df.columns)

    def test_no_manual_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "runs.csv", BASE_RUNS)
            df = load_runs_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        bal = _row(df, "balance", "seed00")
        self.assertEqual(bal["verdict"], "pass")
        self.assertEqual(bal["success_rate"], 1.0)

    def test_partial_keep_base_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "runs.csv", BASE_RUNS)
            # manual 只覆盖 balance；且 success_rate 为空应保留原值
            _write_csv(out / "manual_labels.csv", [
                {"task": "balance", "seed": "seed00", "verdict": "fail",
                 "success_rate": None, "label_source": None, "label_updated_at": None},
            ])
            df = load_runs_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        bal = _row(df, "balance", "seed00")
        self.assertEqual(bal["verdict"], "fail")
        self.assertEqual(bal["success_rate"], 1.0)
        tv1 = _row(df, "traverse_v1", "seed00")
        self.assertTrue(pd.isna(tv1["verdict"]))
        self.assertTrue(pd.isna(tv1["success_rate"]))

    def test_missing_runs_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = load_runs_merged({"output_dir": tmp})
        self.assertIsNone(df)


class LoadLabelsMergedTest(unittest.TestCase):
    """load_labels_merged：labels.csv 人工字段同样被 manual_labels.csv 覆盖。"""

    def test_override_by_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "labels.csv", BASE_LABELS)
            _write_csv(out / "manual_labels.csv", MANUAL_ROWS)
            df = load_labels_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        bal = _row(df, "balance", "seed00")
        self.assertEqual(bal["verdict"], "fail")
        self.assertEqual(bal["success_rate"], 0.0)
        self.assertEqual(bal["label_source"], "manual")
        self.assertEqual(bal["label_updated_at"], "2026-08-18 09:00:00")
        cv2 = _row(df, "traverse_curve_v2", "seed00")
        self.assertEqual(cv2["label_source"], "manual_cheating_exposed")

    def test_no_manual_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _write_csv(out / "labels.csv", BASE_LABELS)
            df = load_labels_merged({"output_dir": str(out)})
        self.assertIsNotNone(df)
        bal = _row(df, "balance", "seed00")
        self.assertEqual(bal["verdict"], "pass")
        self.assertEqual(bal["label_source"], "auto")

    def test_missing_labels_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = load_labels_merged({"output_dir": tmp})
        self.assertIsNone(df)