"""采集器单元测试：解析、TensorBoard、幂等、BOM、跨平台静态检查。"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

import collector
from schema import SCHEMA, validate_frame

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_source(root: Path) -> Path:
    src = root / "source"
    runs = src / "rl" / "runs"
    balance = runs / "balance" / "seed00"
    balance.mkdir(parents=True)
    (balance / "eval_log.csv").write_text(
        "timesteps,mean_reward,std_reward,mean_ep_len\n"
        "100000,1.0,0.0,100.0\n"
        "200000,2.0,0.1,200.0\n",
        encoding="utf-8",
    )
    (balance / ".completed").write_text("", encoding="utf-8")

    tb = balance / "tensorboard" / "run_1"
    tb.mkdir(parents=True)
    from tensorboard.summary import Writer

    w = Writer(str(tb))
    w.add_scalar("rollout/ep_rew_mean", 1.5, step=100000)
    w.add_scalar("rollout/ep_len_mean", 150.0, step=100000)
    w.add_scalar("train/std", 0.9, step=100000)
    w.add_scalar("train/value_loss", 10.0, step=100000)
    w.add_scalar("train/approx_kl", 0.01, step=100000)
    w.add_scalar("train/explained_variance", 0.3, step=100000)
    w.add_scalar("train/learning_rate", 0.0003, step=100000)
    w.add_scalar("train/n_updates", 10, step=100000)
    w.close()

    slope = runs / "traverse_slope" / "seed00"
    slope.mkdir(parents=True)
    (slope / "eval_log.csv").write_text(
        "timesteps,mean_reward,std_reward,mean_ep_len\n"
        "50000,-1.0,0.5,50.0\n",
        encoding="utf-8",
    )

    guard = runs / "_guard"
    guard.mkdir(parents=True)
    (guard / "state.json").write_text(
        json.dumps(
            {
                "runs": {
                    "balance/seed00": {
                        "status": "completed",
                        "owner": "cloud",
                        "attempts": 1,
                    },
                    "traverse_slope/seed00": {
                        "status": "external",
                        "owner": "local",
                        "attempts": 0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (guard / "local_balance_seed00.log").write_text(
        "从零训练 task=balance seed=0\n"
        "开始训练 task=balance seed=0 steps=8000000 envs=8\n",
        encoding="utf-8",
    )
    snap = [
        {
            "time": 1000.0,
            "resources": {
                "cpu_percent": 50.0,
                "mem_percent": 60.0,
                "load": [1.0, 2.0, 3.0],
                "mem_available_mb": 4096.0,
                "mem_total_mb": 8192.0,
                "swap_used_mb": 10.0,
                "swap_total_mb": 1000.0,
                "swap_percent": 1.0,
            },
            "seeds": [
                {"key": "balance/seed00", "timesteps": 100000.0, "reward": 1.0}
            ],
        },
        {
            "time": 1060.0,
            "resources": {
                "cpu_percent": 55.0,
                "mem_percent": 61.0,
                "load": [1.1, 2.1, 3.1],
                "mem_available_mb": 4000.0,
                "mem_total_mb": 8192.0,
                "swap_used_mb": 11.0,
                "swap_total_mb": 1000.0,
                "swap_percent": 1.1,
            },
            "seeds": [
                {"key": "balance/seed00", "timesteps": 200000.0, "reward": 2.0}
            ],
        },
    ]
    (guard / "snapshots.jsonl").write_text(
        "\n".join(json.dumps(s) for s in snap), encoding="utf-8"
    )

    reports = src / "reports" / "balance" / "seed00"
    reports.mkdir(parents=True)
    (reports / "metrics.csv").write_text(
        "label,task,max_dev,min_clear,dual_hold,recovered,settle_seconds,"
        "success,success_rate,distance,time_to_goal,falls,total_reward,"
        "mean_base_reward,nan\n"
        "RL PPO,balance,0.1,0.3,8.0,True,2.5,True,1.0,0.0,,0.0,100.0,0.9,False\n",
        encoding="utf-8",
    )
    (reports / "summary.json").write_text(
        json.dumps({"task": "balance", "seed": 0, "verdict": "pass"}),
        encoding="utf-8",
    )
    return src


def make_config(root: Path, src: Path) -> dict:
    return {
        "source_repo": str(src),
        "lianghua_db": str(root / "missing.db"),
        "output_dir": str(root / "out"),
        "raw_dir": str(root / "raw"),
        "tasks": [
            "balance",
            "full_chain",
            "traverse_slope",
            "traverse_flat_slope",
            "traverse_curve",
        ],
        "peak_hours": [10, 22],
        "pricing": {
            "peak": {"cached_input": 0.10, "uncached_input": 3.0, "output": 9.0},
            "offpeak": {"cached_input": 0.05, "uncached_input": 1.5, "output": 4.5},
        },
    }


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = make_source(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_eval_points(self):
        rows = collector.parse_eval_points(
            "balance", "seed00", self.src / "rl" / "runs" / "balance" / "seed00"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["timesteps"], 200000)
        self.assertAlmostEqual(rows[1]["mean_reward"], 2.0)

    def test_parse_train_config(self):
        cfg = collector.parse_train_config(
            self.src / "rl" / "runs" / "_guard", "balance", "seed00"
        )
        self.assertEqual(cfg["total_steps"], 8000000)
        self.assertEqual(cfg["envs"], 8)

    def test_parse_snapshots(self):
        rows = collector.parse_snapshots(
            self.src / "rl" / "runs" / "_guard" / "snapshots.jsonl"
        )
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["cpu_percent"], 50.0)
        self.assertAlmostEqual(rows[0]["load1"], 1.0)
        self.assertEqual(rows[0]["task"], "balance")

    def test_parse_reports(self):
        rows = collector.parse_reports(self.src / "reports")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["verdict"], "pass")
        self.assertTrue(rows[0]["success"])

    def test_parse_tb_points(self):
        rows = collector.parse_tb_points(
            "balance", "seed00", self.src / "rl" / "runs" / "balance" / "seed00"
        )
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["ep_rew_mean"], 1.5)
        self.assertAlmostEqual(rows[0]["value_loss"], 10.0)
        self.assertEqual(rows[0]["n_updates"], 10)

    def test_parse_costs_pricing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "usage.db"
            con = sqlite3.connect(db)
            con.execute(
                "CREATE TABLE responses (response_id TEXT PRIMARY KEY, thread_id TEXT,"
                " ts INTEGER, model TEXT, input_tokens INTEGER, cached_tokens INTEGER,"
                " output_tokens INTEGER, reasoning_tokens INTEGER, total_tokens INTEGER)"
            )
            # 2026-01-01 03:00 为闲时；价格：cached 0.05 / uncached 1.5 / output 4.5（元/百万）
            ts = int(datetime(2026, 1, 1, 3, 0).timestamp())
            con.execute(
                "INSERT INTO responses VALUES"
                f" ('r1','t1',{ts},'m1',1000000,500000,100000,20000,1600000)"
            )
            con.commit()
            con.close()
            pricing = {
                "peak": {"cached_input": 0.10, "uncached_input": 3.0, "output": 9.0},
                "offpeak": {"cached_input": 0.05, "uncached_input": 1.5, "output": 4.5},
            }
            rows = collector.parse_costs(db, [10, 22], pricing)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["cost_yuan"], 1.225, places=6)
        self.assertEqual(rows[0]["turns"], 1)
        self.assertEqual(rows[0]["total_tokens"], 1600000)


class CollectTest(unittest.TestCase):
    def test_collect_idempotent_and_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_source(root)
            cfg = make_config(root, src)
            first = collector.collect(cfg)
            second = collector.collect(cfg)
            self.assertEqual(first, second)
            self.assertEqual(first["runs"], 2)
            self.assertEqual(first["eval_points"], 3)
            self.assertEqual(first["tb_points"], 1)
            self.assertEqual(first["snapshots"], 2)
            self.assertEqual(first["reports"], 1)
            self.assertEqual(first["costs"], 0)
            self.assertEqual(first["labels"], first["runs"])

            out = Path(cfg["output_dir"])
            for table, n in first.items():
                path = out / f"{table}.csv"
                self.assertTrue(path.exists(), table)
                with open(path, "rb") as f:
                    self.assertEqual(f.read(3), b"\xef\xbb\xbf", f"{table} 缺 BOM")
                df = pd.read_csv(path)
                self.assertEqual(len(df), n, table)
                validate_frame(df, table)

            runs = pd.read_csv(out / "runs.csv")
            balance = runs[runs["task"] == "balance"].iloc[0]
            self.assertTrue(balance["completed"])
            self.assertEqual(balance["verdict"], "pass")
            self.assertEqual(balance["total_steps"], 8000000)
            self.assertEqual(balance["envs"], 8)
            self.assertAlmostEqual(balance["duration_seconds"], 60.0)

            labels = pd.read_csv(out / "labels.csv")
            bl = labels[labels["task"] == "balance"].iloc[0]
            self.assertTrue(bl["completed"])
            self.assertEqual(bl["verdict"], "pass")
            self.assertAlmostEqual(bl["duration_seconds"], 60.0)
            self.assertEqual(bl["label_source"], "auto")
            self.assertTrue(str(bl["label_updated_at"]))


def write_metrics(root: Path, task: str, seed: str, rows: list[tuple]) -> Path:
    """写一份验收 metrics.csv（与 make_source 列序一致）。"""
    reports = root / "reports" / task / seed
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "metrics.csv"
    header = (
        "label,task,max_dev,min_clear,dual_hold,recovered,settle_seconds,"
        "success,success_rate,distance,time_to_goal,falls,total_reward,"
        "mean_base_reward,nan\n"
    )
    path.write_text(header + "\n".join(",".join(str(v) for v in r) for r in rows),
                    encoding="utf-8")
    return path


class LabelChainTest(unittest.TestCase):
    """验收标签链路：summary 优先、metrics 兜底、报告-only run 入表、TB 过滤。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = make_source(self.root)
        self.cfg = make_config(self.root, self.src)
        self.tasks = self.cfg["tasks"] + ["traverse"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_verdict_priority_from_summary(self):
        rows = collector.build_runs(self.src, self.tasks)
        balance = next(r for r in rows if (r["task"], r["seed"]) == ("balance", "seed00"))
        # summary.json verdict=pass 优先；success_rate 缺失时兜底 metrics 均值 1.0
        self.assertEqual(balance["verdict"], "pass")
        self.assertAlmostEqual(balance["success_rate"], 1.0)
        self.assertTrue(balance["completed"])

    def test_verdict_fallback_without_summary(self):
        write_metrics(self.src, "traverse", "seed01", [
            ("RL PPO (flat)", "traverse", 0.08, 0.30, 0.0, False, 0.0, True, 1.0, 0.0, 0.0, 0.0, 100.0, 0.9, False),
            ("RL PPO (slope)", "traverse", 0.40, 0.02, 0.0, False, 0.0, False, 0.2, 0.0, 0.0, 3.0, 10.0, 0.1, False),
        ])
        rows = collector.build_runs(self.src, self.tasks)
        t1 = next(r for r in rows if (r["task"], r["seed"]) == ("traverse", "seed01"))
        self.assertEqual(t1["verdict"], "fail")          # 含 fail 场景 -> fail
        self.assertAlmostEqual(t1["success_rate"], 0.6)  # (1.0+0.2)/2
        self.assertTrue(t1["completed"])                 # 有验收报告
        # parse_reports 同样兜底
        reps = collector.parse_reports(self.src / "reports")
        trav = [r for r in reps if (r["task"], r["seed"]) == ("traverse", "seed01")]
        self.assertEqual(len(trav), 2)
        self.assertTrue(all(r["verdict"] == "fail" for r in trav))

    def test_report_only_run_included(self):
        write_metrics(self.src, "traverse", "seed02", [
            ("RL PPO (flat)", "traverse", 0.08, 0.30, 0.0, False, 0.0, True, 1.0, 0.0, 0.0, 0.0, 100.0, 0.9, False),
        ])
        # 故意不创建 rl/runs/traverse/seed02
        rows = collector.build_runs(self.src, self.tasks)
        keys = {(r["task"], r["seed"]) for r in rows}
        self.assertIn(("traverse", "seed02"), keys)
        t2 = next(r for r in rows if (r["task"], r["seed"]) == ("traverse", "seed02"))
        self.assertTrue(t2["completed"])
        self.assertEqual(t2["verdict"], "pass")
        self.assertAlmostEqual(t2["success_rate"], 1.0)
        self.assertEqual(t2["owner"], "")

    def test_report_only_run_duration_from_snapshots(self):
        # 报告-only run 也写入 runs.csv，且时长由快照推算（端到端 collect）
        guard = self.src / "rl" / "runs" / "_guard" / "snapshots.jsonl"
        extras = [
            {
                "time": 8000.0,
                "resources": {"cpu_percent": 50.0},
                "seeds": [{"key": "traverse/seed02", "timesteps": 100000.0, "reward": 1.0}],
            },
            {
                "time": 9000.0,
                "resources": {"cpu_percent": 50.0},
                "seeds": [{"key": "traverse/seed02", "timesteps": 200000.0, "reward": 2.0}],
            },
        ]
        lines = guard.read_text(encoding="utf-8").splitlines() + [json.dumps(e) for e in extras]
        guard.write_text("\n".join(lines), encoding="utf-8")
        write_metrics(self.src, "traverse", "seed02", [
            ("RL PPO (flat)", "traverse", 0.08, 0.30, 0.0, False, 0.0, True, 1.0, 0.0, 0.0, 0.0, 100.0, 0.9, False),
        ])
        cfg = dict(self.cfg)
        cfg["tasks"] = self.tasks
        collector.collect(cfg)
        runs = pd.read_csv(Path(cfg["output_dir"]) / "runs.csv")
        t2 = runs[(runs["task"] == "traverse") & (runs["seed"] == "seed02")].iloc[0]
        self.assertTrue(t2["completed"])
        self.assertEqual(t2["verdict"], "pass")
        self.assertAlmostEqual(t2["duration_seconds"], 1000.0, places=3)

    def test_tb_filters_implausible_approx_kl(self):
        tb2 = self.src / "rl" / "runs" / "balance" / "seed00" / "tensorboard" / "run_2"
        tb2.mkdir(parents=True)
        from tensorboard.summary import Writer

        w = Writer(str(tb2))
        for step, val in (
            (4096, 0.05),        # 正常
            (8192, 122376.375),  # 损坏值
            (12288, 0.0),        # 界外
            (16384, -0.5),       # 负值
            (20480, 1.5),        # 超界
        ):
            w.add_scalar("train/approx_kl", val, step=step)
        w.add_scalar("train/std", 0.9, step=4096)
        w.close()
        rows = collector.parse_tb_points(
            "balance", "seed00", self.src / "rl" / "runs" / "balance" / "seed00"
        )
        kl = {r["step"]: r["approx_kl"] for r in rows}
        self.assertAlmostEqual(kl[4096], 0.05, places=6)  # tensorboard 序列化有浮点误差
        self.assertIsNone(kl[8192])
        self.assertIsNone(kl[12288])
        self.assertIsNone(kl[16384])
        self.assertIsNone(kl[20480])
        self.assertAlmostEqual(
            next(r for r in rows if r["step"] == 4096)["std"], 0.9, places=6
        )

class LabelTableTest(unittest.TestCase):
    """权威标签表 labels.csv：自动生成、人工锁定保护、幂等。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = make_source(self.root)
        self.cfg = make_config(self.root, self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def _labels(self):
        return pd.read_csv(Path(self.cfg["output_dir"]) / "labels.csv")

    def test_collect_generates_labels(self):
        collector.collect(self.cfg)
        labels = self._labels()
        self.assertEqual(len(labels), 2)  # 与 runs 一一对应
        row = labels.iloc[0]
        self.assertEqual((row["task"], row["seed"]), ("balance", "seed00"))
        self.assertTrue(row["completed"])
        self.assertEqual(row["verdict"], "pass")
        self.assertAlmostEqual(row["success_rate"], 1.0)
        self.assertAlmostEqual(row["duration_seconds"], 60.0, places=3)
        self.assertEqual(row["label_source"], "auto")
        self.assertTrue(str(row["label_updated_at"]))
        # 未完成且无标签的 run 也占行，标签列留空
        row2 = labels.iloc[1]
        self.assertEqual((row2["task"], row2["seed"]), ("traverse_slope", "seed00"))
        self.assertFalse(row2["completed"])
        self.assertTrue(pd.isna(row2["verdict"]))
        self.assertEqual(row2["label_source"], "auto")

    def test_manual_row_survives_recollect(self):
        collector.collect(self.cfg)
        out = Path(self.cfg["output_dir"])
        labels = self._labels()
        labels.loc[0, "verdict"] = "fail"
        labels.loc[0, "label_source"] = "manual"
        labels.to_csv(out / "labels.csv", index=False, encoding="utf-8-sig")
        collector.collect(self.cfg)  # 第二次采集不应覆盖 manual 行
        labels2 = self._labels()
        self.assertEqual(len(labels2), 2)  # 与 runs 一一对应
        row = labels2[labels2["label_source"] == "manual"].iloc[0]
        self.assertEqual(row["verdict"], "fail")
        self.assertAlmostEqual(row["success_rate"], 1.0)
        self.assertTrue(row["completed"])  # manual 行完整保留
        self.assertEqual(len(labels2[labels2["label_source"] == "auto"]), 1)

    def test_labels_idempotent_counts(self):
        first = collector.collect(self.cfg)
        second = collector.collect(self.cfg)
        self.assertEqual(first["labels"], second["labels"])

    def test_labels_utf8_bom_and_schema(self):
        collector.collect(self.cfg)
        path = Path(self.cfg["output_dir"]) / "labels.csv"
        with open(path, "rb") as f:
            self.assertEqual(f.read(3), b"\xef\xbb\xbf")
        validate_frame(pd.read_csv(path), "labels")

class SchemaAndPortabilityTest(unittest.TestCase):
    def test_schema_validate(self):
        df = pd.DataFrame(columns=collector.table_columns("runs"))
        validate_frame(df, "runs")
        with self.assertRaises(ValueError):
            validate_frame(df.drop(columns=["task"]), "runs")
        with self.assertRaises(ValueError):
            validate_frame(df.assign(extra=[1]), "runs")

    def test_schema_covers_all_tables(self):
        self.assertEqual(
            set(SCHEMA),
            {
                "runs",
                "eval_points",
                "tb_points",
                "snapshots",
                "reports",
                "costs",
                "labels",
                "enriched_labels",
            },
        )
        for table, cols in SCHEMA.items():
            self.assertEqual(len({c for c, _t, _d in cols}), len(cols), table)
            self.assertIn("task" if table != "costs" else "date", {c for c, _t, _d in cols})

    def test_no_linux_specific_calls_in_python(self):
        forbidden = ("systemd", "cron", "notify-send")
        hits = []
        for name in ("collector.py", "summary.py", "schema.py"):
            py = PROJECT_ROOT / name
            text = py.read_text(encoding="utf-8")
            for word in forbidden:
                if word in text:
                    hits.append(f"{py.name}: {word}")
        self.assertEqual(hits, [])

    def test_windows_bat_exists(self):
        bat = PROJECT_ROOT / "run_windows.bat"
        self.assertTrue(bat.exists())
        self.assertIn("summary.py", bat.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
