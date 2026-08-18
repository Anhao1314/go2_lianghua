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
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    monitor_cfg = cfg.get("monitor", {})
    log_rel = monitor_cfg.get("log_csv", "data/monitor/realtime_log.csv")
    log_path = (PROJECT_ROOT / log_rel) if not pathlib.Path(log_rel).is_absolute() else pathlib.Path(log_rel)
    if not log_path.exists():
        print("无告警日志，跳过标注:", log_path)
        return
    rows = pd.read_csv(log_path).to_dict("records")
    source = cfg.get("source_repo")
    if source is None or not source.is_dir():
        raise SystemExit("需要 source_repo 才能对照 run 目录")

    def classify(task: str, seed: str):
        seed_dir = source / "rl" / "runs" / task / seed
        return classify_run(seed_dir)

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
