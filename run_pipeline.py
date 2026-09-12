"""统一管线入口：一次启动 Python，内存传递 DataFrame 与因子缓存（方案 A）。

设计：
- 只读一次数据：data_utils.load_all_tables(cfg)（6 张因子表 + labels）；
- 只算一次因子：对全部 (task, seed) 调一次 run_factors 建缓存，
  注入 label_enrichment / data_screening / modeling / quant；
- 串行调用各模块 run()：label_enrichment -> modeling -> data_screening
  -> backtest_rules -> quant；backtest_rules 按"在线视野"逐截面重算因子
  （口径要求），不缓存；
- 输出文件路径/格式/内容与 5 脚本串行执行完全一致（quant 的
  generated_at 为运行时时间戳，属正常差异）。

用法：
  python run_pipeline.py --today 2026-08-19
  python run_pipeline.py --today 2026-08-19 --skip backtest
  python run_pipeline.py --today 2026-08-19 --out data/modeling_tmp --verbose
"""

from __future__ import annotations

import argparse
import time
from datetime import date as _Date
from typing import Any

import pandas as pd

from collector import PROJECT_ROOT, load_config
from data_utils import load_all_tables
from factors import run_factors
from label_enrichment import run_pairs

SKIP_NAMES = (
    "label_enrichment", "modeling", "data_screening", "backtest_rules", "quant",
)

# 兼容 --skip backtest 之类的短别名
_SKIP_ALIASES = {
    "label": "label_enrichment",
    "screen": "data_screening",
    "backtest": "backtest_rules",
}


def build_factors_cache(
    tables: dict[str, pd.DataFrame], cfg: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    """对全部 (task, seed) 各算一次因子，返回 {(task, seed): run_factors 结果}。"""
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    for task, seed in run_pairs(tables):
        cache[(task, seed)] = run_factors(task, seed, tables, cfg)
    return cache


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 统一管线入口（方案 A）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--today", default=None, help="日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--skip", default=None,
                        help="跳过步骤，逗号分隔：" + ",".join(SKIP_NAMES))
    parser.add_argument("--verbose", action="store_true", help="打印每步耗时")
    parser.add_argument("--out", default=None,
                        help="覆盖 modeling/report 输出目录（默认 config 路径）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    today = args.today or _Date.today().isoformat()
    skipped = {
        _SKIP_ALIASES.get(s.strip(), s.strip())
        for s in (args.skip or "").split(",") if s.strip()
    }
    bad = skipped - set(SKIP_NAMES)
    if bad:
        raise SystemExit(f"未知步骤: {sorted(bad)}（可选: {','.join(SKIP_NAMES)}）")

    t0 = time.perf_counter()
    timings: list[tuple[str, float]] = []

    def step(name: str, fn: Any) -> Any:
        ts = time.perf_counter()
        res = fn()
        timings.append((name, time.perf_counter() - ts))
        return res

    # 1. 一次加载全部表
    tables = step("load_all_tables", lambda: load_all_tables(cfg))
    if args.verbose:
        print("[run_pipeline] 数据表: " + ", ".join(
            f"{k} {len(v)}" for k, v in sorted(tables.items())))

    # 2. 一次算全部因子（供 label/screen/modeling/quant 复用）
    factors_cache = step("factors_cache", lambda: build_factors_cache(tables, cfg))

    enriched = None
    if "label_enrichment" not in skipped:
        import label_enrichment
        enriched = step("label_enrichment", lambda: label_enrichment.run(
            cfg, tables=tables, factors_cache=factors_cache,
            today=today, out=args.out))

    dataset = None
    if "modeling" not in skipped:
        import modeling
        dataset = step("modeling", lambda: modeling.run(
            cfg, today=today, tables=tables,
            labels=tables.get("labels"),
            factors_cache=factors_cache, out=args.out))

    if "data_screening" not in skipped:
        import data_screening
        step("data_screening", lambda: data_screening.run(
            cfg, tables=tables, full_df=dataset, enriched_df=enriched,
            factors_cache=factors_cache, today=today, out=args.out))

    if "backtest_rules" not in skipped:
        import backtest_rules
        step("backtest_rules", lambda: backtest_rules.run(
            cfg, tables=tables, today=today, out=args.out))

    if "quant" not in skipped:
        import quant
        step("quant", lambda: quant.run(
            cfg, tables=tables, factors_cache=factors_cache,
            today=today, out=args.out))

    total = time.perf_counter() - t0
    print(f"[run_pipeline] 完成 {today}：总耗时 {total:.1f}s")
    for name, dt in timings:
        print(f"  {name}: {dt:.1f}s")

    # 标签分布与 backtest_rules 口径一致（三层标签：pass/fail/unknown）
    try:
        from backtest_rules import label_counts
        c = label_counts(tables)
        print(f"  标签分布: pass={c['pass']} / fail={c['fail']} / unknown={c['unknown']}")
    except Exception:
        pass
    if dataset is not None and len(dataset):
        x_cols = [col for col in dataset.columns if col not in ("task", "seed")]
        print(f"  数据集: {len(dataset)} runs × {len(x_cols)} 列")


if __name__ == "__main__":
    main()
