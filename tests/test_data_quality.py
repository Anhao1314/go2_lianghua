# -*- coding: utf-8 -*-
"""data_quality_check 数据质量校验系统单元测试。

覆盖 6 大类校验规则（A 缺失值 / B 异常值 / C 时间戳连续性 / D 重复数据 /
E 标签一致性 / F 数据完整性）+ 评分 + 报告生成 + CLI 退出码。
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

import pandas as pd

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "data_quality_check.py"
_spec = importlib.util.spec_from_file_location("data_quality_check", _SCRIPT)
dqc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dqc)

TODAY = "2026-08-21"

# ---------------- 测试数据构造 ----------------

RUN_ROWS = [
    {"task": "balance", "seed": "seed00", "total_steps": 4_000_000,
     "verdict": "fail", "success_rate": 0.0, "completed": True},
]
LABEL_ROWS = [
    {"task": "balance", "seed": "seed00", "verdict": "fail", "success_rate": 0.0,
     "label_source": "formal_eval", "label_updated_at": "2026-08-19 13:30:00"},
]
MANUAL_ROWS = [
    {"task": "balance", "seed": "seed00", "verdict": "fail", "success_rate": 0.0,
     "label_source": "formal_eval", "label_updated_at": "2026-08-19 13:30:00"},
]
EVAL_ROWS = [
    {"task": "balance", "seed": "seed00", "timesteps": i * 400_000,
     "mean_reward": 50.0, "ep_len": 500.0}
    for i in range(10)
]
TB_ROWS = [
    {"task": "balance", "seed": "seed00", "step": i * 50_000, "value": 0.1}
    for i in range(80)
]
SNAP_ROWS = [
    {"task": "balance", "seed": "seed00", "time": i * 60, "value": 0.1}
    for i in range(10)
]
REPORT_ROWS = [
    {"task": "balance", "seed": "seed00", "label": "RL PPO", "verdict": "fail",
     "success": False, "success_rate": 0.0, "distance": 0.9, "falls": 1,
     "total_reward": -9.26},
]


def _write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")

_FILE_NAMES = {"manual": "manual_labels.csv"}


def _make_env(tmp: str, **tables) -> tuple[pathlib.Path, dict]:
    """构造临时数据环境，返回 (out_dir, cfg)。cfg.output_dir 指向 datasets 子目录。"""
    out = pathlib.Path(tmp)
    ds = out / "datasets"
    ds.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        if rows is not None:
            _write_csv(ds / _FILE_NAMES.get(name, f"{name}.csv"), rows)
    return out, {"output_dir": str(ds)}


def _types(issues: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in issues:
        out.setdefault(i["issue_type"], []).append(i)
    return out


def _clean_env(tmp: str) -> tuple[pathlib.Path, dict]:
    """无问题数据环境：1 个 fail run，10 eval 点，80 tb 点，10 snapshot，1 验收行。"""
    return _make_env(tmp, runs=RUN_ROWS, labels=LABEL_ROWS, manual=MANUAL_ROWS,
                     eval_points=EVAL_ROWS, tb_points=TB_ROWS, snapshots=SNAP_ROWS,
                     reports=REPORT_ROWS)


# ---------------- A. 缺失值 ----------------

class MissingValuesTest(unittest.TestCase):
    """A 类：缺失值检测。"""

    def test_insufficient_eval_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, labels=LABEL_ROWS, manual=MANUAL_ROWS,
                                 eval_points=EVAL_ROWS[:5])
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("insufficient_eval_points", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")
        self.assertEqual((hits[0]["task"], hits[0]["seed"]), ("balance", "seed00"))

    def test_missing_total_steps(self):
        runs = [dict(RUN_ROWS[0], total_steps=None)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=runs)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("missing_total_steps", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")

    def test_missing_report(self):
        reports = [dict(REPORT_ROWS[0], task="traverse")]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, reports=reports)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("missing_report", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "critical")


# ---------------- B. 异常值 ----------------

class OutliersTest(unittest.TestCase):
    """B 类：异常值检测。"""

    def test_reward_outlier(self):
        evals = [dict(EVAL_ROWS[0], mean_reward=1000.0)] + EVAL_ROWS[1:]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("reward_outlier", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")
        self.assertIn("1000", hits[0]["description"])

    def test_success_rate_outlier(self):
        runs = [dict(RUN_ROWS[0], success_rate=1.5)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=runs)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("success_rate_outlier", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")


# ---------------- C. 时间戳连续性 ----------------

class TimestampsTest(unittest.TestCase):
    """C 类：时间戳连续性。"""

    def _evals(self, steps):
        return [{"task": "balance", "seed": "seed00", "timesteps": s,
                 "mean_reward": 50.0, "ep_len": 500.0} for s in steps]

    def test_timesteps_not_monotonic(self):
        evals = self._evals([100_000, 200_000, 150_000, 300_000])
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("timesteps_not_monotonic", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "critical")

    def test_large_gap(self):
        evals = self._evals([100_000, 700_000])
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("large_gap", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")

    def test_missing_early_eval(self):
        evals = self._evals([300_000, 700_000, 1_100_000, 1_500_000])
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("missing_early_eval", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "info")

    def test_incomplete_training(self):
        runs = [dict(RUN_ROWS[0], total_steps=8_000_000)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=runs, eval_points=EVAL_ROWS)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("incomplete_training", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")


# ---------------- D. 重复数据 ----------------

class DuplicatesTest(unittest.TestCase):
    """D 类：重复数据检测。"""

    def test_duplicate_eval_points(self):
        evals = EVAL_ROWS + [dict(EVAL_ROWS[3])]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("duplicate_eval_points", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "critical")


# ---------------- E. 标签一致性 ----------------

class LabelConsistencyTest(unittest.TestCase):
    """E 类：标签一致性（读原始文件对比，人工层不生效）。"""

    def test_verdict_mismatch(self):
        labels = [dict(LABEL_ROWS[0], verdict="pass", success_rate=1.0)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, labels=labels,
                                 reports=REPORT_ROWS)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("verdict_mismatch", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "critical")
        self.assertIn("runs", hits[0]["description"])

    def test_merge_layer_mismatch(self):
        manual = MANUAL_ROWS + [
            {"task": "ghost", "seed": "seed00", "verdict": "fail", "success_rate": 0.0,
             "label_source": "manual", "label_updated_at": "2026-08-21 10:00:00"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, manual=manual)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("merge_layer_mismatch", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["task"], hits[0]["seed"]), ("ghost", "seed00"))
        self.assertEqual(hits[0]["severity"], "critical")

    def test_completed_verdict_mismatch(self):
        runs = [dict(RUN_ROWS[0], verdict=None, success_rate=None)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=runs)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("completed_verdict_mismatch", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")


# ---------------- F. 数据完整性 ----------------

class IntegrityTest(unittest.TestCase):
    """F 类：跨表关联。"""

    def test_orphan_data(self):
        ghost = [{"task": "ghost", "seed": "seed00", "timesteps": 100_000,
                  "mean_reward": 1.0, "ep_len": 100.0}]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=EVAL_ROWS + ghost)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("orphan_data", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["task"], hits[0]["seed"]), ("ghost", "seed00"))
        self.assertEqual(hits[0]["severity"], "critical")

    def test_total_steps_mismatch(self):
        runs = [dict(RUN_ROWS[0], total_steps=8_000_000)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=runs, eval_points=EVAL_ROWS)
            issues = dqc.run_check(cfg, TODAY, out)
        hits = _types(issues).get("total_steps_mismatch", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")


# ---------------- 评分 / 报告 / CLI ----------------

class SeverityAndGradeTest(unittest.TestCase):
    """严重程度分类与总体评分。"""

    def test_severity_classification(self):
        evals = [
            {"task": "balance", "seed": "seed00", "timesteps": 300_000,
             "mean_reward": 1000.0, "ep_len": 500.0},
            {"task": "balance", "seed": "seed00", "timesteps": 700_000,
             "mean_reward": 50.0, "ep_len": 500.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, eval_points=evals)
            issues = dqc.run_check(cfg, TODAY, out)
        sev = {i["issue_type"]: i["severity"] for i in issues}
        self.assertEqual(sev.get("reward_outlier"), "warning")
        self.assertEqual(sev.get("missing_early_eval"), "info")
        self.assertEqual(sev.get("insufficient_eval_points"), "warning")

    def test_grade_classification(self):
        self.assertEqual(dqc._grade([]), "A")
        self.assertEqual(dqc._grade([{"severity": "warning"}] * 2), "A")
        self.assertEqual(dqc._grade([{"severity": "warning"}] * 4), "B")
        self.assertEqual(dqc._grade([{"severity": "warning"}] * 8), "C")
        self.assertEqual(dqc._grade([{"severity": "critical"}] * 1), "C")
        self.assertEqual(dqc._grade([{"severity": "warning"}] * 11), "D")
        self.assertEqual(dqc._grade([{"severity": "critical"}] * 3), "D")

    def test_no_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _clean_env(tmp)
            issues = dqc.run_check(cfg, TODAY, out)
        self.assertEqual(issues, [])


class ReportGenerationTest(unittest.TestCase):
    """MD/CSV/JSON 报告生成。"""

    def _write_config(self, ds: pathlib.Path) -> pathlib.Path:
        cfg_path = ds.parent / "config_test.json"
        cfg_path.write_text(json.dumps({"output_dir": str(ds)}), encoding="utf-8")
        return cfg_path

    def test_report_generation(self):
        """MD/CSV/JSON 报告生成。"""
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _clean_env(tmp)
            evals = [dict(EVAL_ROWS[0], mean_reward=999.0)] + EVAL_ROWS[1:]
            _write_csv(out / "datasets" / "eval_points.csv", evals)
            labels = [dict(LABEL_ROWS[0], verdict="pass", success_rate=1.0)]
            _write_csv(out / "datasets" / "labels.csv", labels)
            cfg_path = self._write_config(out / "datasets")
            rc = dqc.main(["--today", TODAY, "--out", str(out),
                           "--config", str(cfg_path), "--json"])
            md = (out / f"quality_report_{TODAY}.md").read_text(encoding="utf-8")
            csv_path = out / f"quality_issues_{TODAY}.csv"
            json_path = out / f"quality_report_{TODAY}.json"
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            cols = list(df.columns)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(rc, 1)
        self.assertIn(f"# 数据质量报告 {TODAY}", md)
        self.assertIn("reward_outlier", md)
        self.assertIn("## 问题统计", md)
        self.assertEqual(cols,
                         ["issue_id", "category", "severity", "task", "seed",
                          "issue_type", "description", "suggestion"])
        self.assertEqual(payload["today"], TODAY)
        self.assertTrue(any(i["issue_type"] == "reward_outlier" for i in payload["issues"]))


class CliExitCodeTest(unittest.TestCase):
    """CLI 退出码：0=无 critical，1=有 critical，2=运行时错误。"""

    def _cfg(self, out: pathlib.Path, ds: pathlib.Path) -> pathlib.Path:
        cfg_path = out / "config_test.json"
        cfg_path.write_text(json.dumps({"output_dir": str(ds)}), encoding="utf-8")
        return cfg_path

    def test_exit_code_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _clean_env(tmp)
            cfg_path = self._cfg(out, out / "datasets")
            rc = dqc.main(["--today", TODAY, "--out", str(out), "--config", str(cfg_path)])
        self.assertEqual(rc, 0)

    def test_exit_code_critical(self):
        labels = [dict(LABEL_ROWS[0], verdict="pass", success_rate=1.0)]
        with tempfile.TemporaryDirectory() as tmp:
            out, cfg = _make_env(tmp, runs=RUN_ROWS, labels=labels, reports=REPORT_ROWS)
            cfg_path = self._cfg(out, out / "datasets")
            rc = dqc.main(["--today", TODAY, "--out", str(out), "--config", str(cfg_path)])
        self.assertEqual(rc, 1)

    def test_exit_code_missing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = dqc.main(["--today", TODAY, "--out", tmp,
                           "--config", str(pathlib.Path(tmp) / "nope.json")])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

