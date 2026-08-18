"""量化因子与风控规则引擎（纯函数，无 I/O）。

方法论映射（参考梁文锋/幻方量化的量化思路）：
- 多因子可计算：训练质量拆成 收敛/稳定/健康/验收/资源/成本 六类因子；
- 风控优先：先定义规则与分级（R0 正常 -> R1 观察 -> R2 警告 -> R3 严重），再给建议；
- 概率与分布思维：一律用窗口统计量（斜率、回撤、连续计数、占比），不靠单点拍脑袋；
- 建议制：只输出 continue / watch / stop / tune / resize，不自动干预训练。

本模块不读文件、不写文件，便于单元测试；I/O 由 quant.py 负责。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _Date, datetime as _DateTime
from typing import Any

import numpy as np
import pandas as pd

RISK_LEVELS = ("R0", "R1", "R2", "R3")
LEVEL_INDEX = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
DECISIONS = ("continue", "watch", "stop", "tune", "resize")


@dataclass
class RiskItem:
    """一条风控记录：级别 + 来源表 + 因子名 + 人类可读证据。"""

    level: str
    table: str
    factor: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "table": self.table,
            "factor": self.factor,
            "message": self.message,
        }


@dataclass
class RunResult:
    """单个 (task, seed) 的因子、风险与决策。"""

    task: str
    seed: str
    factors: dict[str, Any] = field(default_factory=dict)
    risks: list[RiskItem] = field(default_factory=list)
    level: str = "R0"
    decision: str = "continue"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "seed": self.seed,
            "factors": self.factors,
            "risks": [r.to_dict() for r in self.risks],
            "level": self.level,
            "decision": self.decision,
            "reasons": self.reasons,
        }


@dataclass
class QuantResult:
    """一次全量量化分析的完整结果。"""

    today: str
    generated_at: str
    coverage: dict[str, int]
    runs: list[RunResult]
    global_risks: list[RiskItem]
    global_level: str
    cost: dict[str, Any]
    resources: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "today": self.today,
            "generated_at": self.generated_at,
            "coverage": self.coverage,
            "runs": [r.to_dict() for r in self.runs],
            "global_risks": [r.to_dict() for r in self.global_risks],
            "global_level": self.global_level,
            "cost": self.cost,
            "resources": self.resources,
        }


def max_level(items: list[RiskItem]) -> str:
    """取一组风险项中的最高级别（无风险为 R0）。"""
    return max((i.level for i in items), key=LEVEL_INDEX.get, default="R0")


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def _filter(df: pd.DataFrame | None, task: str, seed: str) -> pd.DataFrame:
    """按 task/seed 过滤某张表；表缺失或为空时返回空表。"""
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df["task"] == task) & (df["seed"] == seed)]


def _max_cond_minutes(df: pd.DataFrame, col: str, threshold: float) -> float:
    """连续满足 值<threshold 的最长分钟数（按 time 列，单位秒）。"""
    times = [float(t) for t in df["time"]]
    vals = pd.to_numeric(df[col], errors="coerce").to_numpy()
    max_dur, start_t = 0.0, None
    for t, x in zip(times, vals):
        cond = (not pd.isna(x)) and float(x) < threshold
        if cond:
            if start_t is None:
                start_t = t
            max_dur = max(max_dur, (t - start_t) / 60.0)
        else:
            start_t = None
    return max_dur


def _max_stall_minutes(df: pd.DataFrame) -> float:
    """timesteps 连续不变的最长分钟数。"""
    times = [float(t) for t in df["time"]]
    vals = pd.to_numeric(df["timesteps"], errors="coerce").to_numpy()
    max_dur, start_t, prev, prev_t = 0.0, None, None, None
    for t, x in zip(times, vals):
        if (not pd.isna(x)) and prev is not None and x == prev:
            if start_t is None:
                start_t = prev_t
            max_dur = max(max_dur, (t - start_t) / 60.0)
        else:
            start_t = None
        prev, prev_t = x, t
    return max_dur


def _current_stall_minutes(df: pd.DataFrame) -> float:
    """窗口末端仍在持续的停滞段分钟数（末点步长已变化则 0）。"""
    if df is None or len(df) < 2:
        return 0.0
    d = df.sort_values("time").reset_index(drop=True)
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


def _spec_fall_times(snaps_df: pd.DataFrame) -> list[float]:
    """规格回退点的时间列表：timesteps 从 >100k 回退到 <10k（与实时新 run 判定一致）。"""
    if snaps_df is None or snaps_df.empty:
        return []
    d = snaps_df.sort_values("time").reset_index(drop=True)
    times = [float(t) for t in d["time"]]
    vals = pd.to_numeric(d["timesteps"], errors="coerce").to_numpy(dtype=float)
    out: list[float] = []
    prev: float | None = None
    for t, v in zip(times, vals):
        if pd.isna(v):
            prev = None
            continue
        if prev is not None and prev > 100000.0 and v < 10000.0:
            out.append(t)
        prev = v
    return out


def _section_times(evals_ts: list[float], snaps_df: pd.DataFrame) -> list[float]:
    """每个 eval 点的截面时间：首个（按 time 序）timesteps >= eval.timesteps 的快照时间，无则取最后快照时间。"""
    d = snaps_df.sort_values("time").reset_index(drop=True)
    times = [float(t) for t in d["time"]]
    vals = pd.to_numeric(d["timesteps"], errors="coerce").to_numpy(dtype=float)
    out: list[float] = []
    for ets in evals_ts:
        t = None
        for j in range(len(vals)):
            if not pd.isna(vals[j]) and vals[j] >= ets:
                t = times[j]
                break
        out.append(t if t is not None else times[-1])
    return out


def _neg_ratio_current(evals_df: pd.DataFrame, snaps_df: pd.DataFrame) -> float | None:
    """当前训练尝试（最后一次规格回退之后）的负奖励占比；无回退或无当前段时返回 None。

    与实时状态机同口径：重启后只统计新尝试的 eval 点；分段边界 = 首个截面时间
    >= 最后一次回退时间的 eval 点。
    """
    if evals_df is None or evals_df.empty or snaps_df is None or snaps_df.empty:
        return None
    falls = _spec_fall_times(snaps_df)
    if not falls:
        return None
    d = evals_df.sort_values("timesteps").reset_index(drop=True)
    rewards = pd.to_numeric(d["mean_reward"], errors="coerce")
    ts = pd.to_numeric(d["timesteps"], errors="coerce")
    valid = rewards.notna() & ts.notna()
    if not valid.any():
        return None
    secs = _section_times([float(x) for x in ts[valid]], snaps_df)
    boundary = next((k for k, t in enumerate(secs) if t >= falls[-1]), None)
    if boundary is None:
        return None
    seg = rewards[valid].iloc[boundary:]
    if len(seg) == 0:
        return None
    return round(float((seg < 0).mean()), 4)


def _valid_eval_timesteps(evals_df: pd.DataFrame) -> list[float]:
    """有效（mean_reward 非空）eval 点的 timesteps 列表（升序），用于 tb 因子按 eval 点对齐。"""
    if evals_df is None or evals_df.empty:
        return []
    d = evals_df.sort_values("timesteps").reset_index(drop=True)
    rew = pd.to_numeric(d["mean_reward"], errors="coerce")
    ts = pd.to_numeric(d["timesteps"], errors="coerce")
    return [float(x) for x in ts[rew.notna() & ts.notna()]]


def _neg_streak(series: pd.Series) -> int:
    """从尾部开始连续为负的个数。"""
    s = pd.to_numeric(series, errors="coerce").dropna()
    streak = 0
    for v in reversed(s.tolist()):
        if v < 0:
            streak += 1
        else:
            break
    return streak


def _value_loss_divergent(vl: pd.Series, window: int, rise_points: int, mult: float) -> bool:
    """value_loss 连续上升 rise_points 个点且末值远超前期均值 -> 发散。"""
    s = pd.to_numeric(vl, errors="coerce").dropna().reset_index(drop=True)
    if len(s) < rise_points + 1:
        return False
    streak = 1
    for i in range(len(s) - 1, 0, -1):
        if s.iloc[i] > s.iloc[i - 1]:
            streak += 1
        else:
            break
    if streak < rise_points:
        return False
    base = float(s.iloc[:window].mean()) if len(s) >= window else float(s.mean())
    return float(s.iloc[-1]) > base * mult


# --------------------------------------------------------------------------
# 因子层：六类因子
# --------------------------------------------------------------------------

def eval_factors(df: pd.DataFrame, slope_window: int = 5, recent_window: int = 5) -> dict[str, Any]:
    """收敛/稳定类因子（eval_points：每 50k 步评估）。

    因子字典（公式与口径）：
    - eval_points: 评估点总数
    - eval_last_timesteps: 最后一个评估点的 timesteps
    - eval_last_reward / eval_peak_reward: 末值与峰值 mean_reward
    - eval_drawdown: min(1, (peak-last)/peak)，裁剪到 [0,1]；峰值<=0 时取 0
    - reward_peak_ratio: 最终奖励/峰值奖励，可负可 >1（非峰值占比）
    - eval_slope_per_1e6: 最近 slope_window 点 mean_reward 对 timesteps 的
      最小二乘斜率 x1e6（非首末差分，抗单点噪声）；有效点 <2 或步长无变化时为 0
    - eval_std_recent: std_reward（评估内策略输出 std）最近 5 点均值，
      非 mean_reward 的 std（命名歧义，勿改）
    - eval_neg_ratio: 全部有效评估点中 mean_reward<0 的占比
    - eval_neg_ratio_recent: 最近 recent_window 点中 mean_reward<0 的占比
      （崩溃早期信号，先于回撤报警）
    """
    f: dict[str, Any] = {}
    if df is None or df.empty:
        return f
    d = df.sort_values("timesteps").reset_index(drop=True)
    rewards = pd.to_numeric(d["mean_reward"], errors="coerce")
    if rewards.notna().sum() == 0:
        return f
    peak = float(rewards.max())
    last = float(rewards.iloc[-1])
    f["eval_points"] = int(len(d))
    f["eval_last_timesteps"] = int(pd.to_numeric(d["timesteps"], errors="coerce").iloc[-1])
    f["eval_last_reward"] = round(last, 4)
    f["eval_peak_reward"] = round(peak, 4)
    if pd.notna(last):
        # 裁剪到 [0,1]：末值为负时 (peak-last)/peak 会超过 1（如 1.1884），
        # 回撤定义为不超过峰值的损失比例
        f["eval_drawdown"] = round(min(1.0, (peak - last) / peak), 4) if peak > 0 else 0.0
    f["reward_peak_ratio"] = round(last / peak, 4) if peak > 0 else None
    win = d.tail(max(slope_window, 2))
    xs = pd.to_numeric(win["timesteps"], errors="coerce")
    ys = pd.to_numeric(win["mean_reward"], errors="coerce")
    m = xs.notna() & ys.notna()
    if m.sum() >= 2 and float(xs[m].std(ddof=0)) > 0:
        slope = float(np.polyfit(xs[m], ys[m], 1)[0]) * 1e6
        f["eval_slope_per_1e6"] = round(slope, 4)
    else:
        f["eval_slope_per_1e6"] = 0.0
    stds = pd.to_numeric(d["std_reward"], errors="coerce").tail(5).dropna()
    if len(stds):
        f["eval_std_recent"] = round(float(stds.mean()), 4)
    valid = rewards.dropna()
    if len(valid):
        f["eval_neg_ratio"] = round(float((valid < 0).mean()), 4)
        recent = valid.tail(max(recent_window, 1))
        f["eval_neg_ratio_recent"] = round(float((recent < 0).mean()), 4)
    return f


def tb_factors(
    df: pd.DataFrame, vl_cfg: dict[str, Any], eval_timesteps: list[float] | None = None
) -> dict[str, Any]:
    """健康度因子（tb_points：TensorBoard rollout 指标）。

    因子字典（公式与口径）：
    - approx_kl_last: 过滤后（(0,1] 区间）最后一个有效 approx_kl；
      脏值（<=0 或 >1.0，如日志损坏的 122376）置空不入库
    - kl_divergent: 当前 tb 点 approx_kl 不在 (0,1]（含 NaN）即 True；
      传入 eval_timesteps 时按 eval 点对齐（取 step<=eval 的最后 tb 行原始值），
      与实时轮询口径一致
    - kl_divergent_streak: 尾部连续发散计数（按 eval 点对齐时以 eval 点计，
      否则以 tb 行计）
    - std_last: 最后一个 rollout 策略输出 std（与 eval_std_recent 不同源）
    - ev_neg_streak: 从尾部开始连续为负的 explained_variance 个数（非历史最长）
    - value_loss_divergent: value_loss 连续上升且远超前期均值的发散判定
    """
    f: dict[str, Any] = {}
    if df is None or df.empty:
        return f
    d = df.sort_values("step").reset_index(drop=True)
    # PPO approx_kl 合理区间为 (0, 1]；0/负值/超界（如日志损坏的 122376）视为脏值
    raw_kl = pd.to_numeric(d["approx_kl"], errors="coerce")
    kl = raw_kl.dropna()
    kl = kl[(kl > 0.0) & (kl <= 1.0)]
    if len(kl):
        f["approx_kl_last"] = round(float(kl.iloc[-1]), 4)
    if eval_timesteps:
        # 按 eval 点对齐：每个 eval 点取 step<=eval.timesteps 的最后 tb 行原始 kl
        # （NaN 也计发散，与实时状态机逐轮口径一致）
        steps_s = pd.to_numeric(d["step"], errors="coerce")
        mask = steps_s.notna()
        steps_arr = steps_s[mask].to_numpy(dtype=float)
        kls_arr = raw_kl[mask].to_numpy(dtype=float)
        divs: list[bool] = []
        for ets in sorted(float(x) for x in eval_timesteps):
            idx = int(np.searchsorted(steps_arr, ets, side="right")) - 1
            k = kls_arr[idx] if idx >= 0 else float("nan")
            divs.append(not (0.0 < k <= 1.0))
    else:
        divs = [bool(v) for v in (~((raw_kl > 0.0) & (raw_kl <= 1.0))).tolist()]
    f["kl_divergent"] = bool(divs[-1])
    streak = 0
    for v in reversed(divs):
        if v:
            streak += 1
        else:
            break
    f["kl_divergent_streak"] = streak
    std = pd.to_numeric(d["std"], errors="coerce").dropna()
    if len(std):
        f["std_last"] = round(float(std.iloc[-1]), 4)
    ev = pd.to_numeric(d["explained_variance"], errors="coerce").dropna()
    if len(ev):
        f["ev_neg_streak"] = _neg_streak(ev)
    vl = pd.to_numeric(d["value_loss"], errors="coerce").dropna()
    if len(vl):
        f["value_loss_divergent"] = _value_loss_divergent(
            vl, vl_cfg["window"], vl_cfg["rise_points"], vl_cfg["mult"]
        )
    return f


def acceptance_factors(df: pd.DataFrame) -> dict[str, Any]:
    """验收因子（reports：场景级验收指标）。"""
    f: dict[str, Any] = {}
    if df is None or df.empty:
        return f
    d = df.reset_index(drop=True)
    f["report_rows"] = int(len(d))
    verdicts = d["verdict"].dropna()
    if len(verdicts):
        f["verdict_fail_ratio"] = round(float((verdicts == "fail").mean()), 4)
    sr = pd.to_numeric(d["success_rate"], errors="coerce").dropna()
    if len(sr):
        f["success_rate_mean"] = round(float(sr.mean()), 4)
    md = pd.to_numeric(d["max_dev"], errors="coerce").dropna()
    if len(md):
        f["max_dev_max"] = round(float(md.max()), 4)
    mc = pd.to_numeric(d["min_clear"], errors="coerce").dropna()
    if len(mc):
        f["min_clear_min"] = round(float(mc.min()), 4)
    falls = pd.to_numeric(d["falls"], errors="coerce").dropna()
    if len(falls):
        f["falls_mean"] = round(float(falls.mean()), 4)
    f["nan_count"] = int(d["nan"].astype(bool).sum())
    return f


def snapshot_factors(df: pd.DataFrame, idle_cfg: dict[str, Any]) -> dict[str, Any]:
    """资源类因子（snapshots：30s 采样，资源列可能缺失）。"""
    f: dict[str, Any] = {}
    if df is None or df.empty:
        return f
    d = df.sort_values("time").reset_index(drop=True)
    f["snapshot_count"] = int(len(d))
    f["time_span_minutes"] = round(
        (float(d["time"].iloc[-1]) - float(d["time"].iloc[0])) / 60.0, 1
    )
    ts = pd.to_numeric(d["timesteps"], errors="coerce")
    if ts.notna().any():
        f["timesteps_growth"] = float(ts.iloc[-1] - ts.iloc[0])
        f["stall_minutes"] = round(_max_stall_minutes(d), 1)
        # current_stall_minutes: 当前连续停滞（恢复即归零），与 stall_minutes（max-so-far）并存
        f["current_stall_minutes"] = round(_current_stall_minutes(d), 1)
        # restart_count: 规格回退（timesteps 从 >100k 回退到 <10k）次数
        f["restart_count"] = len(_spec_fall_times(d))
    for col, key in (
        ("cpu_percent", "cpu_percent_max"),
        ("mem_percent", "mem_percent_max"),
        ("swap_percent", "swap_percent_max"),
    ):
        v = pd.to_numeric(d[col], errors="coerce").dropna()
        if len(v):
            f[key] = round(float(v.max()), 1)
    f["idle_minutes"] = round(
        _max_cond_minutes(d, "cpu_percent", idle_cfg["cpu_below"]), 1
    )
    return f


def run_factors(
    task: str, seed: str, tables: dict[str, pd.DataFrame], cfg: dict[str, Any]
) -> dict[str, Any]:
    """汇总单个 (task, seed) 的全部因子（不含 task/seed 本身）。"""
    f: dict[str, Any] = {}
    evals_df = _filter(tables.get("eval_points"), task, seed)
    tb_df = _filter(tables.get("tb_points"), task, seed)
    snaps_df = _filter(tables.get("snapshots"), task, seed)
    f.update(eval_factors(
        evals_df,
        slope_window=int(cfg["risk"]["eval_slope"]["window"]),
        recent_window=int(cfg["risk"]["neg_ratio"]["recent_window"]),
    ))
    # kl_divergent 按 eval 点对齐（与实时轮询口径一致）：每个有效 eval 点取
    # step<=eval.timesteps 的最后 tb 行原始 approx_kl 判定发散
    f.update(tb_factors(tb_df, cfg["risk"]["value_loss"],
                        eval_timesteps=_valid_eval_timesteps(evals_df)))
    f.update(acceptance_factors(_filter(tables.get("reports"), task, seed)))
    f.update(snapshot_factors(snaps_df, cfg["risk"]["resources"]["idle"]))
    # neg_ratio_current: 当前训练尝试（最后一次规格回退之后）的负奖励占比；
    # 无回退/无快照时退化为全部尝试口径（eval_neg_ratio）；无任何因子数据时跳过
    if f:
        cur_ratio = _neg_ratio_current(evals_df, snaps_df)
        f["neg_ratio_current"] = cur_ratio if cur_ratio is not None else f.get("eval_neg_ratio")
    runs = tables.get("runs")
    if runs is not None and len(runs) and f:
        row = runs[(runs["task"] == task) & (runs["seed"] == seed)]
        if len(row):
            f["completed"] = bool(row["completed"].astype(bool).iloc[0])
            total = pd.to_numeric(row["total_steps"], errors="coerce").dropna()
            if len(total) and f.get("eval_last_timesteps") is not None:
                f["progress_ratio"] = round(f["eval_last_timesteps"] / float(total.iloc[0]), 4)
    return f


# --------------------------------------------------------------------------
# 风控层：规则 + 分级
# --------------------------------------------------------------------------

def run_risk_items(f: dict[str, Any], cfg: dict[str, Any]) -> list[RiskItem]:
    """按规则把单个 run 的因子映射为风险项（无风险则返回空表）。"""
    r = cfg["risk"]
    items: list[RiskItem] = []

    def add(level: str, table: str, factor: str, message: str) -> None:
        items.append(RiskItem(level, table, factor, message))

    # 回撤：峰值回撤 15% 观察，30% 警告
    dd = f.get("eval_drawdown", 0.0)
    if dd > r["drawdown"]["stop"]:
        add("R2", "eval_points", "drawdown",
            f"评估奖励较峰值回撤 {dd:.1%}（阈值 {r['drawdown']['stop']:.0%}）")
    elif dd > r["drawdown"]["watch"]:
        add("R1", "eval_points", "drawdown",
            f"评估奖励较峰值回撤 {dd:.1%}（阈值 {r['drawdown']['watch']:.0%}）")

    # 停滞：进度超 60% 而奖励不足峰值 60%
    pr, rpr = f.get("progress_ratio"), f.get("reward_peak_ratio")
    if pr is not None and rpr is not None and rpr < r["stagnation"]["reward_ratio"] \
            and pr >= r["stagnation"]["progress"]:
        add("R2", "eval_points", "stagnation",
            f"训练进度 {pr:.0%} 但奖励仅为峰值的 {rpr:.0%}"
            f"（<{r['stagnation']['reward_ratio']:.0%}），疑似停滞")

    # 负奖励占比：崩溃早期信号，先于回撤报警（recent>50% 严重，整体>30% 观察）
    neg_recent = f.get("eval_neg_ratio_recent")
    if neg_recent is not None and neg_recent > r["neg_ratio"]["severe"]:
        add("R2", "eval_points", "neg_ratio",
            f"近期评估奖励负值占比 {neg_recent:.0%}（>{r['neg_ratio']['severe']:.0%}），疑似策略崩溃")
    elif f.get("eval_neg_ratio") is not None and f["eval_neg_ratio"] > r["neg_ratio"]["watch"]:
        add("R1", "eval_points", "neg_ratio",
            f"评估奖励负值占比 {f['eval_neg_ratio']:.0%}（>{r['neg_ratio']['watch']:.0%}）")

    # 当前训练尝试（重启后）负奖励占比：与 eval_neg_ratio 同阈值，重启感知
    neg_cur = f.get("neg_ratio_current")
    if neg_cur is not None:
        if neg_cur > r["neg_ratio"]["severe"]:
            add("R2", "eval_points", "neg_ratio_current",
                f"当前训练尝试负奖励占比 {neg_cur:.0%}（>{r['neg_ratio']['severe']:.0%}），疑似崩溃")
        elif neg_cur > r["neg_ratio"]["watch"]:
            add("R1", "eval_points", "neg_ratio_current",
                f"当前训练尝试负奖励占比 {neg_cur:.0%}（>{r['neg_ratio']['watch']:.0%}）")

    # 评估内策略输出 std 塌缩（与 tb_points std_last 不同源；评估点数不足 5 不判）
    eval_pts = f.get("eval_points", 0)
    esr = f.get("eval_std_recent")
    if eval_pts >= 5 and esr is not None and esr < r["std_reward"]["collapse"]:
        add("R1", "eval_points", "std_reward_collapse",
            f"策略输出标准差 {esr}（<{r['std_reward']['collapse']}），疑似确定性退化")

    # 策略输出标准差：塌缩观察，发散警告
    std_last = f.get("std_last")
    if std_last is not None:
        if std_last > r["std"]["explode"]:
            add("R2", "tb_points", "std", f"策略输出标准差 {std_last}（>{r['std']['explode']}），疑似发散")
        elif std_last < r["std"]["collapse"]:
            add("R1", "tb_points", "std", f"策略输出标准差 {std_last}（<{r['std']['collapse']}），疑似塌缩")

    if f.get("value_loss_divergent"):
        add("R2", "tb_points", "value_loss", "value_loss 连续上升且远超前期均值，疑似发散")

    kl = f.get("approx_kl_last")
    if kl is not None:
        if kl > r["approx_kl"]["warn"]:
            add("R2", "tb_points", "approx_kl", f"approx_kl={kl}（>{r['approx_kl']['warn']}）")
        elif kl > r["approx_kl"]["watch"]:
            add("R1", "tb_points", "approx_kl", f"approx_kl={kl}（>{r['approx_kl']['watch']}）")

    # KL 发散：当前 tb 点 approx_kl 不在 (0,1]（含 NaN），按 eval 点连续计数
    kl_streak = f.get("kl_divergent_streak", 0)
    if kl_streak >= r["kl_divergent"]["r3"]:
        add("R3", "tb_points", "kl_divergent",
            f"approx_kl 持续 {kl_streak} 个 eval 点超界（>={r['kl_divergent']['r3']}），疑似数据损坏/发散")
    elif kl_streak >= r["kl_divergent"]["r2"]:
        add("R2", "tb_points", "kl_divergent",
            f"approx_kl 持续 {kl_streak} 个 eval 点超界（>={r['kl_divergent']['r2']}）")

    if f.get("ev_neg_streak", 0) >= r["explained_variance"]["neg_points"]:
        add("R2", "tb_points", "explained_variance",
            f"explained_variance 连续 {f['ev_neg_streak']} 点为负"
            f"（>={r['explained_variance']['neg_points']}）")

    # 验收：NaN 计数与物理指标越界
    nan_count = f.get("nan_count", 0)
    if nan_count >= r["nan"]["severe"]:
        add("R3", "reports", "nan", f"验收报告出现 {nan_count} 次 NaN（>={r['nan']['severe']}）")
    elif nan_count >= r["nan"]["warn"]:
        add("R2", "reports", "nan", f"验收报告出现 {nan_count} 次 NaN")

    if f.get("verdict_fail_ratio") == 1.0:
        add("R1", "reports", "acceptance", "全部验收场景 verdict=fail，需人工复核")
    mdev = f.get("max_dev_max")
    if mdev is not None and mdev > r["acceptance"]["max_dev"]:
        add("R1", "reports", "acceptance",
            f"最大俯仰偏差 {mdev} rad（>{r['acceptance']['max_dev']}）")
    mclear = f.get("min_clear_min")
    if mclear is not None and mclear < r["acceptance"]["min_clear"]:
        add("R1", "reports", "acceptance",
            f"最小离地高度 {mclear} m（<{r['acceptance']['min_clear']}）")

    # 资源：Swap/内存/CPU 过载、timesteps 停滞、空闲疑似卡死
    swap = f.get("swap_percent_max")
    if swap is not None:
        if swap > r["resources"]["swap"]["warn"]:
            add("R2", "snapshots", "swap",
                f"Swap 使用率峰值 {swap:.0f}%（>{r['resources']['swap']['warn']:.0f}%）")
        elif swap > r["resources"]["swap"]["watch"]:
            add("R1", "snapshots", "swap",
                f"Swap 使用率峰值 {swap:.0f}%（>{r['resources']['swap']['watch']:.0f}%）")
    mem = f.get("mem_percent_max")
    if mem is not None and mem > r["resources"]["mem_warn"]:
        add("R2", "snapshots", "mem",
            f"内存使用率峰值 {mem:.0f}%（>{r['resources']['mem_warn']:.0f}%）")
    cpu = f.get("cpu_percent_max")
    if cpu is not None and cpu > r["resources"]["cpu_warn"]:
        add("R1", "snapshots", "cpu",
            f"CPU 使用率峰值 {cpu:.0f}%（>{r['resources']['cpu_warn']:.0f}%）")

    stall = f.get("stall_minutes", 0.0)
    if not f.get("completed") and stall >= r["stall_minutes"]["warn"]:
        add("R2", "snapshots", "stall",
            f"timesteps 连续 {stall:.0f} 分钟无增长（>={r['stall_minutes']['warn']}）")
    elif not f.get("completed") and stall >= r["stall_minutes"]["watch"]:
        add("R1", "snapshots", "stall",
            f"timesteps 连续 {stall:.0f} 分钟无增长（>={r['stall_minutes']['watch']}）")

    # 当前连续停滞（恢复即归零）：与 stall（max-so-far）并存，同阈值，仅未完成 run
    cur_stall = f.get("current_stall_minutes", 0.0)
    if not f.get("completed") and cur_stall >= r["stall_minutes"]["warn"]:
        add("R2", "snapshots", "stall_current",
            f"当前连续停滞 {cur_stall:.0f} 分钟（>={r['stall_minutes']['warn']}）")
    elif not f.get("completed") and cur_stall >= r["stall_minutes"]["watch"]:
        add("R1", "snapshots", "stall_current",
            f"当前连续停滞 {cur_stall:.0f} 分钟（>={r['stall_minutes']['watch']}）")

    # 训练重启：规格回退（timesteps 从 >100k 回退到 <10k）次数
    rc = f.get("restart_count", 0)
    if rc >= r["restart_count"]["r3"]:
        add("R3", "snapshots", "restart",
            f"检测到 {rc} 次训练重启（>={r['restart_count']['r3']}），训练反复崩溃")
    elif rc >= r["restart_count"]["r2"]:
        add("R2", "snapshots", "restart",
            f"检测到 {rc} 次训练重启（>={r['restart_count']['r2']}）")

    idle = f.get("idle_minutes", 0.0)
    if not f.get("completed") and idle >= r["resources"]["idle"]["minutes"]:
        add("R2", "snapshots", "idle",
            f"CPU<{r['resources']['idle']['cpu_below']:.0f}% 持续 {idle:.0f} 分钟"
            f"（>={r['resources']['idle']['minutes']}）且训练未完成，疑似卡死")
    return items


# --------------------------------------------------------------------------
# 决策层：建议制矩阵
# --------------------------------------------------------------------------

def decide(f: dict[str, Any], risks: list[RiskItem], cfg: dict[str, Any]) -> tuple[str, list[str]]:
    """由风险项给出建议：continue / watch / stop / tune / resize。

    矩阵：R3 -> stop；R2 -> 按触发因子细分（回撤/停滞/NaN/负奖励崩溃/反复重启 早停，
    健康度/KL 发散 调参，资源/当前停滞 重调度）；R1 -> watch；R0 -> continue。
    """
    level = max_level(risks)
    msgs = [i.message for i in risks]
    if level == "R3":
        return "stop", msgs
    if level == "R2":
        if f.get("eval_drawdown", 0.0) > cfg["risk"]["drawdown"]["stop"]:
            return "stop", msgs
        factors = {i.factor for i in risks if i.level == "R2"}
        if factors & {"value_loss", "approx_kl", "explained_variance", "kl_divergent"}:
            return "tune", msgs
        if factors & {"swap", "mem", "cpu", "stall", "idle", "stall_current"}:
            return "resize", msgs
        if factors & {"stagnation", "nan", "neg_ratio", "neg_ratio_current", "restart"}:
            return "stop", msgs
        return "watch", msgs
    if level == "R1":
        return "watch", msgs
    return "continue", msgs


# --------------------------------------------------------------------------
# 成本与全局资源
# --------------------------------------------------------------------------

def cost_factors(costs: pd.DataFrame | None, today: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """成本因子：日/周/月成本、预算占比、token 缓存率。"""
    if costs is None or costs.empty:
        return {"present": False}
    d = costs.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["cost_yuan"] = pd.to_numeric(d["cost_yuan"], errors="coerce").fillna(0.0)
    today_ts = pd.Timestamp(today)

    def span_sum(days: int) -> float:
        lo = today_ts - pd.Timedelta(days=days - 1)
        m = d[(d["date"] >= lo) & (d["date"] <= today_ts)]
        return float(m["cost_yuan"].sum())

    inp = float(pd.to_numeric(d["input_tokens"], errors="coerce").sum())
    cached = float(pd.to_numeric(d["cached_tokens"], errors="coerce").sum())
    cache_rate = cached / (inp + cached) if (inp + cached) > 0 else None
    b = cfg["risk"]["budget"]
    return {
        "present": True,
        "daily_cost": round(span_sum(1), 2),
        "weekly_cost": round(span_sum(7), 2),
        "monthly_cost": round(span_sum(30), 2),
        "total_cost": round(float(d["cost_yuan"].sum()), 2),
        "daily_budget": b["daily"],
        "weekly_budget": b["weekly"],
        "monthly_budget": b["monthly"],
        "cache_rate": round(cache_rate, 4) if cache_rate is not None else None,
    }


def cost_risk_items(cost: dict[str, Any], cfg: dict[str, Any]) -> list[RiskItem]:
    """成本风控：预算 80% 观察、100% 警告、150% 严重；缓存率过低提示。"""
    if not cost.get("present"):
        return []
    b = cfg["risk"]["budget"]
    items: list[RiskItem] = []
    for key, label in (("daily", "今日"), ("weekly", "本周"), ("monthly", "本月")):
        budget = b[key]
        if budget <= 0:
            continue
        ratio = cost[f"{key}_cost"] / budget
        if ratio >= b["severe_ratio"]:
            items.append(RiskItem("R3", "costs", f"cost_{key}",
                                  f"{label}成本 {cost[f'{key}_cost']:.2f} 元，达预算 {ratio:.0%}"
                                  f"（>={b['severe_ratio']:.0%}）"))
        elif ratio >= 1.0:
            items.append(RiskItem("R2", "costs", f"cost_{key}",
                                  f"{label}成本 {cost[f'{key}_cost']:.2f} 元，超预算 {ratio:.0%}"))
        elif ratio >= b["watch_ratio"]:
            items.append(RiskItem("R1", "costs", f"cost_{key}",
                                  f"{label}成本 {cost[f'{key}_cost']:.2f} 元，达预算 {ratio:.0%}"
                                  f"（>={b['watch_ratio']:.0%}）"))
    cr = cost.get("cache_rate")
    if cr is not None and cr < cfg["risk"]["cache_rate_watch"]:
        items.append(RiskItem("R1", "costs", "cache_rate",
                              f"token 缓存率 {cr:.0%}（<{cfg['risk']['cache_rate_watch']:.0%}），"
                              "建议检查上下文缓存策略"))
    return items


def resource_summary(snaps: pd.DataFrame | None, cfg: dict[str, Any]) -> dict[str, Any]:
    """整机资源总览（跨所有 run 的采样）。"""
    if snaps is None or snaps.empty:
        return {"present": False}
    d = snaps.copy()
    out: dict[str, Any] = {"present": True, "sampled_rows": int(len(d))}
    cpu = pd.to_numeric(d["cpu_percent"], errors="coerce").dropna()
    if len(cpu):
        out["cpu_mean"] = round(float(cpu.mean()), 1)
        out["cpu_max"] = round(float(cpu.max()), 1)
    mem = pd.to_numeric(d["mem_percent"], errors="coerce").dropna()
    if len(mem):
        out["mem_mean"] = round(float(mem.mean()), 1)
        out["mem_max"] = round(float(mem.max()), 1)
    swap = pd.to_numeric(d["swap_percent"], errors="coerce").dropna()
    if len(swap):
        out["swap_max"] = round(float(swap.max()), 1)
    load1 = pd.to_numeric(d["load1"], errors="coerce").dropna()
    if len(load1):
        out["load1_max"] = round(float(load1.max()), 1)
    out["idle_minutes"] = round(
        _max_cond_minutes(d, "cpu_percent", cfg["risk"]["resources"]["idle"]["cpu_below"]), 1
    )
    return out


# --------------------------------------------------------------------------
# 汇总入口
# --------------------------------------------------------------------------

def compute_all(
    cfg: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    today: str | None = None,
) -> QuantResult:
    """全量量化分析：逐 run 因子+风控+决策，外加成本与全局资源。"""
    today = today or _Date.today().isoformat()
    coverage = {name: int(len(df)) for name, df in tables.items()}

    runs_df = tables.get("runs")
    if runs_df is not None and len(runs_df):
        pairs = list(zip(runs_df["task"], runs_df["seed"]))
    else:
        seen: set[tuple[str, str]] = set()
        for name in ("eval_points", "tb_points", "reports", "snapshots"):
            df = tables.get(name)
            if df is not None and len(df):
                seen.update(zip(df["task"], df["seed"]))
        pairs = sorted(seen)

    runs: list[RunResult] = []
    for task, seed in pairs:
        f = run_factors(task, seed, tables, cfg)
        risks = run_risk_items(f, cfg)
        if not f:
            decision, reasons = "continue", ["暂无可用数据（未开始或已归档）"]
        else:
            decision, reasons = decide(f, risks, cfg)
        runs.append(RunResult(
            task=task, seed=seed, factors=f, risks=risks,
            level=max_level(risks), decision=decision, reasons=reasons,
        ))
    runs.sort(key=lambda r: (-LEVEL_INDEX[r.level], r.task, r.seed))

    cost = cost_factors(tables.get("costs"), today, cfg)
    global_risks = cost_risk_items(cost, cfg)
    resources = resource_summary(tables.get("snapshots"), cfg)
    return QuantResult(
        today=today,
        generated_at=_DateTime.now().isoformat(timespec="seconds"),
        coverage=coverage,
        runs=runs,
        global_risks=global_risks,
        global_level=max_level(global_risks),
        cost=cost,
        resources=resources,
    )