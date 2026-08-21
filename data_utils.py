"""数据分层工具：manual_labels.csv 人工标注层合并（第一阶段）。

背景：Linux 端自动采集多次覆盖 Windows 端人工标注（balance→pass、curve_v2 作弊暴露→pass 等），
根因是自动字段与人工字段混在同一文件。第一阶段引入 manual_labels.csv 作为"最终裁决层"：
  - runs.csv / labels.csv 的人工字段（verdict/success_rate/label_source/label_updated_at）
    以 manual_labels.csv 为准（非空值覆盖，空值保留原文件值）；
  - manual_labels.csv 不存在时回退直接读取原文件；
  - runs.csv 仍保留人工字段（备份），第二阶段验证通过后再清理。
"""
from __future__ import annotations

import pathlib

import pandas as pd

from collector import PROJECT_ROOT, load_config

# 人工层字段：合并时以 manual_labels.csv 非空值覆盖
MANUAL_COLUMNS = ("verdict", "success_rate", "label_source", "label_updated_at")


def _resolve_out_dir(cfg: dict | None) -> pathlib.Path:
    """解析数据目录（cfg 缺省时读取 config.json；相对路径锚定到项目根）。"""
    if cfg is None:
        cfg = load_config()
    raw = cfg.get("output_dir", "")
    if raw:
        p = pathlib.Path(raw)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "data"


def _merge_manual(base: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """按 (task, seed) 左连接 manual，人工字段非空值覆盖原文件值。

    只覆盖 base 已存在的列：runs schema 不含 label_source/label_updated_at，
    合并后不得引入多余列，否则 validate_frame 报"多余列"错误。
    """
    base_cols = set(base.columns)
    merged = base.merge(manual, on=["task", "seed"], how="left", suffixes=("", "_manual"))
    for col in MANUAL_COLUMNS:
        if col not in base_cols:
            if col in merged.columns:
                merged.drop(columns=[col], inplace=True)
            continue
        manual_col = f"{col}_manual"
        if manual_col in merged.columns:
            merged[col] = merged[manual_col].fillna(merged[col])
            merged.drop(columns=[manual_col], inplace=True)
    return merged


def load_runs_merged(cfg: dict | None = None) -> pd.DataFrame | None:
    """读取 runs.csv，用 manual_labels.csv 覆盖人工字段；文件不存在返回 None。"""
    out_dir = _resolve_out_dir(cfg)
    runs_path = out_dir / "runs.csv"
    manual_path = out_dir / "manual_labels.csv"
    if not runs_path.exists():
        return None
    runs = pd.read_csv(runs_path, encoding="utf-8-sig")
    if manual_path.exists():
        manual = pd.read_csv(manual_path, encoding="utf-8-sig")
        runs = _merge_manual(runs, manual)
    return runs


def load_labels_merged(cfg: dict | None = None) -> pd.DataFrame | None:
    """读取 labels.csv，用 manual_labels.csv 覆盖人工字段；文件不存在返回 None。"""
    out_dir = _resolve_out_dir(cfg)
    labels_path = out_dir / "labels.csv"
    manual_path = out_dir / "manual_labels.csv"
    if not labels_path.exists():
        return None
    labels = pd.read_csv(labels_path, encoding="utf-8-sig")
    if manual_path.exists():
        manual = pd.read_csv(manual_path, encoding="utf-8-sig")
        labels = _merge_manual(labels, manual)
    return labels

def load_all_tables(cfg: dict | None = None) -> dict[str, pd.DataFrame]:
    """一次性加载全部数据表（6 张因子表 + labels），供 run_pipeline 复用。

    与 quant.load_tables 同款读取方式（runs 走 load_runs_merged，其余直读并校验），
    另追加 labels 键（走 load_labels_merged）。缺失表跳过。
    注意：不 import quant（避免循环依赖），读取逻辑内联于此。
    """
    from schema import validate_frame

    out_dir = _resolve_out_dir(cfg)
    tables: dict[str, pd.DataFrame] = {}
    for table in ("runs", "eval_points", "tb_points", "snapshots", "reports", "costs"):
        if table == "runs":
            df = load_runs_merged(cfg)
            if df is not None:
                validate_frame(df, "runs")
                tables[table] = df
            continue
        tpath = out_dir / f"{table}.csv"
        if not tpath.exists():
            continue
        df = pd.read_csv(tpath)
        validate_frame(df, table)
        tables[table] = df
    labels = load_labels_merged(cfg)
    if labels is not None:
        tables["labels"] = labels
    return tables
