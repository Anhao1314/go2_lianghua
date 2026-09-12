"""特征固化：把 factors 因子矩阵与 labels 标签合成 v3 建模数据集（X + y）。

用法：
  python modeling.py --config config.json                    # 今天日期
  python modeling.py --config config.json --today 2026-08-17
  python modeling.py --config config.json --out data/modeling

输出 data/modeling/dataset_YYYY-MM-DD.csv（UTF-8 BOM），每行一个 (task, seed)：
  task / seed / <X: 数值因子特征> / completed / verdict / success_rate /
  duration_seconds / label_source

只读 data/datasets；labels.csv 兼容合并版（8 列）与早期版（9 列）。
"""

from __future__ import annotations

import argparse
import pathlib
from datetime import date as _Date
from typing import Any

import pandas as pd

from collector import PROJECT_ROOT, load_config
from factors import compute_all
from data_utils import load_labels_merged
from quant import load_tables

# 标签（y）与来源列；其余来自 labels.csv 的列（如早期版的 final_reward）不属于标签
Y_COLUMNS = ("completed", "verdict", "success_rate", "duration_seconds", "label_source")

# completed 是训练结束后的状态，决策时刻不可知，不进特征（X）；它作为 y 保留
EXCLUDED_FEATURES = {"completed", "task", "seed"}


def read_labels_csv(
    cfg: dict | None = None,
    labels_df: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    """读取 labels.csv（经 manual_labels.csv 人工层合并）；合并版 8 列与早期版 9 列均兼容，只保留 y 列。

    labels_df 传入时直接使用（供 run_pipeline 内存传递），缺省回退磁盘读取。
    """
    df = load_labels_merged(cfg) if labels_df is None else labels_df
    if df is None:
        return None
    keep = ["task", "seed"] + [c for c in Y_COLUMNS if c in df.columns]
    out = df[keep].copy()
    if "completed" in out.columns:
        out["completed"] = out["completed"].map(
            lambda v: (
                str(v).strip().lower() in ("true", "1", "1.0")
                if not pd.isna(v)
                else None
            )
        )
    return out


def build_dataset(
    cfg: dict,
    today: str,
    tables: dict[str, pd.DataFrame] | None = None,
    labels: pd.DataFrame | None = None,
    factors_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """因子矩阵（X，来自 factors）与标签（y，来自 labels.csv）合成一行一个 run。

    tables/labels/factors_cache 供 run_pipeline 内存传递，缺省回退磁盘读取与全量计算。
    """
    if tables is None:
        tables = load_tables(cfg)
    result = compute_all(cfg, tables, today=today, factors_cache=factors_cache)

    feat_rows: list[dict] = []
    for r in result.runs:
        row: dict = {"task": r.task, "seed": r.seed}
        for k, v in r.factors.items():
            if k in EXCLUDED_FEATURES:
                continue
            try:
                num = float(v)
            except (TypeError, ValueError):
                continue  # 非数值因子（如字符串）不进入 X
            if pd.isna(num):
                continue
            row[k] = num
        feat_rows.append(row)
    feats = pd.DataFrame(feat_rows)

    labels = read_labels_csv(cfg, labels_df=labels)
    if labels is not None and len(labels):
        df = feats.merge(labels, on=["task", "seed"], how="outer")
    else:
        df = feats.copy()
        for c in Y_COLUMNS:
            df[c] = None

    for c in Y_COLUMNS:
        if c not in df.columns:
            df[c] = None  # 旧版 labels.csv 缺列时补齐
    df = df.sort_values(["task", "seed"]).reset_index(drop=True)
    x_cols = [c for c in df.columns if c not in ("task", "seed") + tuple(Y_COLUMNS)]
    # 特征列统一转数值（非数值因子置 NaN，建模时丢弃或填充）
    for c in x_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["task", "seed"] + sorted(x_cols) + list(Y_COLUMNS)]


def resolve_out_dir(cfg: dict, override: str | None) -> pathlib.Path:
    raw = override or cfg.get("modeling_dir") or "data/modeling"
    p = pathlib.Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


def run(
    cfg: dict,
    today: str | None = None,
    tables: dict[str, pd.DataFrame] | None = None,
    labels: pd.DataFrame | None = None,
    factors_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
    out: str | None = None,
    screened: bool = False,
    full_df: pd.DataFrame | None = None,
    enriched_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """特征固化全流程：建数据集 -> 写 CSV ->（可选）筛选输出，返回 dataset。

    供 CLI 与 run_pipeline 复用；tables/labels/factors_cache 传入时跳过重复计算；
    full_df/enriched_df 供 --screened 内存传递（缺省回退磁盘读取）。
    """
    today = today or _Date.today().isoformat()
    df = build_dataset(cfg, today, tables=tables, labels=labels,
                       factors_cache=factors_cache)

    out_dir = resolve_out_dir(cfg, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dataset_{today}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    if screened:
        import data_screening  # 函数内 import 避免循环依赖
        data_screening.screen_outputs(
            cfg, today, out_dir,
            tables=tables, full_df=full_df, enriched_df=enriched_df,
            factors_cache=factors_cache,
        )

    x_cols = [c for c in df.columns if c not in ("task", "seed") + tuple(Y_COLUMNS)]
    n_verdict = int(df["verdict"].notna().sum())
    n_sr = int(df["success_rate"].notna().sum())
    n_dur = int(df["duration_seconds"].notna().sum())
    n_completed = int(df["completed"].fillna(False).astype(bool).sum())
    print(f"[go2w-quant] 特征数据集 {today}：{len(df)} runs × {len(x_cols)} 特征")
    print(f"  标签可用：verdict {n_verdict} / success_rate {n_sr} / duration {n_dur} / completed {n_completed}")
    print(f"  输出: {path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 特征固化（B 方案）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--today", default=None, help="数据集日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖输出目录（默认 config.modeling_dir）")
    parser.add_argument("--screened", action="store_true",
                        help="生成全量数据集后追加数据筛选输出（需先运行 label_enrichment.py）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run(cfg, today=args.today, out=args.out, screened=args.screened)


if __name__ == "__main__":
    main()
