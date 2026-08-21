"""数据质量校验系统（阶段1）：6 大类 20+ 项只读校验。

设计（梁文锋量化思路：垃圾进，垃圾出）：
- 只读校验，不修改任何数据文件，只生成报告：
  data/quality_report_{today}.md + data/quality_issues_{today}.csv（可选 JSON）；
- 读取 runs/labels 使用 data_utils 合并层（manual_labels.csv 人工层生效），
  但"标签一致性"（E 类）分别读取原始 runs.csv/labels.csv/manual_labels.csv
  对比，合并后看不到不一致；
- 容错：单个文件缺失/格式错误时记录错误并继续其他校验；
- 退出码：0=无 critical，1=有 critical，2=运行时错误（文件缺失等）。

用法：
  python scripts/data_quality_check.py --today 2026-08-21
  python scripts/data_quality_check.py --today 2026-08-21 --out data/ --threshold warning --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import date
from typing import Any

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from collector import PROJECT_ROOT, load_config
from data_utils import load_runs_merged, load_labels_merged

# ---------------- 阈值常量（脚本顶部集中配置，便于调整） ----------------
MIN_EVAL_POINTS = 10        # A2：eval 点数下限
MIN_TB_POINTS = 50          # A3：tb 点数下限
MIN_SNAPSHOTS = 10          # A4：snapshot 数下限
REWARD_MAX = 600.0          # B1：奖励上限（物理不合理）
REWARD_MIN = -200.0         # B1：奖励下限
EP_LEN_MAX = 1500.0         # B2：ep_len 上限（15s x 100Hz）
TIMESTEPS_MAX = 10_000_000  # B3：训练步数上限
DISTANCE_MAX = 10.0         # B4：distance 上限（弯道总长约 4.85m）
FALLS_MAX = 10              # B6：falls 上限
LARGE_GAP_STEPS = 500_000   # C2：相邻 eval 点大跳变阈值
EARLY_EVAL_MAX_STEPS = 200_000  # C3：首个 eval 点过晚阈值
TOTAL_STEPS_TOL = 0.20      # C4/F2：total_steps 偏差容忍 20%

# E3：已知合法 label_source（含项目实际使用的 manual_curve / manual_cheating_exposed）
KNOWN_LABEL_SOURCES = {
    "formal_eval", "manual", "auto", "cheating_exposed", "unknown",
    "manual_curve", "manual_cheating_exposed",
}

# 输出目录解析：--out 覆盖，默认 data/（锚定项目根）
def _out_dir(args_out: str | None) -> pathlib.Path:
    if args_out:
        p = pathlib.Path(args_out)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "data"


# ---------------- 数据加载（容错） ----------------
def _read_csv(path: pathlib.Path) -> pd.DataFrame | None:
    """读取 CSV（utf-8-sig），失败返回 None 并打印原因。"""
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:  # noqa: BLE001 - 容错：记录并继续
        print(f"[data_quality] 读取失败 {path.name}: {exc}")
        return None


def load_tables(cfg: dict[str, Any], out_dir: pathlib.Path) -> dict[str, Any]:
    """加载全部数据表。

    runs/labels 走 data_utils 合并层（人工层生效）；同时保留原始 runs/labels
    （E 类标签一致性对比用）与 manual_labels.csv。
    """
    ds_dir = out_dir / "datasets"
    tables: dict[str, Any] = {}
    tables["runs_merged"] = load_runs_merged(cfg)
    tables["labels_merged"] = load_labels_merged(cfg)
    tables["manual"] = _read_csv(ds_dir / "manual_labels.csv")
    for name in ("runs", "labels", "eval_points", "tb_points", "snapshots", "reports"):
        tables[name] = _read_csv(ds_dir / f"{name}.csv")
    return tables


# ---------------- 问题记录 ----------------
class _Collector:
    """问题收集器：统一生成 issue_id 并分类统计。"""

    def __init__(self) -> None:
        self.issues: list[dict[str, Any]] = []
        self._seq = 0

    def add(self, category: str, severity: str, task: str, seed: str,
            issue_type: str, description: str, suggestion: str = "") -> None:
        self._seq += 1
        self.issues.append({
            "issue_id": f"DQ{self._seq:03d}",
            "category": category,
            "severity": severity,
            "task": task,
            "seed": seed,
            "issue_type": issue_type,
            "description": description,
            "suggestion": suggestion,
        })

    def check_error(self, category: str, exc: Exception) -> None:
        self.add(category, "critical", "", "",
                 "check_error", f"{category} 类校验执行失败: {exc}", "修复校验脚本")


# ---------------- A. 缺失值检测 ----------------
def check_missing(collector: _Collector, t: dict[str, Any]) -> None:
    runs = t.get("runs_merged")
    eval_df = t.get("eval_points")
    tb_df = t.get("tb_points")
    snap_df = t.get("snapshots")
    reports = t.get("reports")

    if runs is not None:
        for _, row in runs.iterrows():
            task, seed = str(row.get("task", "")), str(row.get("seed", ""))
            if not task or not seed or (isinstance(row.get("seed"), float) and pd.isna(row.get("seed"))):
                collector.add("A", "critical", task, seed, "missing_key",
                              "run 缺少 task 或 seed（主键不完整）", "补全主键")
            if pd.isna(row.get("total_steps")):
                collector.add("A", "warning", task, seed, "missing_total_steps",
                              "total_steps 为空", "补全训练步数（或用 eval 末点推算）")
            v = row.get("verdict")
            if isinstance(v, str) and v.strip() == "":
                collector.add("A", "warning", task, seed, "invalid_verdict",
                              "verdict 为空字符串（unknown 建议统一用 NaN/unknown 表示）",
                              "统一 unknown 表示")

    # A2/A3/A4：按 run 统计点数
    for df, col, itype, minimum, label in (
        (eval_df, "task", "insufficient_eval_points", MIN_EVAL_POINTS, "eval"),
        (tb_df, "task", "insufficient_tb_points", MIN_TB_POINTS, "tb"),
        (snap_df, "task", "insufficient_snapshots", MIN_SNAPSHOTS, "snapshot"),
    ):
        if df is None or runs is None:
            continue
        counts = df.groupby(["task", "seed"]).size()
        for (task, seed), n in counts.items():
            if n < minimum:
                collector.add("A", "warning", str(task), str(seed), itype,
                              f"{label} 点数仅 {n}（<{minimum}）",
                              "已知问题可接受（如 dagger 系列），否则补采数据")

    # A5：verdict=pass/fail 的 run 必须在 reports.csv 有对应行
    if runs is not None and reports is not None and len(reports):
        report_keys = set(zip(reports["task"].astype(str), reports["seed"].astype(str)))
        for _, row in runs.iterrows():
            v = row.get("verdict")
            if v in ("pass", "fail"):
                key = (str(row["task"]), str(row["seed"]))
                if key not in report_keys:
                    collector.add("A", "critical", key[0], key[1], "missing_report",
                                  f"verdict={v} 但 reports.csv 无对应验收行",
                                  "补充正式验收报告或调整标签来源")

    # A6：verdict=pass/fail 的 run 必须有 eval 数据（≥1 点）
    if runs is not None and eval_df is not None and len(eval_df):
        eval_keys = set(zip(eval_df["task"].astype(str), eval_df["seed"].astype(str)))
        for _, row in runs.iterrows():
            v = row.get("verdict")
            if v in ("pass", "fail"):
                key = (str(row["task"]), str(row["seed"]))
                if key not in eval_keys:
                    collector.add("A", "critical", key[0], key[1], "missing_eval_data",
                                  f"verdict={v} 但无任何 eval 点（无法验证训练表现）",
                                  "补充 eval 数据或改为 unknown")


# ---------------- B. 异常值检测 ----------------
def check_outliers(collector: _Collector, t: dict[str, Any]) -> None:
    eval_df = t.get("eval_points")
    reports = t.get("reports")

    if eval_df is not None and len(eval_df):
        for _, row in eval_df.iterrows():
            task, seed = str(row.get("task", "")), str(row.get("seed", ""))
            ts = row.get("timesteps")
            if pd.notna(ts) and (ts < 0 or ts > TIMESTEPS_MAX):
                collector.add("B", "warning", task, seed, "timesteps_outlier",
                              f"timesteps={ts} 超出 [0, {TIMESTEPS_MAX}]", "检查数据源")
            r = row.get("mean_reward")
            if pd.notna(r) and (r > REWARD_MAX or r < REWARD_MIN):
                collector.add("B", "warning", task, seed, "reward_outlier",
                              f"mean_reward={r} 超出 [{REWARD_MIN}, {REWARD_MAX}]（物理不合理）",
                              "检查 eval 采集或单位换算")
            ep = row.get("ep_len")
            if pd.notna(ep) and (ep < 0 or ep > EP_LEN_MAX):
                collector.add("B", "warning", task, seed, "ep_len_outlier",
                              f"ep_len={ep} 超出 [0, {EP_LEN_MAX}]（15s x 100Hz）",
                              "检查 episode 时长采集")

    if reports is not None and len(reports):
        for _, row in reports.iterrows():
            task, seed = str(row.get("task", "")), str(row.get("seed", ""))
            d = row.get("distance") if "distance" in row else row.get("avg_distance")
            if pd.notna(d) and (d < 0 or d > DISTANCE_MAX):
                collector.add("B", "warning", task, seed, "distance_outlier",
                              f"distance={d} 超出 [0, {DISTANCE_MAX}]（任务总长约 4.85m）",
                              "检查验收测量")
            f = row.get("falls") if "falls" in row else row.get("fall_count")
            if pd.notna(f) and (f < 0 or f > FALLS_MAX):
                collector.add("B", "warning", task, seed, "falls_outlier",
                              f"falls={f} 超出 [0, {FALLS_MAX}]", "检查验收记录")
            sr = row.get("success_rate")
            if pd.notna(sr) and (sr < 0 or sr > 1):
                collector.add("B", "warning", task, seed, "success_rate_outlier",
                              f"success_rate={sr} 超出 [0, 1]", "检查验收计算")

    for name, df in (("runs", t.get("runs_merged")), ("labels", t.get("labels_merged"))):
        if df is None:
            continue
        for _, row in df.iterrows():
            sr = row.get("success_rate")
            if pd.notna(sr) and (sr < 0 or sr > 1):
                collector.add("B", "warning", str(row.get("task", "")), str(row.get("seed", "")),
                              "success_rate_outlier", f"{name} 的 success_rate={sr} 超出 [0, 1]",
                              "检查标签写入")


# ---------------- C. 时间戳连续性 ----------------
def check_timestamps(collector: _Collector, t: dict[str, Any]) -> None:
    eval_df = t.get("eval_points")
    runs = t.get("runs_merged")
    if eval_df is None or not len(eval_df):
        return

    for (task, seed), g in eval_df.groupby(["task", "seed"]):
        task, seed = str(task), str(seed)
        # C1：按原始写入顺序检测单调性（先排序会掩盖乱序写入）
        raw = g.dropna(subset=["timesteps"])
        raw_steps = raw["timesteps"].to_numpy(dtype=float)
        if len(raw_steps) >= 2 and (raw_steps[1:] < raw_steps[:-1]).any():
            drops = int((raw_steps[1:] < raw_steps[:-1]).sum())
            collector.add("C", "critical", task, seed, "timesteps_not_monotonic",
                          f"timesteps 单调性被破坏（{drops} 处下降，疑似乱序写入）",
                          "检查采集端写入顺序，必要时修复数据")
        # C2/C3/C4 在排序后的序列上计算（间隔/起点/终点）
        gg = g.sort_values("timesteps").dropna(subset=["timesteps"])
        steps = gg["timesteps"].to_numpy(dtype=float)
        if len(steps) < 2:
            continue
        # C2：相邻点大跳变
        gaps = steps[1:] - steps[:-1]
        for gap in gaps[gaps > LARGE_GAP_STEPS]:
            collector.add("C", "warning", task, seed, "large_gap",
                          f"相邻 eval 点间隔 {gap:.0f} 步（>{LARGE_GAP_STEPS}，疑似数据丢失/训练中断）",
                          "确认训练日志完整性")
        # C3：起点异常
        if steps[0] > EARLY_EVAL_MAX_STEPS:
            collector.add("C", "info", task, seed, "missing_early_eval",
                          f"首个 eval 点 @{steps[0]:.0f} 步（>{EARLY_EVAL_MAX_STEPS}，前段无 eval）",
                          "可能是续训/BC 预热，确认符合预期")
        # C4：终点 vs total_steps
        if runs is not None and len(runs):
            hit = runs[(runs["task"] == task) & (runs["seed"] == seed)]
            if len(hit):
                ts_total = hit.iloc[0].get("total_steps")
                if pd.notna(ts_total) and ts_total > 0:
                    ratio = steps[-1] / ts_total
                    if abs(1 - ratio) > TOTAL_STEPS_TOL:
                        collector.add("C", "warning", task, seed, "incomplete_training",
                                      f"末 eval 点 {steps[-1]:.0f} 与 total_steps={ts_total:.0f} 偏差 "
                                      f"{abs(1-ratio)*100:.0f}%（>{TOTAL_STEPS_TOL*100:.0f}%）",
                                      "确认是否提前停止/续训（续训 run 以阶段总步数为口径）")


# ---------------- D. 重复数据检测 ----------------
def check_duplicates(collector: _Collector, t: dict[str, Any]) -> None:
    # D1：eval_points 同 (task,seed,timesteps) 重复
    eval_df = t.get("eval_points")
    if eval_df is not None and len(eval_df):
        dup = eval_df[eval_df.duplicated(subset=["task", "seed", "timesteps"], keep=False)]
        for (task, seed), g in dup.groupby(["task", "seed"]):
            n = len(g)
            collector.add("D", "critical", str(task), str(seed), "duplicate_eval_points",
                          f"同 timesteps 重复 {n} 行", "去重（保留首行）")
    # D2：tb_points 同 (task,seed,step) 重复
    tb_df = t.get("tb_points")
    if tb_df is not None and len(tb_df):
        step_col = "step" if "step" in tb_df.columns else "timesteps"
        dup = tb_df[tb_df.duplicated(subset=["task", "seed", step_col], keep=False)]
        for (task, seed), g in dup.groupby(["task", "seed"]):
            n = len(g)
            collector.add("D", "critical", str(task), str(seed), "duplicate_tb_points",
                          f"同 {step_col} 重复 {n} 行", "去重（保留首行）")
    # D3：snapshots 同 (task,seed,time) 重复
    snap_df = t.get("snapshots")
    if snap_df is not None and len(snap_df):
        time_col = "time" if "time" in snap_df.columns else "timesteps"
        dup = snap_df[snap_df.duplicated(subset=["task", "seed", time_col], keep=False)]
        for (task, seed), g in dup.groupby(["task", "seed"]):
            n = len(g)
            collector.add("D", "critical", str(task), str(seed), "duplicate_snapshots",
                          f"同 {time_col} 重复 {n} 行", "去重（保留首行）")
    # D4：runs 同 (task,seed) 重复（防御性）
    runs = t.get("runs_merged")
    if runs is not None and len(runs):
        dup = runs[runs.duplicated(subset=["task", "seed"], keep=False)]
        for (task, seed), g in dup.groupby(["task", "seed"]):
            collector.add("D", "critical", str(task), str(seed), "duplicate_runs",
                          f"runs.csv 中同 (task,seed) 出现 {len(g)} 行", "删除重复行")


# ---------------- E. 标签一致性（用原始文件对比，人工层不生效） ----------------
def check_labels(collector: _Collector, t: dict[str, Any]) -> None:
    raw_runs = t.get("runs")
    raw_labels = t.get("labels")
    reports = t.get("reports")
    manual = t.get("manual")
    merged_runs = t.get("runs_merged")
    merged_labels = t.get("labels_merged")

    # E1：三表 verdict 一致（都存在时）
    tables_map: list[tuple[str, pd.DataFrame]] = []
    if raw_runs is not None:
        tables_map.append(("runs", raw_runs))
    if raw_labels is not None:
        tables_map.append(("labels", raw_labels))
    if reports is not None and len(reports) and "verdict" in reports.columns:
        tables_map.append(("reports", reports))

    if len(tables_map) >= 2:
        # 收集所有 run 的三表 verdict
        verdicts: dict[tuple[str, str], dict[str, str]] = {}
        for tbl_name, df in tables_map:
            for _, row in df.iterrows():
                task, seed = str(row.get("task", "")), str(row.get("seed", ""))
                v = row.get("verdict")
                if isinstance(v, str) and v:  # 只比较非空 verdict
                    verdicts.setdefault((task, seed), {})[tbl_name] = v
        for (task, seed), vs in verdicts.items():
            vals = set(vs.values())
            if len(vals) > 1:
                collector.add("E", "critical", task, seed, "verdict_mismatch",
                              f"三表 verdict 不一致: {vs}", "以 manual_labels.csv 人工层为准修正")

    # E2：success_rate 与 verdict 一致
    for df, name in ((raw_runs, "runs"), (raw_labels, "labels")):
        if df is None:
            continue
        for _, row in df.iterrows():
            task, seed = str(row.get("task", "")), str(row.get("seed", ""))
            v = row.get("verdict"); sr = row.get("success_rate")
            if isinstance(v, str) and v == "pass" and (pd.isna(sr) or sr <= 0):
                collector.add("E", "warning", task, seed, "success_rate_verdict_mismatch",
                              f"{name}: verdict=pass 但 success_rate={sr}（应为 >0）",
                              "修正 success_rate")
            if isinstance(v, str) and v == "unknown" and pd.notna(sr):
                collector.add("E", "warning", task, seed, "success_rate_verdict_mismatch",
                              f"{name}: verdict=unknown 但 success_rate={sr}（应为空）",
                              "清空 success_rate")

    # E3：label_source 合理性
    for df, name in ((raw_labels, "labels"), (manual, "manual_labels")):
        if df is None or "label_source" not in df.columns:
            continue
        for _, row in df.iterrows():
            src = row.get("label_source")
            if isinstance(src, str) and src not in KNOWN_LABEL_SOURCES:
                collector.add("E", "info", str(row.get("task", "")), str(row.get("seed", "")),
                              "unknown_label_source",
                              f"{name}: label_source='{src}' 非已知类型",
                              "统一 label_source 取值")

    # E4：manual_labels 合并层正确性（人工层非空值应与合并输出一致）
    if manual is not None and merged_runs is not None and len(manual):
        for _, row in manual[manual["verdict"].notna()].iterrows():
            task, seed = str(row["task"]), str(row["seed"])
            hit = merged_runs[(merged_runs["task"] == task) & (merged_runs["seed"] == seed)]
            if len(hit) != 1:
                collector.add("E", "critical", task, seed, "merge_layer_mismatch",
                              f"manual_labels 有 {task}/{seed} 但合并 runs 无此行", "同步数据文件")
            elif hit.iloc[0].get("verdict") != row["verdict"]:
                collector.add("E", "critical", task, seed, "merge_layer_mismatch",
                              f"合并层 verdict={hit.iloc[0].get('verdict')} 与 manual={row['verdict']} 不一致",
                              "检查 data_utils 合并逻辑")

    # E5：completed 与 verdict 一致
    if raw_runs is not None:
        for _, row in raw_runs.iterrows():
            task, seed = str(row.get("task", "")), str(row.get("seed", ""))
            comp = row.get("completed"); v = row.get("verdict")
            if pd.notna(comp) and bool(comp) and not (isinstance(v, str) and v in ("pass", "fail")):
                collector.add("E", "warning", task, seed, "completed_verdict_mismatch",
                              f"completed=True 但 verdict={v if isinstance(v,str) else '未设置'}（应为 pass/fail）",
                              "验收后补标或改 completed")


# ---------------- F. 数据完整性（跨表关联） ----------------
def check_integrity(collector: _Collector, t: dict[str, Any]) -> None:
    runs = t.get("runs_merged")
    eval_df = t.get("eval_points")
    tb_df = t.get("tb_points")
    snap_df = t.get("snapshots")
    reports = t.get("reports")

    run_keys: set[tuple[str, str]] = set()
    if runs is not None and len(runs):
        run_keys = {(str(r["task"]), str(r["seed"])) for _, r in runs.iterrows()}

    def keys_of(df: pd.DataFrame | None) -> set[tuple[str, str]]:
        if df is None or not len(df):
            return set()
        return {(str(r["task"]), str(r["seed"])) for _, r in df.iterrows()}

    # F1：runs 每个 run 在 eval 至少 1 行
    if runs is not None and eval_df is not None and len(eval_df):
        eval_keys = keys_of(eval_df)
        for task, seed in sorted(run_keys):
            if (task, seed) not in eval_keys:
                collector.add("F", "warning", task, seed, "missing_eval_for_run",
                              "runs 中有该 run 但 eval_points 无任何点",
                              "刚启动可接受，否则补采")

    # F2：total_steps 与 eval 最大 timesteps 偏差 >20%
    if runs is not None and eval_df is not None and len(eval_df):
        for (task, seed), g in eval_df.groupby(["task", "seed"]):
            max_ts = g["timesteps"].max()
            hit = runs[(runs["task"] == str(task)) & (runs["seed"] == str(seed))]
            if len(hit):
                ts_total = hit.iloc[0].get("total_steps")
                if pd.notna(ts_total) and ts_total > 0:
                    ratio = max_ts / ts_total
                    if abs(1 - ratio) > TOTAL_STEPS_TOL:
                        collector.add("F", "warning", str(task), str(seed), "total_steps_mismatch",
                                      f"total_steps={ts_total:.0f} 与 eval 末点 {max_ts:.0f} 偏差 "
                                      f"{abs(1-ratio)*100:.0f}%（>{TOTAL_STEPS_TOL*100:.0f}%）",
                                      "确认续训口径（阶段 total_steps vs 累计步数）")

    # F3：reports 有数据的 run 必须在 eval 有数据
    if reports is not None and len(reports) and eval_df is not None and len(eval_df):
        eval_keys = keys_of(eval_df)
        for _, row in reports.iterrows():
            key = (str(row.get("task", "")), str(row.get("seed", "")))
            if key[0] and key not in eval_keys:
                collector.add("F", "warning", key[0], key[1], "report_without_eval",
                              "reports.csv 有验收行但 eval_points 无数据", "补充 eval 数据")

    # F4：孤儿数据（eval/tb/snap 中有但 runs 中没有）
    if runs is not None and len(runs):
        for df, label in ((eval_df, "eval_points"), (tb_df, "tb_points"), (snap_df, "snapshots")):
            for task, seed in sorted(keys_of(df) - run_keys):
                collector.add("F", "critical", task, seed, "orphan_data",
                              f"{label} 中存在孤儿 run（runs.csv 无此 run）",
                              "确认是否归档任务，归档则移入 archived 处理")


# ---------------- 评分与报告 ----------------
def _grade(issues: list[dict[str, Any]]) -> str:
    n = len(issues)
    nc = sum(1 for i in issues if i["severity"] == "critical")
    if n > 10 or nc > 2:
        return "D"
    if (6 <= n <= 10) or (1 <= nc <= 2):
        return "C"
    if 3 <= n <= 5:
        return "B"
    return "A"


def _grade_desc(grade: str) -> str:
    return {
        "A": "优秀：0-2个问题，无严重问题",
        "B": "良好：3-5个问题，无严重问题",
        "C": "一般：6-10个问题，或有1-2个严重问题",
        "D": "较差：>10个问题，或有>2个严重问题",
    }[grade]


_CATEGORY_NAMES = {
    "A": "缺失值", "B": "异常值", "C": "时间戳连续性",
    "D": "重复数据", "E": "标签一致性", "F": "数据完整性",
}


def render_markdown(today: str, issues: list[dict[str, Any]], grade: str) -> str:
    lines: list[str] = []
    lines.append(f"# 数据质量报告 {today}")
    lines.append("")
    lines.append(f"## 总体评分：{grade}（{_grade_desc(grade)}）")
    lines.append("")
    n_crit = sum(1 for i in issues if i["severity"] == "critical")
    lines.append(f"- 问题总数：{len(issues)}（其中严重 {n_crit}）")
    lines.append("")
    lines.append("## 问题统计")
    lines.append("")
    lines.append("| 类别 | 问题数 | 严重问题数 |")
    lines.append("|---|---|---|")
    total = len(issues)
    total_crit = n_crit
    for cat in ("A", "B", "C", "D", "E", "F"):
        sub = [i for i in issues if i["category"] == cat]
        sub_crit = sum(1 for i in sub if i["severity"] == "critical")
        lines.append(f"| {cat}.{_CATEGORY_NAMES[cat]} | {len(sub)} | {sub_crit} |")
    lines.append(f"| **总计** | **{total}** | **{total_crit}** |")
    lines.append("")
    lines.append("## 严重问题（必须处理）")
    lines.append("")
    crit = [i for i in issues if i["severity"] == "critical"]
    if crit:
        for i in crit:
            lines.append(f"- **{i['issue_id']}** [{i['category']}] {i['task']}/{i['seed']}："
                         f"{i['description']}（建议：{i['suggestion'] or '人工核实'}）")
    else:
        lines.append("- 无严重问题")
    lines.append("")
    lines.append("## 详细问题列表")
    lines.append("")
    for cat in ("A", "B", "C", "D", "E", "F"):
        sub = [i for i in issues if i["category"] == cat]
        lines.append(f"### {cat}.{_CATEGORY_NAMES[cat]}（{len(sub)}）")
        lines.append("")
        if sub:
            for i in sub:
                lines.append(f"- {i['issue_id']} | {i['task'] or '-'}/{i['seed'] or '-'} | "
                             f"[{i['severity']}] {i['issue_type']}：{i['description']}"
                             + (f" | 建议：{i['suggestion']}" if i["suggestion"] else ""))
        else:
            lines.append("- 无")
        lines.append("")
    lines.append("## 建议处理优先级")
    lines.append("")
    ordered = sorted(issues, key=lambda i: (0 if i["severity"] == "critical" else 1,
                                            0 if i["severity"] == "warning" else 2,
                                            i["issue_id"]))
    if ordered:
        for rank, i in enumerate(ordered, 1):
            lines.append(f"{rank}. [{i['severity']}] {i['issue_type']}（{i['task']}/{i['seed']}）："
                         f"{i['suggestion'] or '人工核实'}")
    else:
        lines.append("1. 无需处理")
    lines.append("")
    return "\n".join(lines)


def run_check(cfg: dict[str, Any], today: str, out_dir: pathlib.Path) -> list[dict[str, Any]]:
    """执行全部校验，返回 issues 列表。"""
    t = load_tables(cfg, out_dir)
    collector = _Collector()
    checks = (
        ("A", check_missing), ("B", check_outliers), ("C", check_timestamps),
        ("D", check_duplicates), ("E", check_labels), ("F", check_integrity),
    )
    for cat, fn in checks:
        try:
            fn(collector, t)
        except Exception as exc:  # noqa: BLE001 - 容错：单类失败不阻断
            collector.check_error(cat, exc)
    return collector.issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="go2w-quant 数据质量校验（6 大类 20+ 项只读校验）")
    parser.add_argument("--today", default=str(date.today()), help="报告日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="输出目录（默认 data/）")
    parser.add_argument("--threshold", default="info", choices=("info", "warning", "critical"),
                        help="报告中显示的最低严重程度（默认 info）")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 config.json）")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON 报告")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config) if args.config else load_config()
    except Exception as exc:  # noqa: BLE001
        print(f"[data_quality] 配置加载失败: {exc}")
        return 2

    out_dir = _out_dir(args.out)
    if args.threshold != "info":
        out_dir = out_dir  # 阈值只影响展示；CSV 始终全量
    try:
        issues = run_check(cfg, args.today, out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[data_quality] 校验失败: {exc}")
        return 2

    level_order = {"info": 0, "warning": 1, "critical": 2}
    min_level = level_order[args.threshold]
    shown = [i for i in issues if level_order[i["severity"]] >= min_level]

    grade = _grade(issues)
    md_text = render_markdown(args.today, shown, grade)

    md_path = out_dir / f"quality_report_{args.today}.md"
    csv_path = out_dir / f"quality_issues_{args.today}.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")
    pd.DataFrame(shown).to_csv(csv_path, index=False, encoding="utf-8-sig")
    if args.json:
        json_path = out_dir / f"quality_report_{args.today}.json"
        json_path.write_text(json.dumps({"today": args.today, "grade": grade, "issues": shown},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[data_quality] JSON: {json_path}")

    n_crit = sum(1 for i in issues if i["severity"] == "critical")
    print(f"[data_quality] 数据质量校验 {args.today}：评分 {grade}，问题 {len(issues)} 个（critical {n_crit}）")
    print(f"  报告: {md_path}")
    print(f"  CSV: {csv_path}")
    return 1 if n_crit else 0


if __name__ == "__main__":
    sys.exit(main())
