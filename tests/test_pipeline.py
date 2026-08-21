"""run_pipeline 统一管线入口的集成测试：CLI 子进程端到端 + 各模块
run() 函数独立调用与管线产物一致性。"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from collector import load_config
from data_utils import load_all_tables, load_runs_merged
from factors import compute_all

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-08-19"

# 管线产物 8 个文件 + screening_summary 共 9 个
ARTIFACTS = [
    f"enriched_labels_{TODAY}.csv",
    f"dataset_{TODAY}.csv",
    f"screened_dataset_{TODAY}.csv",
    f"anomaly_archive_{TODAY}.csv",
    f"rule_backtest_{TODAY}.csv",
    f"rule_backtest_{TODAY}.md",
    f"quant_{TODAY}.md",
    f"quant_{TODAY}.json",
    f"screening_summary_{TODAY}.md",
]

_CFG = None
_TABLES = None
_CACHE = None
_E2E_DIR = None
_E2E_STDOUT = None


def _cfg() -> dict:
    global _CFG
    if _CFG is None:
        _CFG = load_config(PROJECT_ROOT / "config.json")
    return _CFG


def _tables() -> dict:
    global _TABLES
    if _TABLES is None:
        _TABLES = load_all_tables(_cfg())
    return _TABLES


def _cache() -> dict:
    global _CACHE
    if _CACHE is None:
        from run_pipeline import build_factors_cache
        _CACHE = build_factors_cache(_tables(), _cfg())
    return _CACHE


def _e2e_out() -> tuple[Path, str]:
    """运行一次完整的 run_pipeline 子进程（输出到临时目录），返回 (临时目录, stdout)。"""
    global _E2E_DIR, _E2E_STDOUT
    if _E2E_DIR is None:
        tmp = Path(tempfile.mkdtemp(prefix="pipe_e2e_"))
        env = dict(os.environ, PYTHONUTF8="1")
        proc = subprocess.run(
            [sys.executable, "run_pipeline.py", "--today", TODAY, "--out", str(tmp)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", env=env, timeout=900,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"run_pipeline 子进程失败 rc={proc.returncode}\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        _E2E_DIR = tmp
        _E2E_STDOUT = proc.stdout
    return _E2E_DIR, _E2E_STDOUT


def _read_norm(path: Path) -> str:
    """归一化读取文本：quant 的时间戳差异不参与跨进程产物对比。"""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", "<TS>", text)


class LoadAllTablesTest(unittest.TestCase):
    """load_all_tables 应返回 6 张因子表 + labels；runs 人工标注合并生效。"""

    def test_keys_and_shapes(self):
        tables = _tables()
        self.assertEqual(
            set(tables),
            {"runs", "eval_points", "tb_points", "snapshots", "reports", "costs", "labels"},
        )
        self.assertEqual(len(tables["runs"]), 36)
        self.assertEqual(len(tables["eval_points"]), 1688)
        self.assertEqual(len(tables["tb_points"]), 11852)
        self.assertEqual(len(tables["snapshots"]), 24872)
        self.assertEqual(len(tables["reports"]), 19)
        self.assertEqual(len(tables["costs"]), 4)
        self.assertEqual(len(tables["labels"]), 36)

    def test_runs_manual_labels_merged(self):
        runs = _tables()["runs"]
        manual = pd.read_csv(PROJECT_ROOT / "data" / "datasets" / "manual_labels.csv",
                             encoding="utf-8-sig")
        self.assertNotIn("label_source", runs.columns)
        self.assertNotIn("label_updated_at", runs.columns)
        m = manual[manual["verdict"].notna()]
        self.assertGreater(len(m), 0)
        for _, row in m.iterrows():
            hit = runs[(runs["task"] == row["task"]) & (runs["seed"] == row["seed"])]
            self.assertEqual(len(hit), 1, f"缺 run {row['task']}/{row['seed']}")
            self.assertEqual(hit.iloc[0]["verdict"], row["verdict"])
            self.assertEqual(hit.iloc[0]["success_rate"], row["success_rate"])

    def test_load_runs_merged_consistent(self):
        # 与 load_runs_merged 保持一致
        a = load_runs_merged(_cfg())
        b = _tables()["runs"]
        pd.testing.assert_frame_equal(a, b)


class FactorsCacheEquivalenceTest(unittest.TestCase):
    """factors_cache 传入与否，结果应完全一致。"""

    def test_build_enriched_equivalence(self):
        from label_enrichment import build_enriched
        a = build_enriched(_tables(), _cfg())
        b = build_enriched(_tables(), _cfg(), factors_cache=_cache())
        pd.testing.assert_frame_equal(a, b)

    def test_screen_all_equivalence(self):
        from data_screening import screen_all
        a = screen_all(_tables(), _cfg())
        b = screen_all(_tables(), _cfg(), factors_cache=_cache())
        pd.testing.assert_frame_equal(a, b)

    def test_compute_all_equivalence(self):
        a = compute_all(_cfg(), _tables(), today=TODAY)
        b = compute_all(_cfg(), _tables(), today=TODAY, factors_cache=_cache())
        self.assertEqual(a.coverage, b.coverage)
        self.assertEqual([r.to_dict() for r in a.runs], [r.to_dict() for r in b.runs])
        self.assertEqual(a.global_level, b.global_level)


class PipelineEndToEndTest(unittest.TestCase):
    """run_pipeline.py 端到端：产物齐全且内容正确。"""

    def test_artifacts_exist(self):
        out_dir, _ = _e2e_out()
        for name in ARTIFACTS:
            self.assertTrue((out_dir / name).exists(), f"缺少产物: {name}")

    def test_stdout_summary(self):
        _, stdout = _e2e_out()
        self.assertIn(f"完成 {TODAY}", stdout)
        self.assertIn("标签分布: pass=2 / fail=21 / unknown=13", stdout)

    def test_dataset_shape_and_screen_subset(self):
        out_dir, _ = _e2e_out()
        dataset = pd.read_csv(out_dir / f"dataset_{TODAY}.csv", encoding="utf-8-sig")
        screened = pd.read_csv(out_dir / f"screened_dataset_{TODAY}.csv", encoding="utf-8-sig")
        self.assertEqual(len(dataset), 36)
        self.assertIn("task", dataset.columns)
        self.assertIn("seed", dataset.columns)
        self.assertIn("verdict", dataset.columns)
        self.assertGreater(len(dataset.columns), 40)
        # screened 是 dataset 的 (task, seed) 子集
        ds_pairs = set(zip(dataset["task"], dataset["seed"]))
        sc_pairs = set(zip(screened["task"], screened["seed"]))
        self.assertTrue(sc_pairs.issubset(ds_pairs))
        self.assertLessEqual(len(screened), len(dataset))
        # 筛选结果应保留 data_quality 列
        self.assertIn("data_quality", screened.columns)
        self.assertIn("fail_reasons", screened.columns)

    def test_label_distribution_matches_tables(self):
        from backtest_rules import label_counts
        counts = label_counts(_tables())
        self.assertEqual(counts, {"pass": 2, "fail": 21, "unknown": 13})

    def test_quant_json_parseable(self):
        out_dir, _ = _e2e_out()
        payload = json.loads(
            (out_dir / f"quant_{TODAY}.json").read_text(encoding="utf-8")
        )
        self.assertIn("generated_at", payload)
        self.assertIn("runs", payload)
        self.assertIn("coverage", payload)
        self.assertIn("global_level", payload)


class PipelineSkipStepTest(unittest.TestCase):
    """--skip backtest 应跳过该步骤，且不影响其他产物。"""

    def test_skip_backtest(self):
        tmp = Path(tempfile.mkdtemp(prefix="pipe_skip_"))
        env = dict(os.environ, PYTHONUTF8="1")
        proc = subprocess.run(
            [sys.executable, "run_pipeline.py", "--today", TODAY,
             "--skip", "backtest", "--out", str(tmp)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", env=env, timeout=900,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:] if proc.stderr else "")
        self.assertFalse((tmp / f"rule_backtest_{TODAY}.csv").exists())
        self.assertFalse((tmp / f"rule_backtest_{TODAY}.md").exists())
        for name in ARTIFACTS:
            if name.startswith("rule_backtest_"):
                continue
            self.assertTrue((tmp / name).exists(), f"缺少产物: {name}")


class IndividualScriptsStillWorkTest(unittest.TestCase):
    """各模块 run() 独立调用（传入 tables/cache）应与管线产物一致。"""

    def test_run_functions_match_pipeline_outputs(self):
        e2e_dir, _ = _e2e_out()
        tmp = Path(tempfile.mkdtemp(prefix="pipe_ind_"))
        cfg, tables, cache = _cfg(), _tables(), _cache()

        import label_enrichment
        import modeling
        import data_screening
        import backtest_rules
        import quant

        enriched = label_enrichment.run(
            cfg, tables=tables, factors_cache=cache, today=TODAY, out=str(tmp))
        self.assertEqual(len(enriched), 36)

        dataset = modeling.run(
            cfg, today=TODAY, tables=tables, labels=tables.get("labels"),
            factors_cache=cache, out=str(tmp))
        self.assertEqual(len(dataset), 36)

        screened, archive, summary = data_screening.run(
            cfg, tables=tables, full_df=dataset, enriched_df=enriched,
            factors_cache=cache, today=TODAY, out=str(tmp))
        self.assertEqual(len(screened), 23)
        self.assertGreater(len(summary), 0)

        odds, stop_rows, backtest_md = backtest_rules.run(
            cfg, tables=tables, today=TODAY, out=str(tmp))
        self.assertGreater(len(odds), 0)

        md_text, json_obj = quant.run(
            cfg, tables=tables, factors_cache=cache, today=TODAY, out=str(tmp))
        self.assertIn("量化风控日报", md_text)
        self.assertIn("generated_at", json_obj)

        for name in ARTIFACTS:
            pa, pb = e2e_dir / name, tmp / name
            self.assertTrue(pa.exists(), f"缺少产物: {name}")
            self.assertTrue(pb.exists(), f"独立 run 缺产物: {name}")
            self.assertEqual(_read_norm(pa), _read_norm(pb),
                             f"独立 run 与管线产物不一致: {name}")


if __name__ == "__main__":
    unittest.main()
