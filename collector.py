"""Go2w 训练数据采集器（v1：只采集，不建模）。

只在 Linux 数据源机器上执行 collect；生成的 CSV 带 UTF-8 BOM，
Windows 设备 git pull 后可直接用 Excel 打开或运行 summary.py。

用法：
  python collector.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from schema import KEY_COLUMNS, SCHEMA, table_columns, validate_frame

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"

START_LINE_RE = re.compile(
    r"开始训练 task=(\S+) seed=(\S+) steps=(\d+) envs=(\d+)"
)

# traverse_curve 课程学习：seed00 下 stage1~4 展平为 s1~s4 四个 run，
# timesteps 按阶段累加偏移，保证跨阶段曲线连续（每阶段 1M 步上限）。
CURRICULUM_TASK = "traverse_curve_curriculum"
CURRICULUM_STAGE_NAMES = (
    "stage1_straight",
    "stage2_big_curve",
    "stage3_mid_curve",
    "stage4_target",
)
CURRICULUM_SEEDS = ("s1", "s2", "s3", "s4")
CURRICULUM_SEED_OFFSETS = {"s1": 0, "s2": 1_000_000, "s3": 2_000_000, "s4": 3_000_000}

MULTI_SEGMENT_TASK = "traverse_curve_multi_segment"
MULTI_SEGMENT_STAGE_NAMES = ("stage1", "stage2", "stage3")
MULTI_SEGMENT_SEEDS = ("m1", "m2", "m3")
MULTI_SEGMENT_OFFSETS = {"m1": 0, "m2": 500_000, "m3": 1_000_000}

JUNCTION_TASK = "traverse_curve_junction"
JUNCTION_STAGE_NAMES = ("stage1", "stage2", "stage3")
JUNCTION_SEEDS = ("j1", "j2", "j3")
JUNCTION_OFFSETS = {"j1": 0, "j2": 300_000, "j3": 800_000}


def expand_path(raw: str) -> Path:
    """展开 ~ 与环境变量后返回绝对路径。"""
    return Path(os.path.expanduser(os.path.expandvars(raw))).resolve()


def load_config(path: str | Path | None = None) -> dict:
    local = PROJECT_ROOT / "config.local.json"
    cfg_path = Path(path) if path else (local if local.exists() else DEFAULT_CONFIG)
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data["_config_path"] = str(cfg_path)
    data["_project_root"] = str(PROJECT_ROOT)
    for key in ("source_repo", "lianghua_db"):
        raw = data.get(key)
        data[key] = expand_path(raw) if raw else None
    for key in ("output_dir", "raw_dir"):
        raw = data.get(key, "")
        data[key] = (PROJECT_ROOT / raw) if raw else PROJECT_ROOT / "data"
    return data


def _frame(rows: Iterable[dict], table: str) -> pd.DataFrame:
    df = pd.DataFrame(list(rows), columns=table_columns(table))
    validate_frame(df, table)
    return df


def write_frame(df: pd.DataFrame, table: str, out_dir: Path) -> None:
    """按 schema 列序写 CSV，UTF-8 BOM，Windows Excel 中文不乱码。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{table}.csv"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=out_dir, suffix=".tmp", delete=False,
                                         mode="w", encoding="utf-8-sig", newline="") as temp:
            temp_path = Path(temp.name)
            df[table_columns(table)].to_csv(temp, index=False)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


# ----------------------------------------------------------------------
# 数据源解析
# ----------------------------------------------------------------------


def read_state(source_repo: Path) -> dict:
    state_path = source_repo / "rl" / "runs" / "_guard" / "state.json"
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def iter_run_dirs(source_repo: Path, tasks: list[str]) -> list[tuple[str, str, Path]]:
    runs: list[tuple[str, str, Path]] = []
    for task in tasks:
        task_dir = source_repo / "rl" / "runs" / task
        if not task_dir.is_dir():
            continue
        if task == CURRICULUM_TASK:
            root = task_dir / "seed00"
            if not root.is_dir():
                continue
            for seed, name in zip(CURRICULUM_SEEDS, CURRICULUM_STAGE_NAMES):
                stage_dir = root / name
                if stage_dir.is_dir():
                    runs.append((task, seed, stage_dir))
            continue
        if task == MULTI_SEGMENT_TASK:
            root = task_dir / "seed00_v2"
            if not root.is_dir():
                root = task_dir / "seed00"
            if not root.is_dir():
                continue
            for seed, name in zip(MULTI_SEGMENT_SEEDS, MULTI_SEGMENT_STAGE_NAMES):
                stage_dir = root / name
                if stage_dir.is_dir():
                    runs.append((task, seed, stage_dir))
            continue
        if task == JUNCTION_TASK:
            root = task_dir / "seed00"
            if not root.is_dir():
                continue
            for seed, name in zip(JUNCTION_SEEDS, JUNCTION_STAGE_NAMES):
                stage_dir = root / name
                if stage_dir.is_dir():
                    runs.append((task, seed, stage_dir))
            continue
        for seed_dir in sorted(task_dir.glob("seed*")):
            if not seed_dir.is_dir():
                continue
            seed = seed_dir.name
            runs.append((task, seed, seed_dir))
    return runs


def parse_eval_points(
    task: str, seed: str, run_dir: Path, offset: int = 0
) -> list[dict]:
    path = run_dir / "eval_log.csv"
    if not path.exists():
        return []
    rows: list[dict] = []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    if len(lines) < 2:
        return []
    for ln in lines[1:]:
        if not ln:
            continue
        parts = ln.split(",")
        if len(parts) < 4:
            continue
        try:
            rows.append(
                {
                    "task": task,
                    "seed": seed,
                    "timesteps": int(float(parts[0])) + offset,
                    "mean_reward": float(parts[1]),
                    "std_reward": float(parts[2]),
                    "mean_ep_len": float(parts[3]),
                }
            )
        except ValueError:
            continue
    return rows


def _newest_tb_dir(run_dir: Path) -> Path | None:
    tb_root = run_dir / "tensorboard"
    if not tb_root.is_dir():
        return None
    candidates = [p for p in tb_root.iterdir() if p.is_dir()]
    if not candidates:
        return tb_root
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_tb_points(
    task: str, seed: str, run_dir: Path, offset: int = 0
) -> list[dict]:
    """读取最新 TensorBoard run 目录的标量（事件约每 rollout 16k 步刷新）。"""
    tb_dir = _newest_tb_dir(run_dir)
    if tb_dir is None:
        return []
    try:
        from tensorboard.backend.event_processing import event_accumulator

        acc = event_accumulator.EventAccumulator(
            str(tb_dir), size_guidance={"tensors": 0}
        )
        acc.Reload()
    except Exception:
        return []

    def scalar(tag: str) -> list[tuple[int, float]]:
        def _clean(values: list[tuple[int, float]]) -> list[tuple[int, float]]:
            # 丢弃非有限值（损坏/未初始化事件），避免污染因子计算
            return [(s, v) for s, v in values if math.isfinite(v)]

        try:
            events = acc.Scalars(tag)
            if events:
                return _clean([(e.step, float(e.value)) for e in events])
        except Exception:
            pass
        # 新版 SummaryWriter 可能把标量写成 tensor 事件
        try:
            from tensorboard.util import tensor_util

            return _clean(
                [
                    (e.step, float(tensor_util.make_ndarray(e.tensor_proto).reshape(-1)[0]))
                    for e in acc.Tensors(tag)
                ]
            )
        except Exception:
            return []

    tags = {
        "ep_rew_mean": "rollout/ep_rew_mean",
        "ep_len_mean": "rollout/ep_len_mean",
        "std": "train/std",
        "value_loss": "train/value_loss",
        "approx_kl": "train/approx_kl",
        "explained_variance": "train/explained_variance",
        "learning_rate": "train/learning_rate",
        "n_updates": "train/n_updates",
    }
    series = {name: scalar(tag) for name, tag in tags.items()}
    steps = sorted({s for series_ in series.values() for s, _v in series_})
    rows = []
    for step in steps:
        row = {"task": task, "seed": seed, "step": int(step) + offset}
        for name, values in series.items():
            value = next((v for s, v in values if s == step), None)
            if name == "approx_kl" and value is not None and not (0.0 < value <= 1.0):
                # PPO approx_kl 合理区间为 (0, 1]；0/负值/超界视为日志误写或损坏值
                value = None
            row[name] = value
        rows.append(row)
    return rows


def parse_snapshots(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = float(rec.get("time", 0.0))
        res = rec.get("resources") or {}
        load = res.get("load") or [None, None, None]
        for s in rec.get("seeds", []):
            key = str(s.get("key", ""))
            if "/" not in key:
                continue
            task, seed = key.split("/", 1)
            rows.append(
                {
                    "time": t,
                    "task": task,
                    "seed": seed,
                    "timesteps": float(s.get("timesteps", 0.0)),
                    "reward": (
                        float(s["reward"]) if s.get("reward") is not None else None
                    ),
                    "cpu_percent": res.get("cpu_percent"),
                    "mem_percent": res.get("mem_percent"),
                    "load1": load[0] if len(load) > 0 else None,
                    "load5": load[1] if len(load) > 1 else None,
                    "load15": load[2] if len(load) > 2 else None,
                    "mem_available_mb": res.get("mem_available_mb"),
                    "mem_total_mb": res.get("mem_total_mb"),
                    "swap_used_mb": res.get("swap_used_mb"),
                    "swap_total_mb": res.get("swap_total_mb"),
                    "swap_percent": res.get("swap_percent"),
                }
            )
    return rows


def parse_train_config(guard_dir: Path, task: str, seed: str) -> dict:
    """从训练日志尽力解析配置（total_steps/envs/课程/地形/init）。"""
    seed_num = seed.removeprefix("seed")
    names = [
        f"local_{task}_{seed}.log",
        f"cloud_{task}_{seed}.log",
        f"{task}_{seed}.log",
        f"{task}_seed{seed_num}.log",
        f"logs/{task}_{seed}.log",
    ]
    text = ""
    for name in names:
        p = guard_dir / name
        if p.exists():
            text += p.read_text(encoding="utf-8", errors="replace")
    cfg: dict[str, Any] = {}
    m = START_LINE_RE.search(text)
    if m:
        cfg["total_steps"] = int(m.group(3))
        cfg["envs"] = int(m.group(4))
    m = re.search(r"--curriculum-steps\s+(\d+)", text)
    if m:
        cfg["curriculum_steps"] = int(m.group(1))
    m = re.search(r"--terrain\s+(\S+)", text)
    if m:
        cfg["terrain"] = m.group(1)
    m = re.search(r"--init-from\s+(\S+)", text)
    if m:
        cfg["init_from"] = m.group(1)
    return cfg


def parse_run_config_json(run_dir: Path) -> dict:
    """优先读取训练目录内的 train_config.json（课程阶段等自定义目录可靠）。"""
    path = run_dir / "train_config.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, Any] = {}
    for key in ("total_steps", "envs", "curriculum_steps", "terrain", "init_from"):
        value = data.get(key)
        if value is not None:
            out[key] = value
    return out


def _curriculum_labels(reports_root: Path) -> dict:
    """课程学习统一验收标签：读取 seed00 汇总报告并应用到 s1~s4。"""
    labels: dict[str, Any] = {
        "verdict": None,
        "success_rate": None,
        "has_metrics": False,
    }
    summary = _read_summary(reports_root, CURRICULUM_TASK, "seed00")
    if summary:
        labels["verdict"] = summary.get("verdict")
        labels["success_rate"] = summary.get("success_rate")
    metrics_path = reports_root / CURRICULUM_TASK / "seed00" / "metrics.csv"
    if not metrics_path.exists():
        return labels
    labels["has_metrics"] = True
    try:
        df = pd.read_csv(metrics_path)
    except Exception:
        return labels
    if len(df) and "success" in df.columns:
        ok = all(bool(v) for v in df["success"].tolist())
        if not labels["verdict"]:
            labels["verdict"] = "pass" if ok else "fail"
    if labels["success_rate"] is None and "success_rate" in df.columns:
        vals = [
            float(v) for v in df["success_rate"].tolist()
            if v is not None and v == v
        ]
        if vals:
            labels["success_rate"] = sum(vals) / len(vals)
    return labels


def _multi_segment_labels(reports_root: Path) -> dict:
    """多段任务统一验收标签：读取 seed00_v2 汇总报告。"""
    labels: dict[str, Any] = {
        "verdict": None,
        "success_rate": None,
        "has_metrics": False,
    }
    seed = "seed00_v2"
    summary = _read_summary(reports_root, MULTI_SEGMENT_TASK, seed)
    if summary:
        labels["verdict"] = summary.get("verdict")
        labels["success_rate"] = summary.get("success_rate")
    metrics_path = reports_root / MULTI_SEGMENT_TASK / seed / "metrics.csv"
    if not metrics_path.exists():
        return labels
    labels["has_metrics"] = True
    try:
        df = pd.read_csv(metrics_path)
    except Exception:
        return labels
    if len(df) and "success" in df.columns:
        ok = all(bool(v) for v in df["success"].tolist())
        if not labels["verdict"]:
            labels["verdict"] = "pass" if ok else "fail"
    if labels["success_rate"] is None and "success_rate" in df.columns:
        vals = [
            float(v) for v in df["success_rate"].tolist()
            if v is not None and v == v
        ]
        if vals:
            labels["success_rate"] = sum(vals) / len(vals)
    return labels


def _report_run_keys(reports_root: Path) -> set[tuple[str, str]]:
    """扫描 reports/ 下全部 (task, seed) 验收键（以 metrics.csv 为准）。"""
    keys: set[tuple[str, str]] = set()
    for metrics in reports_root.glob("*/seed*/metrics.csv"):
        keys.add((metrics.parent.parent.name, metrics.parent.name))
    return keys


def _acceptance_labels(reports_root: Path, task: str, seed: str) -> dict:
    """验收标签：优先 summary.json；缺失时从 metrics.csv 兜底推导。

    verdict 兜底：场景 success 全为 True -> pass，否则 fail；
    success_rate 兜底：场景 success_rate 的均值（summary 优先）。
    返回 {"summary", "verdict", "success_rate", "has_metrics"}。
    """
    summary = _read_summary(reports_root, task, seed)
    labels: dict[str, Any] = {
        "summary": summary,
        "verdict": summary.get("verdict") if summary else None,
        "success_rate": summary.get("success_rate") if summary else None,
        "has_metrics": False,
    }
    metrics_path = reports_root / task / seed / "metrics.csv"
    if not metrics_path.exists():
        return labels
    labels["has_metrics"] = True
    try:
        df = pd.read_csv(metrics_path)
    except Exception:
        return labels
    if len(df) and "success" in df.columns:
        success = pd.to_numeric(df["success"], errors="coerce").fillna(0).astype(bool)
        if not labels["verdict"]:
            labels["verdict"] = "pass" if bool(success.all()) else "fail"
    if labels["success_rate"] is None and "success_rate" in df.columns:
        sr = pd.to_numeric(df["success_rate"], errors="coerce").dropna()
        if len(sr):
            labels["success_rate"] = float(sr.mean())
    return labels


def _junction_labels(reports_root: Path) -> dict:
    """Junction 岔路口统一验收标签：读取 seed00 汇总报告。"""
    labels: dict[str, Any] = {
        "verdict": None,
        "success_rate": None,
        "has_metrics": False,
    }
    summary = _read_summary(reports_root, JUNCTION_TASK, "seed00")
    if summary:
        labels["verdict"] = summary.get("verdict")
        labels["success_rate"] = summary.get("success_rate")
    metrics_path = reports_root / JUNCTION_TASK / "seed00" / "metrics.csv"
    if not metrics_path.exists():
        return labels
    labels["has_metrics"] = True
    try:
        df = pd.read_csv(metrics_path)
    except Exception:
        return labels
    if labels["success_rate"] is None and "success_rate" in df.columns:
        sr = pd.to_numeric(df["success_rate"], errors="coerce").dropna()
        if len(sr):
            labels["success_rate"] = float(sr.mean())
    return labels


def _run_keys(
    source_repo: Path, tasks: list[str], reports_root: Path
) -> dict[tuple[str, str], Path | None]:
    """run 集合 = rl/runs 目录 ∪ reports 验收报告（限定任务范围）。"""
    keys: dict[tuple[str, str], Path | None] = {}
    for task, seed, run_dir in iter_run_dirs(source_repo, tasks):
        keys[(task, seed)] = run_dir
    allowed = set(tasks)
    for task, seed in _report_run_keys(reports_root):
        # 课程/多段/岔路口用 s1~s4/m1~m3/j1~j3 展开行承载验收标签，汇总行不单独入 runs
        if task in allowed and task not in (
            CURRICULUM_TASK,
            MULTI_SEGMENT_TASK,
            JUNCTION_TASK,
        ):
            keys.setdefault((task, seed), None)  # 只有验收报告、无运行目录的 run 也入表
    return keys


def build_runs(source_repo: Path, tasks: list[str]) -> list[dict]:
    state = read_state(source_repo)
    runs_state = state.get("runs", {})
    guard_dir = source_repo / "rl" / "runs" / "_guard"
    reports_root = source_repo / "reports"
    keys = _run_keys(source_repo, tasks, reports_root)
    rows: list[dict] = []
    for (task, seed), run_dir in sorted(keys.items()):
        rec = runs_state.get(f"{task}/{seed}", {})
        cfg = parse_run_config_json(run_dir) if run_dir else {}
        cfg.update(parse_train_config(guard_dir, task, seed))
        labels = (
            _curriculum_labels(reports_root)
            if task == CURRICULUM_TASK
            else _multi_segment_labels(reports_root)
            if task == MULTI_SEGMENT_TASK
            else _junction_labels(reports_root)
            if task == JUNCTION_TASK
            else _acceptance_labels(reports_root, task, seed)
        )
        completed = bool((run_dir / ".completed").exists()) if run_dir else False
        if labels["has_metrics"]:
            completed = True  # 有验收报告即视为训练完成
        rows.append(
            {
                "task": task,
                "seed": seed,
                "owner": rec.get("owner", ""),
                "status": rec.get("status", ""),
                "attempts": rec.get("attempts"),
                "completed": completed,
                "total_steps": cfg.get("total_steps"),
                "envs": cfg.get("envs"),
                "curriculum_steps": cfg.get("curriculum_steps"),
                "terrain": cfg.get("terrain", ""),
                "init_from": cfg.get("init_from", ""),
                "verdict": labels["verdict"],
                "success_rate": labels["success_rate"],
                "duration_seconds": None,
            }
        )
    return rows


def _read_prev_labels(out_dir: Path) -> dict[tuple[str, str], dict]:
    """读取上一轮 labels.csv 作为人工修正基线（不存在/损坏则视为空）。"""
    path = out_dir / "labels.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    prev: dict[tuple[str, str], dict] = {}
    for _, r in df.iterrows():
        key = (str(r["task"]), str(r["seed"]))
        comp = r.get("completed")
        if pd.isna(comp):
            completed = False
        else:
            completed = str(comp).strip().lower() in ("true", "1", "1.0")
        prev[key] = {
            "completed": completed,
            "verdict": None if pd.isna(r["verdict"]) else r["verdict"],
            "success_rate": (
                None if pd.isna(r["success_rate"]) else float(r["success_rate"])
            ),
            "duration_seconds": (
                None if pd.isna(r["duration_seconds"]) else float(r["duration_seconds"])
            ),
            "label_source": (
                "auto" if pd.isna(r.get("label_source")) else str(r.get("label_source"))
            ),
            "label_updated_at": (
                "" if pd.isna(r.get("label_updated_at")) else str(r.get("label_updated_at"))
            ),
        }
    return prev


def build_labels(
    source_repo: Path,
    tasks: list[str],
    prev: dict[tuple[str, str], dict],
    duration_map: dict[tuple[str, str], float],
    now: str,
) -> list[dict]:
    """权威标签表：auto 行随采集刷新，manual 行人工锁定不被覆盖。

    与 runs.csv 一一对应，每个 (task, seed) 一行（含全部 manual 行）；
    v3 建模直接以本表为标签（y）来源。
    """
    reports_root = source_repo / "reports"
    keys = _run_keys(source_repo, tasks, reports_root)
    rows: list[dict] = []
    for (task, seed), run_dir in sorted(keys.items()):
        old = prev.get((task, seed))
        if old is not None and old["label_source"] == "manual":
            # 人工锁定：整行保留，采集不覆盖
            rows.append(
                {
                    "task": task,
                    "seed": seed,
                    "completed": old["completed"],
                    "verdict": old["verdict"],
                    "success_rate": old["success_rate"],
                    "duration_seconds": old["duration_seconds"],
                    "label_source": "manual",
                    "label_updated_at": old["label_updated_at"],
                }
            )
            continue
        labels = (
            _curriculum_labels(reports_root)
            if task == CURRICULUM_TASK
            else _multi_segment_labels(reports_root)
            if task == MULTI_SEGMENT_TASK
            else _junction_labels(reports_root)
            if task == JUNCTION_TASK
            else _acceptance_labels(reports_root, task, seed)
        )
        verdict = labels["verdict"]
        success_rate = labels["success_rate"]
        duration = duration_map.get((task, seed))
        completed = bool((run_dir / ".completed").exists()) if run_dir else False
        if labels["has_metrics"]:
            completed = True  # 有验收报告即视为训练完成
        rows.append(
            {
                "task": task,
                "seed": seed,
                "completed": completed,
                "verdict": verdict,
                "success_rate": success_rate,
                "duration_seconds": duration,
                "label_source": "auto",
                "label_updated_at": now,
            }
        )
    return rows


def _read_summary(reports_root: Path, task: str, seed: str) -> dict | None:
    path = reports_root / task / seed / "summary.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_reports(reports_root: Path) -> list[dict]:
    """扫描 reports/ 下全部任务的 metrics.csv + summary.json。"""
    rows: list[dict] = []
    for metrics in sorted(reports_root.glob("*/seed*/metrics.csv")):
        seed_dir = metrics.parent
        task = seed_dir.parent.name
        seed = seed_dir.name
        labels = _acceptance_labels(reports_root, task, seed)
        try:
            df = pd.read_csv(metrics)
        except Exception:
            continue
        for _, r in df.iterrows():
            rows.append(
                {
                    "task": task,
                    "seed": seed,
                    "label": str(r.get("label", "")),
                    "verdict": labels["verdict"],
                    "success": r.get("success"),
                    "success_rate": r.get("success_rate"),
                    "max_dev": r.get("max_dev"),
                    "min_clear": r.get("min_clear"),
                    "dual_hold": r.get("dual_hold"),
                    "recovered": r.get("recovered"),
                    "settle_seconds": r.get("settle_seconds"),
                    "distance": r.get("distance"),
                    "time_to_goal": r.get("time_to_goal"),
                    "falls": r.get("falls"),
                    "total_reward": r.get("total_reward"),
                    "mean_base_reward": r.get("mean_base_reward"),
                    "nan": r.get("nan"),
                }
            )
    return rows


def parse_costs(db_path: Path | None, peak_hours: list[int], pricing: dict) -> list[dict]:
    """从 lianghua usage.db（只读）聚合每日/每会话 token 与估算成本。"""
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if db_path is None or not db_path.exists():
        return []
    peak_start, peak_end = peak_hours[0], peak_hours[1]

    def hour_of(ts: int) -> int:
        return datetime.fromtimestamp(ts).hour

    def price_of(ts: int, kind: str) -> float:
        table = "peak" if peak_start <= hour_of(ts) < peak_end else "offpeak"
        return float(pricing[table][kind])

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT response_id, thread_id, ts, model, input_tokens, cached_tokens,"
            " output_tokens, reasoning_tokens, total_tokens FROM responses"
        ).fetchall()
    finally:
        con.close()

    groups: dict[tuple[str, str], dict] = {}
    for rid, thread_id, ts, model, inp, cached, out, reason, total in rows:
        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        key = (date, thread_id)
        g = groups.setdefault(
            key,
            {
                "turns": 0,
                "model": "",
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
                "cost_yuan": 0.0,
                "_last_ts": -1,
            },
        )
        g["turns"] += 1
        g["model"] = str(model)
        g["input_tokens"] += int(inp or 0)
        g["cached_tokens"] += int(cached or 0)
        g["output_tokens"] += int(out or 0)
        g["reasoning_tokens"] += int(reason or 0)
        g["total_tokens"] += int(total or 0)
        # 价格表单位：元/百万 token
        g["cost_yuan"] += (
            int(cached or 0) * price_of(ts, "cached_input")
            + max(0, int(inp or 0) - int(cached or 0)) * price_of(ts, "uncached_input")
            + int(out or 0) * price_of(ts, "output")
        ) / 1_000_000.0
        g["_last_ts"] = max(g["_last_ts"], int(ts))

    result = []
    for (date, thread_id), g in sorted(groups.items()):
        result.append(
            {
                "date": date,
                "thread_id": thread_id,
                "turns": g["turns"],
                "model": g["model"],
                "input_tokens": g["input_tokens"],
                "cached_tokens": g["cached_tokens"],
                "output_tokens": g["output_tokens"],
                "reasoning_tokens": g["reasoning_tokens"],
                "total_tokens": g["total_tokens"],
                "cost_yuan": round(g["cost_yuan"], 4),
            }
        )
    return result


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------


def _duration_map(snapshot_rows: list[dict]) -> dict[tuple[str, str], float]:
    by_key: dict[tuple[str, str], list[float]] = {}
    for r in snapshot_rows:
        by_key.setdefault((r["task"], r["seed"]), []).append(float(r["time"]))
    out: dict[tuple[str, str], float] = {}
    for key, times in by_key.items():
        if len(times) >= 2:
            out[key] = max(times) - min(times)
    return out


def collect(cfg: dict) -> dict[str, int]:
    source = cfg.get("source_repo")
    if isinstance(source, str):
        source = Path(source)
    if source is None or not source.is_dir():
        raise SystemExit(
            "collect 需要数据源机器（Linux）。当前配置 source_repo 不存在: "
            f"{source}；请在该机器上运行，或用 summary.py 查看已同步的数据集。"
        )
    tasks = cfg["tasks"] + cfg.get("archived_tasks", [])
    out_dir = Path(cfg["output_dir"])
    raw_dir = Path(cfg["raw_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    runs_rows = build_runs(source, tasks)
    eval_rows: list[dict] = []
    tb_rows: list[dict] = []
    for task, seed, run_dir in iter_run_dirs(source, tasks):
        offset = (
            CURRICULUM_SEED_OFFSETS.get(seed, 0)
            if task == CURRICULUM_TASK
            else MULTI_SEGMENT_OFFSETS.get(seed, 0)
            if task == MULTI_SEGMENT_TASK
            else JUNCTION_OFFSETS.get(seed, 0)
            if task == JUNCTION_TASK
            else 0
        )
        eval_rows.extend(parse_eval_points(task, seed, run_dir, offset=offset))
        tb_rows.extend(parse_tb_points(task, seed, run_dir, offset=offset))

    snap_path = source / "rl" / "runs" / "_guard" / "snapshots.jsonl"
    snap_rows = parse_snapshots(snap_path)
    if snap_path.exists():
        shutil.copy2(snap_path, raw_dir / "snapshots_latest.jsonl")
    dur = _duration_map(snap_rows)
    for row in runs_rows:
        row["duration_seconds"] = dur.get((row["task"], row["seed"]))

    # 权威标签表：auto 行自动刷新；prev 中的 manual 行保留人工修正
    prev_labels = _read_prev_labels(out_dir)
    labels_rows = build_labels(
        source, tasks, prev_labels, dur, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    reports_rows = parse_reports(source / "reports")
    costs_rows = parse_costs(cfg.get("lianghua_db"), cfg["peak_hours"], cfg["pricing"])

    tables: dict[str, pd.DataFrame] = {
        "runs": _frame(runs_rows, "runs"),
        "eval_points": _frame(eval_rows, "eval_points"),
        "tb_points": _frame(tb_rows, "tb_points"),
        "snapshots": _frame(snap_rows, "snapshots"),
        "reports": _frame(reports_rows, "reports"),
        "costs": _frame(costs_rows, "costs"),
        "labels": _frame(labels_rows, "labels"),
    }
    counts: dict[str, int] = {}
    for table, df in tables.items():
        keys = KEY_COLUMNS[table]
        df = df.drop_duplicates(subset=keys, keep="last").sort_values(keys)
        validate_frame(df, table)
        write_frame(df, table, out_dir)
        counts[table] = len(df)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 数据采集（只在 Linux 数据源机执行）")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    cfg = load_config(args.config)
    counts = collect(cfg)
    print("采集完成：")
    for table, n in counts.items():
        print(f"  {table:<14} {n} 行")


if __name__ == "__main__":
    main()
