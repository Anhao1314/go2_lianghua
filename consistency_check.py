"""consistency_check.py - 回测-实盘一致性校验（P0）。

对同一 run 逐 eval 点推进，在同一时间截面上并行计算：
  - 离线路径: factors.run_factors()（历史数据截断视角，基准）
  - 实时路径: RealtimeMonitor.compute_factors()（webpanel API 因子适配器）
输出每截面关键因子（drawdown / 负奖励占比 / 停滞 / KL / 重启等）的
offline/online/abs_diff/passed 与控制台摘要。

原则：
  - 离线是基准；P0 修复后 factors.py 与 realtime_monitor.py 输出同一定义，
    本模块用于回归校验（发现不一致即回退门槛）。
  - 只读 data/datasets，输出 data/modeling/consistency_check_YYYY-MM-DD.csv（utf-8-sig）。
  - 确定性：同一输入 -> 同一输出（假时钟回放，无真实网络）。
"""

from __future__ import annotations

import argparse
import contextlib
import types
from datetime import date
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

import factors
import realtime_monitor
from collector import PROJECT_ROOT, load_config
from data_utils import load_runs_merged

# webpanel API 保留的最近 eval reward 数量（history 字段）
HISTORY_SIZE = 20

# 对比因子与容差：mode=abs 绝对差 / rel 相对差 / exact 完全一致
COMPARE_SPECS: dict[str, dict[str, Any]] = {
    "eval_drawdown": {"mode": "abs", "tolerance": 0.005},
    "eval_neg_ratio_recent": {"mode": "abs", "tolerance": 0.005},
    "eval_neg_ratio": {"mode": "abs", "tolerance": 0.005},
    "neg_ratio_current": {"mode": "abs", "tolerance": 0.005},
    "stall_minutes": {"mode": "abs", "tolerance": 1.0},
    "current_stall_minutes": {"mode": "abs", "tolerance": 1.0},
    "restart_count": {"mode": "exact", "tolerance": 0.0},
    "approx_kl_last": {"mode": "exact", "tolerance": 0.0},
    "kl_divergent": {"mode": "exact", "tolerance": 0.0},
    "kl_divergent_streak": {"mode": "exact", "tolerance": 0.0},
    "eval_std_recent": {"mode": "abs", "tolerance": 0.01},
    "eval_slope_per_1e6": {"mode": "rel", "tolerance": 0.05},
}

# 实时路径结构上不可用的因子（API 无 std_reward / 带步长的奖励历史），计为 N/A
NA_ONLINE_FACTORS = {"eval_std_recent", "eval_slope_per_1e6"}


class _FakeClock:
    """假时钟：回放时由调用方设置 now，替代 time.time()，保证确定性。"""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        pass


@contextlib.contextmanager
def _patch_monitor_clock(clock: _FakeClock) -> Iterator[None]:
    orig = realtime_monitor.time
    realtime_monitor.time = clock
    try:
        yield
    finally:
        realtime_monitor.time = orig


class OnlineSimulator:
    """实时路径回放器：假时钟 + RealtimeMonitor 状态机 + compute_factors。

    快照粒度轮询只推进停滞/步长状态（eval_reward=None，不更新奖励计数）；
    eval 点轮询更新峰值/负奖励计数并计算实时因子。
    """

    def __init__(self, task: str, seed_id: str, cfg: dict[str, Any]) -> None:
        self.task = task
        self.seed_id = seed_id
        self.key = f"{task}/{seed_id}"
        self.fake = _FakeClock()
        self._ctx = _patch_monitor_clock(self.fake)
        self._ctx.__enter__()
        self.monitor = realtime_monitor.RealtimeMonitor(cfg)

    def close(self) -> None:
        self._ctx.__exit__(None, None, None)

    def __enter__(self) -> "OnlineSimulator":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def poll_snapshot(self, timesteps: float, t: float) -> None:
        """快照粒度轮询：只推进停滞状态（与真实监控连续轮询等价）。"""
        self.fake.now = float(t)
        self.monitor.update_state(self.task, self.seed_id, {
            "key": self.key,
            "timesteps": float(timesteps),
            "eval_reward": None,
            "alive": True,
            "completed": False,
        })

    def poll_eval(self, seed: dict[str, Any], resources: dict[str, Any], t: float) -> dict[str, Any]:
        """eval 点轮询：更新奖励状态并计算实时因子字典。"""
        self.fake.now = float(t)
        self.monitor.update_state(self.task, self.seed_id, seed)
        st = self.monitor.state[(self.task, self.seed_id)]
        # 与生产 poll_once 对齐：update_state -> update_kl_state -> compute_factors
        self.monitor.update_kl_state(st, seed.get("tb_kl"))
        return self.monitor.compute_factors(self.task, seed, resources, st)


def build_eval_seed(
    task: str,
    seed_id: str,
    timesteps: float,
    reward: float,
    history: list[float],
    tb_kl: Any,
    tb_std: Any,
) -> dict[str, Any]:
    """把离线 eval 截面构造成 webpanel API seed 对象。"""
    return {
        "key": f"{task}/{seed_id}",
        "timesteps": float(timesteps),
        "eval_reward": float(reward),
        "tb_reward": None,
        "ep_len": None,
        "speed": None,
        "eta_seconds": None,
        "completed": False,
        "alive": True,
        "stale": False,
        "nan": False,
        "history": history,
        "tb_std": tb_std,
        "tb_value_loss": None,
        "tb_kl": tb_kl,
        "tb_curve": [],
    }


def _load_tables(cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    ds = PROJECT_ROOT / str(cfg.get("output_dir", "data/datasets"))
    return {
        "eval_points": pd.read_csv(ds / "eval_points.csv"),
        "tb_points": pd.read_csv(ds / "tb_points.csv"),
        "snapshots": pd.read_csv(ds / "snapshots.csv"),
        "runs": load_runs_merged(cfg),
    }


def _run_frame(df: pd.DataFrame, task: str, seed: str, by: str) -> pd.DataFrame:
    d = df[(df["task"] == task) & (df["seed"] == seed)].copy()
    d[by] = pd.to_numeric(d[by], errors="coerce")
    return d.dropna(subset=[by]).sort_values(by).reset_index(drop=True)


def build_sections(evals: pd.DataFrame, snaps: pd.DataFrame) -> list[dict[str, float]]:
    """逐 eval 点生成截面：T_i = 首个 timesteps >= eval_i.timesteps 的快照时间（无则取最后快照时间）。"""
    sections: list[dict[str, float]] = []
    snap_times = [float(x) for x in snaps["time"]]
    snap_ts = pd.to_numeric(snaps["timesteps"], errors="coerce").to_numpy(dtype=float)
    for ts in evals["timesteps"]:
        t_i = None
        for j in range(len(snap_ts)):
            if not pd.isna(snap_ts[j]) and snap_ts[j] >= float(ts):
                t_i = snap_times[j]
                break
        if t_i is None:
            t_i = snap_times[-1]
        sections.append({"timesteps": float(ts), "section_time": float(t_i)})
    return sections


def offline_factors(
    task: str,
    seed: str,
    evals_i: pd.DataFrame,
    tbs_i: pd.DataFrame,
    snaps_i: pd.DataFrame,
    runs: pd.DataFrame,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """离线路径：run_factors 兼容输入（reports 恒为空，验收因子在线不可见）。"""
    tables = {
        "eval_points": evals_i,
        "tb_points": tbs_i,
        "snapshots": snaps_i,
        "reports": pd.DataFrame(),
        "runs": runs,
    }
    return factors.run_factors(task, seed, tables, cfg)


def compare_value(off: Any, on: Any, mode: str, tolerance: float) -> tuple[bool, Any]:
    """返回 (passed, diff)。exact 模式 diff 为绝对差，rel 模式 diff 为相对差。"""
    if off is None and on is None:
        return True, 0.0
    if off is None or on is None:
        return False, None
    off = float(off)
    on = float(on)
    if mode == "exact":
        diff = abs(off - on)
        return bool(diff == 0.0), diff
    if mode == "rel":
        diff = abs(off - on) / max(abs(off), abs(on), 1e-9)
        return bool(diff < tolerance), diff
    diff = abs(off - on)
    return bool(diff < tolerance), diff


def compare_factors(off: dict[str, Any], on: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """逐因子对比：offline / online / abs_diff / passed（"N/A" 表示实时结构性不可用）。"""
    result: dict[str, dict[str, Any]] = {}
    for factor, spec in COMPARE_SPECS.items():
        ov = off.get(factor)
        nv = on.get(factor)
        if factor in NA_ONLINE_FACTORS and nv is None:
            result[factor] = {"offline": ov, "online": None, "abs_diff": None, "passed": "N/A"}
            continue
        passed, diff = compare_value(ov, nv, spec["mode"], spec["tolerance"])
        result[factor] = {"offline": ov, "online": nv, "abs_diff": diff, "passed": passed}
    return result


def _restart_count(snaps: pd.DataFrame) -> int:
    """快照流中规格回退（timesteps 从 >100k 回退到 <10k）次数（与 factors/实时状态机同口径）。"""
    vals = pd.to_numeric(snaps["timesteps"], errors="coerce").to_numpy(dtype=float)
    cnt = 0
    prev = None
    for v in vals:
        if pd.isna(v):
            prev = None
            continue
        if prev is not None and prev > 100000 and v < 10000:
            cnt += 1
        prev = v
    return cnt


def _current_stall_minutes(snaps: pd.DataFrame) -> float:
    """窗口末端仍在持续的停滞段时长（分钟）；末端步长已变化则返回 0。

    注意：factors._max_stall_minutes 返回窗口内最大停滞（max-so-far，持久），
    本函数为检查器本地实现的"当前停滞"口径，仅用于语义差异判定，不修改 factors.py。
    """
    if snaps is None or snaps.empty or len(snaps) < 2:
        return 0.0
    d = snaps.sort_values("time").reset_index(drop=True)
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


def _resources_from_snapshot(row: pd.Series) -> dict[str, Any]:
    return {
        "cpu_percent": row.get("cpu_percent"),
        "mem_percent": row.get("mem_percent"),
        "swap_percent": row.get("swap_percent"),
    }


def _new_factor_stats() -> dict[str, Any]:
    return {
        "passed": 0,
        "failed": 0,
        "na": 0,
        "max_diff": None,
        "max_diff_timesteps": None,
    }


def run_check(
    task: str,
    seed: str,
    cfg: dict[str, Any],
    out_path: Path,
    verbose: bool = True,
    tables: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """执行一致性校验：返回摘要 dict，并把逐截面对比写入 out_path（utf-8-sig）。"""
    tables = tables if tables is not None else _load_tables(cfg)
    evals = _run_frame(tables["eval_points"], task, seed, by="timesteps")
    evals = evals[pd.to_numeric(evals["mean_reward"], errors="coerce").notna()].reset_index(drop=True)
    if evals.empty:
        raise ValueError(f"run {task}/{seed} 无有效 eval 点")
    tbs = _run_frame(tables["tb_points"], task, seed, by="step")
    snaps = _run_frame(tables["snapshots"], task, seed, by="time")
    if snaps.empty:
        raise ValueError(f"run {task}/{seed} 无快照数据，无法对齐时间轴")
    runs = tables["runs"]
    sections = build_sections(evals, snaps)

    rows: list[dict[str, Any]] = []
    factor_stats: dict[str, dict[str, Any]] = {f: _new_factor_stats() for f in COMPARE_SPECS}
    failed_sections: list[dict[str, Any]] = []

    with OnlineSimulator(task, seed, cfg) as sim:
        snap_ptr = 0
        snap_times = [float(x) for x in snaps["time"]]
        for i in range(len(evals)):
            eval_row = evals.iloc[i]
            ts_i = float(eval_row["timesteps"])
            t_i = sections[i]["section_time"]
            # 快照粒度推进状态机（时间 <= T_i），模拟连续轮询以正确累积停滞
            while snap_ptr < len(snaps) and snap_times[snap_ptr] <= t_i:
                sim.poll_snapshot(float(snaps["timesteps"].iloc[snap_ptr]), snap_times[snap_ptr])
                snap_ptr += 1
            tb_i = tbs[tbs["step"] <= ts_i]
            tb_row = tb_i.iloc[-1] if len(tb_i) else None
            # 按 tb 行粒度推进 KL 状态（与生产每 5s 轮询一致）：本截面新增 tb 行逐行喂入，
            # 使 last_valid_kl / kl_divergent 与离线窗口（step<=ts_i）完全一致
            if i == 0:
                new_tb = tbs[tbs["step"] <= ts_i]
            else:
                prev_ts_i = float(evals["timesteps"].iloc[i - 1])
                new_tb = tbs[(tbs["step"] > prev_ts_i) & (tbs["step"] <= ts_i)]
            st_kl = sim.monitor.state[(sim.task, sim.seed_id)]
            for _, tb_x in new_tb.iterrows():
                sim.monitor.update_kl_state(st_kl, tb_x["approx_kl"])
            history = [float(x) for x in evals["mean_reward"].iloc[: i + 1].tolist()][-HISTORY_SIZE:]
            # 轮询步长用最后快照步长（生产口径：轮询到的训练步长与快照同源），
            # 使实时停滞状态与离线窗口逐点对齐
            last_snap_ts = float(snaps["timesteps"].iloc[snap_ptr - 1]) if snap_ptr else ts_i
            seed_payload = build_eval_seed(
                task, seed, last_snap_ts, float(eval_row["mean_reward"]), history,
                None if tb_row is None else tb_row["approx_kl"],
                None if tb_row is None else tb_row["std"],
            )
            resources = _resources_from_snapshot(snaps.iloc[snap_ptr - 1]) if snap_ptr else {}
            on = sim.poll_eval(seed_payload, resources, t_i)

            off = offline_factors(
                task, seed,
                evals.iloc[: i + 1].reset_index(drop=True),
                tb_i.reset_index(drop=True),
                snaps[snaps["time"] <= t_i].reset_index(drop=True),
                runs, cfg,
            )
            cmp = compare_factors(off, on)
            row: dict[str, Any] = {"timesteps": ts_i, "section_time": t_i}
            section_failed = False
            for factor, res in cmp.items():
                row[f"{factor}_offline"] = res["offline"]
                row[f"{factor}_online"] = res["online"]
                row[f"{factor}_abs_diff"] = res["abs_diff"]
                row[f"{factor}_passed"] = res["passed"]
                agg = factor_stats[factor]
                if res["passed"] == "N/A":
                    agg["na"] += 1
                elif res["passed"]:
                    agg["passed"] += 1
                else:
                    agg["failed"] += 1
                    section_failed = True
                diff = res["abs_diff"]
                if diff is None and res["passed"] is False:
                    # ???????????????????CSV ? abs_diff ????
                    present = res["offline"] if res["offline"] is not None else res["online"]
                    diff = abs(float(present)) if present is not None else None
                if diff is not None and (agg["max_diff"] is None or diff > agg["max_diff"]):
                    agg["max_diff"] = diff
                    agg["max_diff_timesteps"] = ts_i
            rows.append(row)
            if section_failed:
                failed_sections.append({
                    "index": i + 1, "timesteps": ts_i, "section_time": t_i, "details": cmp,
                })

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    summary: dict[str, Any] = {
        "task": task,
        "seed": seed,
        "out_path": str(out_path),
        "total_sections": len(rows),
        "factor_stats": factor_stats,
        "failed_sections": failed_sections,
        "restart_count": _restart_count(snaps),
    }
    if verbose:
        _print_summary(summary)
    return summary


def _print_summary(s: dict[str, Any]) -> None:
    stats = s["factor_stats"]
    print("=" * 72)
    print(f"一致性校验: {s['task']}/{s['seed']}  总截面 {s['total_sections']}")
    print(f"输出: {s['out_path']}")
    print("-" * 72)
    print(f"{'因子':<22}{'通过':>5}{'失败':>5}{'N/A':>5}{'最大偏差':>13}{'位置(步数)':>14}")
    for factor, agg in stats.items():
        maxd = "-" if agg["max_diff"] is None else f"{agg['max_diff']:.6g}"
        loc = "-" if agg["max_diff_timesteps"] is None else f"{agg['max_diff_timesteps']:.0f}"
        print(f"{factor:<22}{agg['passed']:>5}{agg['failed']:>5}{agg['na']:>5}{maxd:>13}{loc:>14}")
    print("-" * 72)
    print("口径说明（P0 修复后两侧一致）:")
    print("  - stall_minutes = 窗口内最大停滞(max-so-far, 持久)；current_stall_minutes = 当前连续停滞(恢复归零)")
    print("  - restart_count = 规格回退(>100k -> <10k)次数；neg_ratio_current = 最后一次重启后的当前尝试占比")
    print("  - kl_divergent = 当前 tb 点 approx_kl 不在 (0,1]（含 NaN）；streak 按 eval 点连续计数")
    rc = int(s.get("restart_count") or 0)
    if rc:
        print(f"  - 本 run 快照流检测到 {rc} 次规格回退，restart_count / neg_ratio_current 已按重启分段对齐")
    print("-" * 72)
    print("已知结构性差异(不在对比表内):")
    print("  - eval_points: 实时=len(history) or 20(封顶20)，离线=截至截面实际点数")
    print("  - value_loss_divergent: 实时恒 False(API 无 value_loss 历史)，离线可判定发散")
    print("  - completed: 实时=seed.completed(回放中 False)，离线=runs.csv 实际值")
    print("  - eval_neg_ratio 真实部署口径: 5s 轮询会稀释比值；回放按每 eval 点一次轮询，与离线同口径")
    if s["failed_sections"]:
        print("-" * 72)
        show = s["failed_sections"][:3]
        print(f"不一致截面详情(前 {len(show)} 个):")
        for fs in show:
            print(f"  section {fs['index']} @ timesteps={fs['timesteps']:.0f}, T={fs['section_time']:.0f}")
            for factor, res in fs["details"].items():
                if res["passed"] is False:
                    ov = "-" if res["offline"] is None else f"{res['offline']:.6g}"
                    nv = "-" if res["online"] is None else f"{res['online']:.6g}"
                    dd = "-" if res["abs_diff"] is None else f"{res['abs_diff']:.6g}"
                    print(f"    {factor}: offline={ov}, online={nv}, diff={dd}")
    else:
        print("-" * 72)
        print("所有截面全部通过(N/A 因子除外)。")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 回测-实盘一致性校验（P0）")
    parser.add_argument("--config", default=None, help="config.json 路径")
    parser.add_argument("--task", default="balance", help="task（默认 balance）")
    parser.add_argument("--seed", default="seed00", help="seed（默认 seed00）")
    parser.add_argument("--today", default=None, help="输出日期 YYYY-MM-DD（默认今天）")
    parser.add_argument(
        "--out", default=None,
        help="覆盖输出文件路径（默认 data/modeling/consistency_check_YYYY-MM-DD.csv）",
    )
    args = parser.parse_args()
    cfg = load_config(Path(args.config))
    today = args.today or date.today().isoformat()
    out_path = Path(args.out) if args.out else (
        PROJECT_ROOT / str(cfg.get("modeling_dir", "data/modeling")) / f"consistency_check_{today}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_check(args.task, args.seed, cfg, out_path)


if __name__ == "__main__":
    main()