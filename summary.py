"""数据集统计预览：Windows 与 Linux 均可运行，只读 data/datasets。"""

from __future__ import annotations

import argparse
import pathlib

import pandas as pd

from collector import PROJECT_ROOT, expand_path, load_config
from schema import KEY_COLUMNS


def read_table(out_dir: pathlib.Path, table: str) -> pd.DataFrame | None:
    path = out_dir / f"{table}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def print_summary(cfg: dict) -> None:
    out_dir = cfg["output_dir"]
    print(f"go2w-quant 数据集目录: {out_dir}")
    print("=" * 60)

    counts: dict[str, int] = {}
    for table in KEY_COLUMNS:
        df = read_table(out_dir, table)
        if df is None:
            note = "（由 Linux 采集端生成）" if table == "labels" else ""
            print(f"  {table:<14} 不存在{note}")
            continue
        counts[table] = len(df)
        print(f"  {table:<14} {len(df):>8} 行")

    runs = read_table(out_dir, "runs")
    if runs is not None and len(runs):
        completed = len(runs[runs["completed"].astype(bool)])
        with_report = len(runs[runs["verdict"].notna()])
        print(f"\nrun 覆盖: {len(runs)} 个 (完成 {completed}，有验收报告 {with_report})")
        print("按任务:")
        for task, g in runs.groupby("task"):
            print(
                f"  {task:<22} {len(g)} runs, "
                f"完成 {len(g[g['completed'].astype(bool)])}, "
                f"有报告 {len(g[g['verdict'].notna()])}"
            )

    evals = read_table(out_dir, "eval_points")
    if evals is not None and len(evals):
        covered = evals[["task", "seed"]].drop_duplicates()
        print(f"eval_points 覆盖 {len(covered)} 个 run")

    snaps = read_table(out_dir, "snapshots")
    if snaps is not None and len(snaps):
        print(
            "snapshots 时间范围: "
            f"{pd.to_datetime(snaps['time'], unit='s').min()} ~ "
            f"{pd.to_datetime(snaps['time'], unit='s').max()}"
        )

    costs = read_table(out_dir, "costs")
    if costs is None:
        print("costs: 未合并（lianghua 数据库不可用）")
    else:
        print(f"costs: {len(costs)} 行，累计成本 {costs['cost_yuan'].sum():.2f} 元")


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 数据集统计")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    print_summary(cfg)


if __name__ == "__main__":
    main()
