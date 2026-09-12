"""标签富化：把单维 verdict 扩展为多维训练诊断标签（B 方案）。

背景：balance/seed00 说明验收通过（用最佳 checkpoint）不代表训练健康——
奖励在 2M 步后从 100 塌缩到负值，但验收仍 pass。单维 verdict 有歧义。

新增维度（只用训练过程可观测数据，无未来信息泄漏）：
- training_collapsed：峰值后 reward < collapse_drop*peak，且其后始终
  未恢复到 collapse_recover*peak，且塌缩段跨度 >= collapse_min_span_ratio
  的观测窗口；
- best_step / best_step_ratio：最佳评估点位置（分母 = 观测窗口末尾
  last_eval_timesteps，缺失回退 total_steps）；
- collapse_step / collapse_ratio（修正 4）：首个 reward < collapse_drop*peak
  的 timesteps 及其占观测窗口比例；未塌缩为 None/NaN；
- stop_justified：verdict=='fail'，或（塌缩 且 best_step_ratio <
  stop_justified_ratio 且 collapse_ratio < stop_justified_collapse_ratio）——
  末段塌缩（最后 20% 内）早停无意义，不算 justified；
- data_quality：单向依赖 data_screening.classify（good/insufficient/anomalous）。

输出 enriched_labels_YYYY-MM-DD.csv（UTF-8 BOM，schema 校验）。
"""

from __future__ import annotations

import argparse
import pathlib
from datetime import date as _Date
from typing import Any

import pandas as pd

from collector import PROJECT_ROOT, load_config
from factors import run_factors
from quant import load_tables
from data_screening import classify, screening_checks
from modeling import resolve_out_dir
from schema import validate_frame

OUT_COLUMNS = [
    "task", "seed", "verdict", "success_rate", "duration_seconds",
    "training_collapsed", "best_step", "best_step_ratio", "collapse_step",
    "collapse_ratio", "stop_justified", "data_quality", "peak_reward",
    "final_reward", "eval_point_count",
]


def _to_float(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def enrich_one(
    evals: pd.DataFrame,
    tbs: pd.DataFrame | None,
    runs_row: dict[str, Any] | None,
    cfg: dict[str, Any],
    factors_f: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """单 run 多维标签计算（纯函数，无 I/O）。"""
    sc = cfg.get("screening") or {}
    drop = float(sc.get("collapse_drop", 0.5))
    recover = float(sc.get("collapse_recover", 0.8))
    min_span = float(sc.get("collapse_min_span_ratio", 0.2))
    stop_ratio = float(sc.get("stop_justified_ratio", 0.7))
    stop_collapse = float(sc.get("stop_justified_collapse_ratio", 0.8))

    d = evals.copy()
    if len(d):
        d = d.sort_values("timesteps").reset_index(drop=True)
    rewards = pd.to_numeric(d["mean_reward"], errors="coerce") if len(d) else pd.Series(dtype=float)
    steps = pd.to_numeric(d["timesteps"], errors="coerce") if len(d) else pd.Series(dtype=float)
    n = int(len(d))

    last_eval = float(steps.dropna().iloc[-1]) if n and steps.notna().any() else None
    total = _to_float(runs_row.get("total_steps")) if runs_row else None
    window = last_eval if last_eval else total

    # 峰值与最佳点
    peak_reward: float | None = None
    final_reward: float | None = None
    best_step: float | None = None
    best_step_ratio: float | None = None
    if n and rewards.notna().any():
        peak_reward = float(rewards.max())
        final_reward = float(rewards.iloc[-1]) if not pd.isna(rewards.iloc[-1]) else None
        peak_idx = int(rewards.idxmax())  # 第一个全局最大
        best_step = float(steps.iloc[peak_idx]) if not pd.isna(steps.iloc[peak_idx]) else None
        if best_step is not None and window:
            best_step_ratio = round(best_step / window, 4)

    # 塌缩检测（修正 4：collapse_step = 首个 < drop*peak 的点）
    collapsed = False
    collapse_step: float | None = None
    collapse_ratio: float | None = None
    if n >= 2 and peak_reward is not None and peak_reward > 0 and window:
        drop_thr = drop * peak_reward
        below = rewards.iloc[peak_idx + 1:] < drop_thr
        if below.any():
            cpos = int(below.idxmax())  # below 索引连续（peak_idx+1 起）
            cstep = float(steps.iloc[cpos])
            tail = rewards.iloc[cpos:]
            tail_ok = bool(tail.notna().all()) and float(tail.max()) < recover * peak_reward
            if tail_ok and last_eval is not None:
                span_ratio = (last_eval - cstep) / window
                if span_ratio >= min_span:
                    collapsed = True
                    collapse_step = cstep
                    collapse_ratio = round(cstep / window, 4)

    # 早停合理性
    verdict = str((runs_row or {}).get("verdict") or "").strip().lower()
    stop_justified = False
    if verdict == "fail":
        stop_justified = True
    elif (
        collapsed
        and best_step_ratio is not None
        and best_step_ratio < stop_ratio
        and collapse_ratio is not None
        and collapse_ratio < stop_collapse
    ):
        stop_justified = True

    # 数据质量（单向依赖 data_screening）
    passed, _reasons = screening_checks(evals, tbs, runs_row, cfg, factors_f=factors_f)
    quality = classify(passed)

    row = {
        "task": str(runs_row.get("task")) if runs_row else "",
        "seed": str(runs_row.get("seed")) if runs_row else "",
        "verdict": (runs_row or {}).get("verdict") if runs_row else None,
        "success_rate": _to_float((runs_row or {}).get("success_rate")) if runs_row else None,
        "duration_seconds": _to_float((runs_row or {}).get("duration_seconds")) if runs_row else None,
        "training_collapsed": collapsed,
        "best_step": int(best_step) if best_step is not None else None,
        "best_step_ratio": best_step_ratio,
        "collapse_step": collapse_step,
        "collapse_ratio": collapse_ratio,
        "stop_justified": stop_justified,
        "data_quality": quality,
        "peak_reward": round(peak_reward, 4) if peak_reward is not None else None,
        "final_reward": round(final_reward, 4) if final_reward is not None else None,
        "eval_point_count": n,
    }
    return row


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _filter(df: pd.DataFrame | None, task: str, seed: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df["task"] == task) & (df["seed"] == seed)]


def _row(runs_df: pd.DataFrame | None, task: str, seed: str) -> dict[str, Any] | None:
    if runs_df is None or runs_df.empty:
        return None
    rows = runs_df[(runs_df["task"] == task) & (runs_df["seed"] == seed)]
    return rows.iloc[0].to_dict() if len(rows) else None


def run_pairs(tables: dict[str, pd.DataFrame]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    runs = tables.get("runs")
    if runs is not None and len(runs):
        seen.update(zip(runs["task"], runs["seed"]))
    evals = tables.get("eval_points")
    if evals is not None and len(evals):
        seen.update(zip(evals["task"], evals["seed"]))
    return sorted(seen)


def build_enriched(
    tables: dict[str, pd.DataFrame],
    cfg: dict[str, Any],
    factors_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """全部 run 的富化标签表。

    factors_cache: 可选的 {(task, seed): run_factors 结果} 缓存，
    命中时直接复用（供 run_pipeline 一次算因子）。
    """
    rows = []
    for task, seed in run_pairs(tables):
        f = None
        if factors_cache is not None:
            f = factors_cache.get((task, seed))
        if f is None:
            f = run_factors(task, seed, tables, cfg)
        runs_row = _row(tables.get("runs"), task, seed)
        evals = _filter(tables.get("eval_points"), task, seed)
        tbs = _filter(tables.get("tb_points"), task, seed)
        rec = enrich_one(evals, tbs, runs_row, cfg, factors_f=f)
        rec["task"], rec["seed"] = task, seed
        rows.append(rec)
    df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    df = df.sort_values(["task", "seed"]).reset_index(drop=True)
    validate_frame(df, "enriched_labels")
    return df


def run(
    cfg: dict[str, Any],
    tables: dict[str, pd.DataFrame] | None = None,
    factors_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
    today: str | None = None,
    out: str | None = None,
) -> pd.DataFrame:
    """标签富化全流程：读表（缺省）-> 富化 -> 写 CSV -> 打印摘要，返回富化表。

    供 CLI 与 run_pipeline 复用；tables/factors_cache 传入时跳过重复计算。
    """
    if tables is None:
        tables = load_tables(cfg)
    today = today or _Date.today().isoformat()
    df = build_enriched(tables, cfg, factors_cache=factors_cache)

    out_dir = resolve_out_dir(cfg, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"enriched_labels_{today}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")

    n_collapsed = int(df["training_collapsed"].fillna(False).astype(bool).sum())
    n_stop = int(df["stop_justified"].fillna(False).astype(bool).sum())
    print(f"[label_enrichment] 标签富化 {today}：{len(df)} runs")
    print(f"  塌缩 {n_collapsed} / 早停合理 {n_stop} / 质量分布: "
          + ", ".join(f"{k} {v}" for k, v in df["data_quality"].value_counts().items()))
    print(f"  输出: {path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 标签富化（B 方案）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--today", default=None, help="输出日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖输出目录（默认 config.modeling_dir）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run(cfg, today=args.today, out=args.out)


if __name__ == "__main__":
    main()