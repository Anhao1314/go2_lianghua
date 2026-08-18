"""B 方案测试：特征数据集构建（modeling）与基线模型（baseline）。"""

import json
import pathlib
import tempfile
import unittest

import pandas as pd

import baseline
import modeling
from schema import SCHEMA

REPO = pathlib.Path(__file__).resolve().parents[1]


def _write_csv(root: pathlib.Path, table: str, rows: list[dict]) -> None:
    cols = [c for c, _t, _d in SCHEMA[table]]
    path = root / f"{table}.csv"
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False, encoding="utf-8-sig")


def _run_row(task: str, seed: str, completed: bool = True) -> dict:
    return {
        "task": task,
        "seed": seed,
        "owner": "local",
        "status": "completed" if completed else "running",
        "attempts": 1,
        "completed": completed,
        "total_steps": 8000000,
        "envs": 8,
        "curriculum_steps": 0,
        "terrain": "hfield",
        "init_from": "",
        "verdict": None,
        "success_rate": None,
        "duration_seconds": None,
    }


def _eval_row(task: str, seed: str, reward: float) -> dict:
    return {
        "task": task,
        "seed": seed,
        "timesteps": 100000,
        "mean_reward": reward,
        "std_reward": 0.1,
        "mean_ep_len": 100.0,
    }


def _tb_row(task: str, seed: str) -> dict:
    return {
        "task": task,
        "seed": seed,
        "step": 100000,
        "ep_rew_mean": 1.0,
        "ep_len_mean": 100.0,
        "std": 0.9,
        "value_loss": 10.0,
        "approx_kl": 0.01,
        "explained_variance": 0.3,
        "learning_rate": 0.0003,
        "n_updates": 10,
    }


def _snap_row(time: float, task: str, seed: str) -> dict:
    return {
        "time": time,
        "task": task,
        "seed": seed,
        "timesteps": 100000.0,
        "reward": 1.0,
        "cpu_percent": 50.0,
        "mem_percent": 60.0,
        "load1": 1.0,
        "load5": 1.0,
        "load15": 1.0,
        "mem_available_mb": 4096.0,
        "mem_total_mb": 8192.0,
        "swap_used_mb": 10.0,
        "swap_total_mb": 1000.0,
        "swap_percent": 1.0,
    }


def _report_row(task: str, seed: str) -> dict:
    return {
        "task": task,
        "seed": seed,
        "label": "RL PPO",
        "verdict": "pass",
        "success": True,
        "success_rate": 1.0,
        "max_dev": 0.1,
        "min_clear": 0.3,
        "dual_hold": 8.0,
        "recovered": True,
        "settle_seconds": 2.5,
        "distance": 0.0,
        "time_to_goal": None,
        "falls": 0.0,
        "total_reward": 100.0,
        "mean_base_reward": 0.9,
        "nan": False,
    }


class DatasetBuildTest(unittest.TestCase):
    """特征数据集：X（因子）与 y（labels）按 (task, seed) 合并。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.out = self.root / "out"
        self.out.mkdir(parents=True)
        cfg = json.loads((REPO / "config.json").read_text(encoding="utf-8"))
        cfg["output_dir"] = str(self.out)
        cfg["modeling_dir"] = str(self.root / "modeling")
        self.cfg = cfg
        _write_csv(self.out, "runs", [
            _run_row("balance", "seed00"),
            _run_row("traverse", "seed01"),
        ])
        _write_csv(self.out, "eval_points", [
            _eval_row("balance", "seed00", 1.0),
            _eval_row("traverse", "seed01", 0.5),
        ])
        _write_csv(self.out, "tb_points", [
            _tb_row("balance", "seed00"),
        ])
        _write_csv(self.out, "snapshots", [
            _snap_row(1000.0, "balance", "seed00"),
            _snap_row(1060.0, "balance", "seed00"),
        ])
        _write_csv(self.out, "reports", [
            _report_row("balance", "seed00"),
        ])
        _write_csv(self.out, "costs", [])

    def tearDown(self):
        self.tmp.cleanup()

    def _write_labels(self, old_format: bool = False) -> None:
        if old_format:
            rows = [
                {"task": "balance", "seed": "seed00", "completed": True, "verdict": "pass",
                 "success_rate": 1.0, "duration_seconds": 60.0, "total_steps": 8000000,
                 "final_reward": 1.0, "final_ep_len": 100.0},
                {"task": "traverse", "seed": "seed01", "completed": True, "verdict": "fail",
                 "success_rate": 0.5, "duration_seconds": 120.0, "total_steps": 8000000,
                 "final_reward": 0.5, "final_ep_len": 150.0},
            ]
        else:
            rows = [
                {"task": "balance", "seed": "seed00", "completed": True, "verdict": "pass",
                 "success_rate": 1.0, "duration_seconds": 60.0, "label_source": "auto",
                 "label_updated_at": "2026-08-17 10:00:00"},
                {"task": "traverse", "seed": "seed01", "completed": True, "verdict": "fail",
                 "success_rate": 0.5, "duration_seconds": 120.0, "label_source": "manual",
                 "label_updated_at": "2026-08-17 11:00:00"},
            ]
        pd.DataFrame(rows).to_csv(self.out / "labels.csv", index=False, encoding="utf-8-sig")

    def test_joins_features_and_labels(self):
        self._write_labels()
        df = modeling.build_dataset(self.cfg, "2026-08-17")
        self.assertEqual(len(df), 2)
        cols = list(df.columns)
        self.assertIn("task", cols)
        self.assertIn("seed", cols)
        self.assertIn("eval_drawdown", cols)  # X 因子
        self.assertNotIn("completed", cols[: len(df.columns) - len(modeling.Y_COLUMNS)])  # completed 不进 X
        row = df[df["task"] == "balance"].iloc[0]
        self.assertEqual(row["verdict"], "pass")
        self.assertAlmostEqual(row["duration_seconds"], 60.0)
        self.assertEqual(row["label_source"], "auto")
        self.assertTrue(bool(row["completed"]))
        row2 = df[df["task"] == "traverse"].iloc[0]
        self.assertEqual(row2["verdict"], "fail")
        self.assertEqual(row2["label_source"], "manual")

    def test_accepts_old_9col_labels(self):
        self._write_labels(old_format=True)
        df = modeling.build_dataset(self.cfg, "2026-08-17")
        self.assertEqual(len(df), 2)
        self.assertEqual(df["verdict"].tolist(), ["pass", "fail"])
        self.assertTrue(df["label_source"].isna().all())  # 旧版无此列 -> 补空

    def test_without_labels_keeps_runs(self):
        df = modeling.build_dataset(self.cfg, "2026-08-17")
        self.assertEqual(len(df), 2)
        self.assertTrue(df["verdict"].isna().all())
        self.assertIn("eval_drawdown", df.columns)


def _synthetic_df(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "task": f"t{i % 2}",
            "seed": f"seed{i}",
            "feat_a": float(i % 2),
            "feat_b": float(i),
            "feat_c": 1.0,
            "completed": True,
            "verdict": "pass" if i % 2 == 0 else "fail",
            "success_rate": 0.5 + 0.05 * (i % 5),
            "duration_seconds": 1000.0 + 100.0 * i,
            "label_source": "auto",
        })
    return pd.DataFrame(rows)


class BaselineTest(unittest.TestCase):
    """基线模型：门槛逻辑与 LOO 评估。"""

    def test_verdict_ok_with_both_classes(self):
        df = _synthetic_df(6)
        X = baseline.feature_matrix(df)
        res = baseline.verdict_baseline(df, X)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["n_pos"], 3)
        self.assertEqual(res["n_neg"], 3)
        self.assertIn("accuracy", res)
        self.assertIn("f1", res)
        self.assertIn("dummy_accuracy", res)

    def test_verdict_insufficient(self):
        df = _synthetic_df(1)
        res = baseline.verdict_baseline(df, baseline.feature_matrix(df))
        self.assertEqual(res["status"], "insufficient")
        self.assertEqual(res["n_pos"], 1)
        self.assertEqual(res["n_neg"], 0)

    def test_regression_ok(self):
        df = _synthetic_df(8)
        X = baseline.feature_matrix(df)
        res = baseline.regression_baseline(df, X, "duration_seconds")
        self.assertEqual(res["status"], "ok")
        self.assertIn("r2", res)
        self.assertIn("mae", res)
        self.assertIn("dummy_mae", res)
        self.assertGreaterEqual(res["dummy_mae"], 0.0)

    def test_regression_insufficient(self):
        df = _synthetic_df(3)
        res = baseline.regression_baseline(df, baseline.feature_matrix(df), "duration_seconds")
        self.assertEqual(res["status"], "insufficient")

    def test_run_baselines_full_pipeline(self):
        df = _synthetic_df(8)
        res = baseline.run_baselines(df)
        self.assertEqual(res["n_runs"], 8)
        self.assertGreaterEqual(res["n_features"], 2)
        self.assertEqual(res["verdict"]["status"], "ok")
        self.assertEqual(res["duration_seconds"]["status"], "ok")

    def test_duration_leak_features_excluded(self):
        # 特征全部为泄漏列（time_span_minutes/snapshot_count/swap_percent_max）
        rows = []
        for i in range(8):
            rows.append({
                "task": f"t{i % 2}", "seed": f"seed{i}",
                "time_span_minutes": float(i),
                "snapshot_count": float(i * 10),
                "swap_percent_max": float(i * 5),
                "completed": True,
                "verdict": "pass",
                "success_rate": 0.5,
                "duration_seconds": 1000.0 + 100.0 * i,
                "label_source": "auto",
            })
        df = pd.DataFrame(rows)
        res = baseline.regression_baseline(df, baseline.feature_matrix(df), "duration_seconds")
        # 排除后无可用特征 -> insufficient
        self.assertEqual(res["status"], "insufficient")
        self.assertEqual(res["reason"], "有效样本内无可用特征")

    def test_univariate_corrs_skips_constant(self):
        df = _synthetic_df(8)
        X = baseline.feature_matrix(df)
        corr = baseline.univariate_corrs(X, pd.to_numeric(df["duration_seconds"], errors="coerce"))
        self.assertNotIn("feat_c", set(corr["feature"]))  # 常量列被跳过


if __name__ == "__main__":
    unittest.main()
