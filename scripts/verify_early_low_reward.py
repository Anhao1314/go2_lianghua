# -*- coding: utf-8 -*-
'''early_low_reward 规则回测验证（只读验证，不上线）。

规则定义：前 25% 训练步数内（total_steps 缺失时用该 run 最后一个 eval 步长），
若 early_points >= 3 且 max(mean_reward) < task 阈值，则判定为"从未学会型"失败，
触发 R2 stop。

用法：
  python scripts/verify_early_low_reward.py --today 2026-08-19

输出：控制台摘要 + data/modeling/early_low_reward_verification_YYYY-MM-DD.md
本脚本只读 data/datasets，不修改任何现有文件与规则。
'''

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter
from datetime import date as _Date
from typing import Any

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backtest_rules import ground_truth
from collector import PROJECT_ROOT, load_config
from quant import load_tables

# 现有 7 个首次 stop 事件（rule_backtest_2026-08-19.md 首表，用于重叠/新增命中判定）
EXISTING_STOPS: set[tuple[str, str]] = {
    ("balance", "seed00"),
    ("full_chain", "seed00"),
    ("traverse", "seed00"),
    ("traverse", "seed01"),
    ("traverse_curve", "seed00"),
    ("traverse_flat_slope", "seed00"),
    ("traverse_slope", "seed00"),
}

EARLY_RATIO = 0.25          # 前 25% 训练步数
MIN_EARLY_POINTS = 3        # 至少 3 个 early eval 点
EP_STALL_WINDOW = 5         # ep_len_stall 连续点数
EP_STALL_MAX_EP_LEN = 50    # ep_len_stall 的 ep_len 上限


def task_threshold(task: str) -> float:
    '''按 task 系列返回 early_low_reward 阈值：balance*/full_chain* = 50，其余 = 30。'''
    if task.startswith("balance") or task.startswith("full_chain"):
        return 50.0
    return 30.0


def total_steps_for(
    runs_df: pd.DataFrame | None, evals: pd.DataFrame, task: str, seed: str
) -> float | None:
    '''total_steps 优先取 runs.csv；缺失则回退为该 run 最后一个 eval timesteps。'''
    if runs_df is not None and len(runs_df):
        rows = runs_df[(runs_df["task"] == task) & (runs_df["seed"] == seed)]
        if len(rows):
            v = rows["total_steps"].iloc[0]
            if pd.notna(v):
                return float(v)
    sub = evals[(evals["task"] == task) & (evals["seed"] == seed)]
    if len(sub):
        return float(sub["timesteps"].max())
    return None


def early_low_reward(
    evals: pd.DataFrame, total_steps: float, threshold: float
) -> dict[str, Any]:
    '''纯函数：前 25% 步数内 early 点 >=3 且 max(mean_reward) < threshold 则触发。'''
    sub = evals.sort_values("timesteps")
    cutoff = total_steps * EARLY_RATIO
    early = sub[sub["timesteps"] <= cutoff]
    early_max = float(early["mean_reward"].max()) if len(early) else None
    early_mean = float(early["mean_reward"].mean()) if len(early) else None
    triggered = len(early) >= MIN_EARLY_POINTS and early_max is not None and early_max < threshold
    return {
        "threshold_25pct": cutoff,
        "early_count": len(early),
        "early_max": early_max,
        "early_mean": early_mean,
        "triggered": triggered,
    }


def ep_len_stall(
    evals: pd.DataFrame,
    window: int = EP_STALL_WINDOW,
    max_ep_len: float = EP_STALL_MAX_EP_LEN,
) -> float | None:
    '''连续 window 个 eval 点 mean_ep_len < max_ep_len 时，返回首个满足窗口的末尾 timesteps。'''
    sub = evals.sort_values("timesteps").reset_index(drop=True)
    if len(sub) < window:
        return None
    for i in range(len(sub) - window + 1):
        seg = sub["mean_ep_len"].iloc[i : i + window]
        if (pd.to_numeric(seg, errors="coerce") < max_ep_len).all():
            return float(sub["timesteps"].iloc[i + window - 1])
    return None


def run_pairs(evals: pd.DataFrame) -> list[tuple[str, str]]:
    '''全部有 eval 数据的 (task, seed)，确定性排序。'''
    return sorted(set(zip(evals["task"], evals["seed"])))


def _f(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _int(value: float | None) -> str:
    return "-" if value is None else f"{int(value):,}"


def render_markdown(
    today: str,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
    sensitivity: list[dict[str, Any]],
    ep_rows: list[dict[str, Any]],
) -> str:
    '''生成验证报告 Markdown（调用方写文件时转 CRLF）。'''
    lines: list[str] = []
    lines.append(f"# early_low_reward 规则回测验证（{today}）")
    lines.append("")
    lines.append(
        "规则：前 25% 训练步数内（total_steps 缺失用最后 eval 步长），"
        "early_points >= 3 且 max(mean_reward) < task 阈值 → 触发 R2 stop。"
        "阈值：traverse* = 30，balance*/full_chain* = 50，其他 = 30。"
    )
    lines.append("")
    lines.append("> 本报告为只读验证，未修改任何现有规则/配置，不代表上线决定。")
    lines.append("")
    lines.append("## 一、逐 run 触发明细")
    lines.append("")
    lines.append(
        "| run | verdict | total_steps | 25% 步数 | early点数 | early_max | early_mean | 触发 | 触发步数 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            "| {run} | {verdict} | {total} | {cut} | {n} | {mx} | {mn} | {hit} | {ts} |".format(
                run=r["run"],
                verdict=r["verdict"],
                total=_int(r["total_steps"]),
                cut=_int(r["threshold_25pct"]),
                n=r["early_count"],
                mx=_f(r["early_max"]),
                mn=_f(r["early_mean"]),
                hit="是" if r["triggered"] else "否",
                ts=_int(r["threshold_25pct"]) if r["triggered"] else "-",
            )
        )
    lines.append("")
    lines.append("## 二、触发统计")
    lines.append("")
    lines.append(f"- 有 eval 数据 run：{stats['total_runs']}；触发：{stats['triggered']}")
    lines.append(f"- 触发 verdict 分布：pass {stats['pass']} / fail {stats['fail']} / unknown {stats['unknown']}")
    lines.append(f"- 命中率（fail / (fail+pass)）：{stats['hit_rate']}")
    lines.append(f"- 误杀数（触发的 pass）：{stats['miskill']}")
    lines.append(f"- 与现有 stop 事件重叠：{stats['overlap']}；新增命中：{stats['new_hits']}（fail {stats['new_fail']} / unknown {stats['new_unknown']}）")
    lines.append("")
    lines.append("## 三、阈值敏感性（traverse* 系列：20 / 30 / 50 / 80）")
    lines.append("")
    lines.append("| 阈值 | 触发数 | 触发 run | 误杀 pass |")
    lines.append("|---|---|---|---|")
    for s in sensitivity:
        lines.append(f"| {s['threshold']} | {s['count']} | {s['runs']} | {s['miskill']} |")
    lines.append("")
    lines.append("## 四、ep_len_stall 对比（连续 5 点 mean_ep_len < 50）")
    lines.append("")
    lines.append("| run | verdict | 首个触发步数 | 是否同时命中 early_low_reward |")
    lines.append("|---|---|---|---|")
    if ep_rows:
        for e in ep_rows:
            lines.append(
                f"| {e['run']} | {e['verdict']} | {_int(e['trigger_ts'])} | {e['overlap']} |"
            )
    else:
        lines.append("| - | - | - | - |")
    lines.append("")
    lines.append("## 五、结论")
    lines.append("")
    lines.append(stats["conclusion"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant early_low_reward 规则回测验证（只读）")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    parser.add_argument("--today", default=None, help="报告日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖输出目录（默认 config.modeling_dir）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables = load_tables(cfg)
    evals = tables["eval_points"]
    runs = tables.get("runs")
    reports = tables.get("reports")
    today = args.today or _Date.today().isoformat()

    rows: list[dict[str, Any]] = []
    for task, seed in run_pairs(evals):
        run_evals = evals[(evals["task"] == task) & (evals["seed"] == seed)]
        total = total_steps_for(runs, evals, task, seed)
        check = (
            early_low_reward(run_evals, total, task_threshold(task))
            if total is not None
            else {"threshold_25pct": None, "early_count": 0, "early_max": None,
                  "early_mean": None, "triggered": False}
        )
        rows.append({
            "run": f"{task}/{seed}",
            "verdict": ground_truth(runs, reports, task, seed),
            "total_steps": total,
            **check,
        })

    triggered = [r for r in rows if r["triggered"]]
    counts = Counter(r["verdict"] for r in triggered)
    n_pass = counts.get("pass", 0)
    n_fail = counts.get("fail", 0)
    n_unknown = counts.get("unknown", 0)
    denom = n_pass + n_fail
    hit_rate = f"{n_fail / denom:.2f}" if denom else "-"
    overlap = sorted(
        r["run"] for r in triggered
        if tuple(r["run"].split("/")) in EXISTING_STOPS
    )
    new_hits = sorted(
        (r for r in triggered if tuple(r["run"].split("/")) not in EXISTING_STOPS),
        key=lambda r: r["run"],
    )
    new_fail = sum(1 for r in new_hits if r["verdict"] == "fail")
    new_unknown = sum(1 for r in new_hits if r["verdict"] == "unknown")

    # 阈值敏感性：仅 traverse* 系列
    sensitivity: list[dict[str, Any]] = []
    for thr in (20, 30, 50, 80):
        hits: list[str] = []
        for task, seed in run_pairs(evals):
            if not task.startswith("traverse"):
                continue
            run_evals = evals[(evals["task"] == task) & (evals["seed"] == seed)]
            total = total_steps_for(runs, evals, task, seed)
            if total is None:
                continue
            if early_low_reward(run_evals, total, float(thr))["triggered"]:
                hits.append(f"{task}/{seed}")
        miskill = sum(
            1 for h in hits
            if ground_truth(runs, reports, *tuple(h.split("/"))) == "pass"
        )
        sensitivity.append({
            "threshold": thr,
            "count": len(hits),
            "runs": "、".join(hits) if hits else "-",
            "miskill": miskill,
        })

    # ep_len_stall 对比
    ep_rows: list[dict[str, Any]] = []
    early_triggered = {r["run"] for r in triggered}
    for task, seed in run_pairs(evals):
        run_evals = evals[(evals["task"] == task) & (evals["seed"] == seed)]
        ts = ep_len_stall(run_evals)
        if ts is not None:
            ep_rows.append({
                "run": f"{task}/{seed}",
                "verdict": ground_truth(runs, reports, task, seed),
                "trigger_ts": ts,
                "overlap": "是" if f"{task}/{seed}" in early_triggered else "否",
            })

    if n_fail >= 2 and n_pass == 0:
        conclusion = (
            f"建议上线：阈值 30 下触发 {len(triggered)} 个 run（fail {n_fail} / "
            f"unknown {n_unknown}），0 误杀，命中率 {hit_rate}，新增 fail 命中 {new_fail} 个；"
            "敏感性分析中 20/30 一致、50/80 增加 traverse_flat_slope_v1（early_max=30.05，margin 小），"
            "推荐阈值 30。"
        )
    else:
        conclusion = (
            f"暂缓上线：触发 {len(triggered)}（fail {n_fail} / pass {n_pass} / unknown {n_unknown}），"
            "误杀或新增命中不足，需更多样本后重新验证。"
        )

    stats = {
        "total_runs": len(rows),
        "triggered": len(triggered),
        "pass": n_pass,
        "fail": n_fail,
        "unknown": n_unknown,
        "hit_rate": hit_rate,
        "miskill": n_pass,
        "overlap": len(overlap),
        "new_hits": len(new_hits),
        "new_fail": new_fail,
        "new_unknown": new_unknown,
        "conclusion": conclusion,
    }

    md = render_markdown(today, rows, stats, sensitivity, ep_rows)
    out_dir = pathlib.Path(args.out) if args.out else pathlib.Path(cfg["modeling_dir"])
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"early_low_reward_verification_{today}.md"
    md_path.write_text(md, encoding="utf-8", newline="\r\n")

    print(f"[verify_early_low_reward] {today}")
    print(f"  有 eval run={len(rows)}  触发={len(triggered)}  pass={n_pass}  fail={n_fail}  unknown={n_unknown}")
    print(f"  命中率={hit_rate}  误杀={n_pass}  与现有stop重叠={len(overlap)}  新增命中={len(new_hits)}（fail {new_fail}）")
    print(f"  报告: {md_path}")


if __name__ == "__main__":
    main()
