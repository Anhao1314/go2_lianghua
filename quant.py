"""量化风控日报生成器：只读 data/datasets，输出 data/reports/quant_YYYY-MM-DD.md 与同名 .json。

用法：
  python quant.py --config config.json                      # 用当天日期
  python quant.py --config config.json --today 2026-08-17   # 指定报告日期（成本窗口）
  python quant.py --config config.json --out data/reports   # 覆盖报告目录

报告为"建议制"：只给出 continue / watch / stop / tune / resize 建议与风险等级，
不自动干预训练。阈值全部来自 config.json 的 risk 段。
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from datetime import date as _Date

import pandas as pd

from collector import PROJECT_ROOT, load_config
from factors import DECISIONS, QuantResult, compute_all
from schema import validate_frame

# 因子来源表；labels 为 v3 建模标签表（y），不是因子输入
FACTOR_TABLES = ("runs", "eval_points", "tb_points", "snapshots", "reports", "costs")


def read_table(out_dir: pathlib.Path, table: str) -> pd.DataFrame | None:
    """只读一张 CSV；不存在返回 None，存在则按 schema 校验。"""
    path = out_dir / f"{table}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    validate_frame(df, table)
    return df


def load_tables(cfg: dict) -> dict[str, pd.DataFrame]:
    """读取 data/datasets 下全部表（缺失表跳过）。"""
    out_dir = pathlib.Path(cfg["output_dir"])
    tables: dict[str, pd.DataFrame] = {}
    for table in FACTOR_TABLES:
        df = read_table(out_dir, table)
        if df is not None:
            tables[table] = df
    return tables


def resolve_report_dir(cfg: dict, override: str | None) -> pathlib.Path:
    raw = override or cfg.get("report_dir") or "data/reports"
    p = pathlib.Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


# --------------------------------------------------------------------------
# Markdown 报告
# --------------------------------------------------------------------------

def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _factor_line(factors: dict) -> str:
    keys = [
        "eval_points", "eval_last_timesteps", "eval_last_reward", "eval_peak_reward",
        "eval_drawdown", "eval_slope_per_1e6", "eval_std_recent", "progress_ratio",
        "reward_peak_ratio", "approx_kl_last", "std_last", "ev_neg_streak",
        "value_loss_divergent", "report_rows", "verdict_fail_ratio", "success_rate_mean",
        "max_dev_max", "min_clear_min", "falls_mean", "nan_count",
        "snapshot_count", "time_span_minutes", "stall_minutes", "idle_minutes",
        "cpu_percent_max", "mem_percent_max", "swap_percent_max", "timesteps_growth",
    ]
    parts = []
    for k in keys:
        if k in factors:
            parts.append(f"{k}={_fmt(factors[k])}")
    return "，".join(parts)


def _level_badge(level: str) -> str:
    return {"R0": "✅ R0", "R1": "🟡 R1", "R2": "🟠 R2", "R3": "🔴 R3"}.get(level, level)


def render_markdown(result: QuantResult) -> str:
    """把 QuantResult 渲染为人类可读的 Markdown 日报。"""
    lines: list[str] = []
    add = lines.append
    add(f"# go2w-quant 量化风控日报：{result.today}")
    add("")
    add(f"- 生成时间：{result.generated_at}　全局风险等级：**{_level_badge(result.global_level)}**")
    cov = " / ".join(f"{k} {v}" for k, v in sorted(result.coverage.items()))
    add(f"- 数据覆盖：{cov or '（无）'}")
    add("")

    add("## 一、决策汇总")
    add("")
    add("| 等级 | 任务 | seed | 决策 | 触发证据 |")
    add("|---|---|---|---|---|")
    for r in result.runs:
        evidence = "；".join(r.reasons) if r.reasons else "—"
        evidence = evidence.replace("|", "｜")
        add(f"| {_level_badge(r.level)} | {r.task} | {r.seed} | **{r.decision}** | {evidence} |")
    add("")

    add("## 二、风险清单（R1 及以上）")
    add("")
    risky = [r for r in result.runs if r.level != "R0"]
    if not risky:
        add("- 无")
    for r in risky:
        for item in r.risks:
            add(f"- **{item.level}** `{r.task}/{r.seed}` [{item.table}/{item.factor}] {item.message}")
    add("")

    add("## 三、成本与资源")
    add("")
    cost = result.cost
    if cost.get("present"):
        add(f"- 成本：今日 {cost['daily_cost']:.2f}/{cost['daily_budget']:.2f} 元"
            f"，本周 {cost['weekly_cost']:.2f}/{cost['weekly_budget']:.2f} 元"
            f"，本月 {cost['monthly_cost']:.2f}/{cost['monthly_budget']:.2f} 元"
            f"，累计 {cost['total_cost']:.2f} 元")
        cr = cost.get("cache_rate")
        add(f"- token 缓存率：{f'{cr:.1%}' if cr is not None else '-'}")
    else:
        add("- 成本：无 costs 数据（lianghua 数据库不可用）")
    res = result.resources
    if res.get("present"):
        add(f"- 资源：CPU 均值/峰值 {res.get('cpu_mean', '-')}/{res.get('cpu_max', '-')}%"
            f"，内存 {res.get('mem_mean', '-')}/{res.get('mem_max', '-')}%"
            f"，Swap 峰值 {res.get('swap_max', '-')}%"
            f"，负载峰值 {res.get('load1_max', '-')}"
            f"，疑似空闲 {res.get('idle_minutes', 0)} 分钟"
            f"（采样 {res.get('sampled_rows', 0)} 行）")
    else:
        add("- 资源：无资源采样数据")
    add("")

    add("## 四、全局风险")
    add("")
    if result.global_risks:
        for item in result.global_risks:
            add(f"- **{item.level}** [{item.table}/{item.factor}] {item.message}")
    else:
        add("- 无")
    add("")

    add("## 五、逐任务因子")
    add("")
    for r in result.runs:
        add(f"### {r.task} / {r.seed}（{_level_badge(r.level)} · 建议 **{r.decision}**）")
        add("")
        if r.factors:
            add(f"- 因子：{_factor_line(r.factors)}")
        else:
            add("- 因子：暂无可用数据")
        if r.risks:
            for item in r.risks:
                add(f"- 风险：**{item.level}** {item.message}")
        else:
            add("- 风险：无")
        add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 量化风控日报")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    parser.add_argument("--today", default=None, help="报告日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖报告目录（默认 config.report_dir）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables = load_tables(cfg)
    today = args.today or _Date.today().isoformat()
    result = compute_all(cfg, tables, today=today)

    report_dir = resolve_report_dir(cfg, args.out)
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / f"quant_{today}.md"
    json_path = report_dir / f"quant_{today}.json"
    md_path.write_text(render_markdown(result), encoding="utf-8")
    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 控制台摘要
    dec_counts = Counter(r.decision for r in result.runs)
    level_counts = Counter(r.level for r in result.runs)
    print(f"[go2w-quant] 量化风控日报 {today}　全局风险: {result.global_level}")
    print(f"  数据覆盖: {result.coverage}")
    print(f"  决策分布: " + ", ".join(f"{d} {dec_counts.get(d, 0)}" for d in DECISIONS))
    print(f"  风险分布: " + ", ".join(f"{l} {level_counts.get(l, 0)}" for l in ("R0", "R1", "R2", "R3")))
    for r in result.runs:
        if r.level in ("R2", "R3"):
            print(f"  !! {r.task}/{r.seed} [{r.level}] 建议 {r.decision}")
            for item in r.risks:
                print(f"     - {item.message}")
    print(f"  报告: {md_path}")
    print(f"  JSON: {json_path}")


if __name__ == "__main__":
    main()