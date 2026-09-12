"""告警标注：把 realtime_monitor 的 R2/R3 告警与训练最终状态对照，
生成 “是否真的崩溃” 标注数据，供量化建模使用。

用法：
  python annotate_alerts.py --config config.json
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import time
from datetime import datetime

import pandas as pd

from collector import PROJECT_ROOT, expand_path, load_config
from data_utils import load_runs_merged

ANNOTATION_COLUMNS = [
    "timestamp",
    "task",
    "seed",
    "level",
    "triggered_rules",
    "eval_reward",
    "ep_len",
    "confirmed_crash",
    "note",
    "annotated_at",
]


def classify_run(run_dir: pathlib.Path, now: float | None = None,
                 stale_hours: float = 2.0) -> tuple[bool | None, str]:
    """根据 run 目录判断是否真的崩溃。

    返回 (confirmed_crash, note)：
      True  = 未完成且数据停滞（崩溃/中断）
      False = 有 final_model + .completed（正常完成）
      None  = 仍在训练或数据新鲜（无法判定）
    """
    now = time.time() if now is None else now
    completed = (run_dir / "final_model.zip").exists() and (
        run_dir / ".completed"
    ).exists()
    if completed:
        return False, "completed"
    eval_csv = run_dir / "eval_log.csv"
    if not eval_csv.exists():
        return None, "no_eval_log"
    age_h = (now - eval_csv.stat().st_mtime) / 3600.0
    if age_h >= stale_hours:
        return True, f"stale {age_h:.1f}h"
    return None, f"fresh {age_h:.1f}h"


def _run_frame(df, task, seed, by):
    """过滤单 run 并按时间/步长排序（与 consistency_check 同口径）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    d = df[(df["task"] == task) & (df["seed"] == seed)].copy()
    d[by] = pd.to_numeric(d[by], errors="coerce")
    return d.dropna(subset=[by]).sort_values(by).reset_index(drop=True)


def _tail_stall_minutes(snaps_df):
    """窗口末端当前连续停滞分钟数（timesteps 不变段，恢复即归零）。"""
    if snaps_df is None or len(snaps_df) < 2:
        return 0.0
    d = snaps_df.sort_values("time").reset_index(drop=True)
    times = [float(t) for t in d["time"]]
    vals = pd.to_numeric(d["timesteps"], errors="coerce").to_numpy(dtype=float)
    start_t = None
    for i in range(1, len(vals)):
        if pd.isna(vals[i]) or pd.isna(vals[i - 1]):
            start_t = None
        elif vals[i] == vals[i - 1]:
            if start_t is None:
                start_t = times[i - 1]
        else:
            start_t = None
    if start_t is None:
        return 0.0
    return (times[-1] - start_t) / 60.0


def _recent_neg_all(evals_df, window: int = 5) -> bool | None:
    """最近 window 个有效 eval 点是否全部为负（点数不足按可用计）。"""
    if evals_df is None or evals_df.empty:
        return None
    d = evals_df.copy()
    d["mean_reward"] = pd.to_numeric(d["mean_reward"], errors="coerce")
    d = d.dropna(subset=["mean_reward"])
    if d.empty:
        return None
    return bool((d["mean_reward"].tail(window) < 0).all())


def classify_local(
    task: str,
    seed: str,
    tables: dict,
    cfg: dict,
    stall_minutes: float | None = None,
    neg_recent: bool | None = None,
) -> tuple[bool | None, str]:
    """基于本地 data/datasets 判定是否真正崩溃（不依赖 Linux run 目录）。

    判定逻辑：
      - 已完成（runs.completed=True）：verdict=fail -> True；verdict=pass -> False；
        verdict 缺失 -> None（无法判定）
      - 未完成：尾部停滞 >= risk.stall_minutes.watch（默认 30 分钟）且最近 5 个
        有效 eval 点奖励持续为负 -> True；仅停滞达标 -> None（无法判定）；
        无停滞 -> None（训练中/新鲜）
    """
    runs = tables.get("runs")
    row = None
    if runs is not None and len(runs):
        m = runs[(runs["task"] == task) & (runs["seed"] == seed)]
        if len(m):
            row = m.iloc[0]
    completed = None
    verdict = None
    if row is not None:
        cv = row.get("completed")
        completed = bool(cv) if pd.notna(cv) else None
        v = row.get("verdict")
        verdict = str(v).strip().lower() if (pd.notna(v) and str(v).strip()) else None
    if completed is True:
        if verdict == "fail":
            return True, "completed+fail"
        if verdict == "pass":
            return False, "completed+pass"
        return None, "completed_no_verdict"
    snaps = _run_frame(tables.get("snapshots"), task, seed, by="time")
    if snaps.empty:
        return None, "no_snapshots"
    watch = float(cfg.get("risk", {}).get("stall_minutes", {}).get("watch", 30))
    stall = _tail_stall_minutes(snaps) if stall_minutes is None else stall_minutes
    evals = _run_frame(tables.get("eval_points"), task, seed, by="timesteps")
    neg = _recent_neg_all(evals) if neg_recent is None else neg_recent
    if stall >= watch and neg is True:
        return True, f"stall {stall:.0f}min+neg_reward"
    if stall >= watch:
        return None, f"stall {stall:.0f}min_no_neg"
    return None, f"fresh stall {stall:.0f}min"


def build_annotations(
    rows: list[dict],
    classify,
    now: float | None = None,
) -> list[dict]:
    """只标注 R2/R3 告警行，按 (timestamp, task, seed) 去重。"""
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for r in rows:
        level = str(r.get("level", ""))
        if level not in ("R2", "R3"):
            continue
        key = (str(r.get("timestamp")), str(r.get("task")), str(r.get("seed")))
        if key in seen:
            continue
        seen.add(key)
        crash, note = classify(r.get("task"), r.get("seed"))
        out.append(
            {
                "timestamp": r.get("timestamp"),
                "task": r.get("task"),
                "seed": r.get("seed"),
                "level": level,
                "triggered_rules": r.get("triggered_rules", ""),
                "eval_reward": r.get("eval_reward"),
                "ep_len": r.get("ep_len"),
                "confirmed_crash": crash,
                "note": note,
                "annotated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="R2/R3 告警崩溃标注")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    monitor_cfg = cfg.get("monitor", {})
    log_rel = monitor_cfg.get("log_csv", "data/monitor/realtime_log.csv")
    log_path = (PROJECT_ROOT / log_rel) if not pathlib.Path(log_rel).is_absolute() else pathlib.Path(log_rel)
    if not log_path.exists():
        print("无告警日志，跳过标注:", log_path)
        return
    rows = pd.read_csv(log_path).to_dict("records")
    out_dir = pathlib.Path(cfg.get("output_dir", "data/datasets"))
    tables: dict = {}
    for name in ("runs", "snapshots", "eval_points"):
        p = out_dir / f"{name}.csv"
        if not p.exists():
            continue
        if name == "runs":
            tables[name] = load_runs_merged(cfg)
        else:
            tables[name] = pd.read_csv(p)

    def classify(task: str, seed: str):
        return classify_local(task, seed, tables, cfg)

    annotations = build_annotations(rows, classify)
    out_path = PROJECT_ROOT / "data" / "monitor" / "alert_annotations.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    pd.DataFrame(annotations, columns=ANNOTATION_COLUMNS).to_csv(
        out_path, mode="a", header=new_file, index=False, encoding="utf-8-sig"
    )
    print(f"标注完成：{len(annotations)} 条 R2/R3 告警 -> {out_path}")


if __name__ == "__main__":
    main()
