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
