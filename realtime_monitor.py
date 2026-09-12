"""realtime_monitor.py - Windows 侧实时训练监控（本地建议制）。

每 poll_interval_seconds（默认 5s）轮询 Linux webpanel API：
  GET {webpanel_url}/api/state    -> {resources, seeds[]}
  GET {webpanel_url}/api/viewers  -> [{key, running, pid, model_available, ...}]

把每个 seed 的当前值适配成 factors.run_risk_items 可消费的因子字典
（API -> 因子字典适配器），复用离线风控规则与阈值，绝不重实现；

原则：
- 只输出本地建议、绝不自动干预训练（建议制，样本量尚不足以自动早停）；
- 复用 factors.py 的规则引擎，本模块只做字段适配；

用法：
  python realtime_monitor.py                 # 前台守护，Ctrl+C 停止
  python realtime_monitor.py --once          # 单轮轮询（连通性测试）
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

import factors
from collector import PROJECT_ROOT, load_config

_LEVEL_COLORS = {
    "R0": "\033[32m",
    "R1": "\033[33m",
    "R2": "\033[31m",
    "R3": "\033[91m",
    "RESET": "\033[0m",
}
_LEVEL_ORDER = ("R0", "R1", "R2", "R3")


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _enable_ansi() -> bool:
    """Windows 下尝试启用 VT 终端处理；失败返回 False（回退纯文本）。"""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        return True
    except Exception:
        return False


@dataclass
class SeedStatus:
    """单 seed 的单轮状态行（控制台表格用）。"""

    key: str
    timesteps: float
    reward: float
    drawdown: float
    level: str
    decision: str
    rules: list[str] = field(default_factory=list)


class RealtimeMonitor:
    """实时监控器：轮询 -> 因子适配 -> 复用风控规则 -> 表格/日志。"""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.mon: dict[str, Any] = cfg["monitor"]
        self.risk: dict[str, Any] = cfg["risk"]
        self.base_url = str(self.mon.get("webpanel_url", "http://127.0.0.1:8787")).rstrip("/")
        self.state: dict[tuple[str, str], dict[str, Any]] = {}
        self.started_at = time.time()
        self._color = _enable_ansi()
        self._last_resources: dict[str, Any] = {}
        self._last_alive = 0

    # ------------------------------------------------------------------
    # API 读取（优雅降级：任何失败返回 None/[]，不抛异常）
    # ------------------------------------------------------------------

    def fetch_state(self) -> dict[str, Any] | None:
        try:
            r = requests.get(f"{self.base_url}/api/state", timeout=5)
            if r.status_code != 200:
                print(f"[WARN] API返回 {r.status_code}", flush=True)
                return None
            data = r.json()
            return data if isinstance(data, dict) else None
        except requests.RequestException as e:
            print(f"[WARN] 无法连接 webpanel: {e}, 重试中", flush=True)
            return None
        except ValueError:
            print("[WARN] API格式异常", flush=True)
            return None

    def fetch_viewers(self) -> list[dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/viewers", timeout=5)
            if r.status_code != 200:
                return []
            data = r.json()
            return [v for v in data if isinstance(v, dict)] if isinstance(data, list) else []
        except (requests.RequestException, ValueError):
            return []

    # ------------------------------------------------------------------
    # 状态机
    # ------------------------------------------------------------------

    @staticmethod
    def _task_seed(key: str) -> tuple[str, str]:
        parts = str(key).split("/")
        return parts[0], parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _new_state() -> dict[str, Any]:
        return {
            "peak_reward": float("-inf"),
            "prev_timesteps": None,
            "last_timesteps": None,
            "stall_start_ts": None,
            "neg_count": 0,            # 当前训练尝试的负奖励/轮询计数（重启重置）
            "poll_count": 0,
            "total_neg_count": 0,      # 全部尝试累计（重启不重置，与离线 eval_neg_ratio 同口径）
            "total_poll_count": 0,
            "restart_count": 0,        # 规格回退（timesteps >100k -> <10k）次数
            "max_stall_minutes": 0.0,  # stall_minutes：窗口内最大停滞（max-so-far，持久）
            "last_valid_kl": None,     # 最近一次有效 approx_kl（当前点损坏时回退）
            "kl_divergent": False,     # 当前 tb 点 KL 超界（含 NaN/缺失）标志
            "kl_divergent_streak": 0,  # 连续发散的 eval 轮数（按 eval 轮次计数）
            "prev_alive": None,
            "last_factors": {},
            "eval_history": [],  # [timesteps, reward] 当前训练尝试的 eval 点序列（重启重置）
        }

    def update_state(self, task: str, seed_id: str, seed: dict[str, Any]) -> dict[str, Any]:
        """维护单 run 内存状态：峰值、步数、停滞、负奖励计数、KL 状态、alive 沿。

        重启判定：
          - 规格回退：prev>100k 且 cur<10k（restart_count +1，与离线同口径）；
          - alive False->True（重置当前尝试，但不计 restart_count）。
        重启时保留跨重启状态：全部尝试计数（total_*）、restart_count、
        last_valid_kl 与 kl_divergent_streak（与离线全窗口口径一致）；
        重置当前尝试状态：峰值、负奖励计数、停滞、冷却历史。
        stall_minutes 为 max-so-far（持久），current_stall_minutes 恢复即归零。
        """
        key = (task, seed_id)
        st = self.state.get(key)
        if st is None:
            st = self._new_state()
            self.state[key] = st
        cur_ts = _to_float(seed.get("timesteps")) or 0.0
        alive = bool(seed.get("alive", True))
        prev_ts = st["prev_timesteps"]
        is_fall = prev_ts is not None and prev_ts > 100000 and cur_ts < 10000
        if is_fall or (st["prev_alive"] is False and alive):
            carry = {
                "total_neg_count": st["total_neg_count"],
                "total_poll_count": st["total_poll_count"],
                "restart_count": st["restart_count"] + (1 if is_fall else 0),
                "last_valid_kl": st["last_valid_kl"],
                "kl_divergent": st["kl_divergent"],
                "kl_divergent_streak": st["kl_divergent_streak"],
                "max_stall_minutes": st["max_stall_minutes"],  # max-so-far 跨重启持久
            }
            st = self._new_state()
            st.update(carry)
            self.state[key] = st
        st["prev_timesteps"] = cur_ts
        st["prev_alive"] = alive
        reward = _to_float(seed.get("eval_reward"))
        if reward is not None:
            if reward > st["peak_reward"]:
                st["peak_reward"] = reward
            st["poll_count"] += 1
            st["total_poll_count"] += 1
            if reward < 0:
                st["neg_count"] += 1
                st["total_neg_count"] += 1
            # early_low_reward 历史：按"奖励值变化去重"追加（同一 eval 点在多次
            # 轮询间 eval_reward 不变，不重复计；新 eval 点奖励变化时计入）
            hist = st["eval_history"]
            if not hist or hist[-1][1] != reward:
                hist.append([cur_ts, reward])
        now = time.time()
        if st["last_timesteps"] is not None and cur_ts == st["last_timesteps"]:
            if st["stall_start_ts"] is None:
                st["stall_start_ts"] = now
        else:
            st["stall_start_ts"] = None
        st["last_timesteps"] = cur_ts
        if st["stall_start_ts"] is not None:
            cur_stall = (now - st["stall_start_ts"]) / 60.0
            if cur_stall > st["max_stall_minutes"]:
                st["max_stall_minutes"] = cur_stall
        return st

    def update_kl_state(self, st: dict[str, Any], tb_kl: Any) -> None:
        """按 tb 行粒度维护 KL 状态：当前点有效则更新 last_valid_kl 并清发散标志，
        损坏（NaN/<=0/>1）或缺失则保持 last_valid_kl 并置发散标志。
        kl_divergent_streak 由 compute_factors 按 eval 轮次计数（规则口径）。
        """
        kl = _to_float(tb_kl)
        valid = kl is not None and (0.0 < kl <= 1.0)
        st["kl_divergent"] = not valid
        if valid:
            st["last_valid_kl"] = kl

    def _total_steps(self, task: str) -> float:
        per = self.mon.get("total_steps") or {}
        return float(per.get(task, self.mon.get("total_steps_default", 8000000)))

    # ------------------------------------------------------------------
    # 因子适配器：API seed -> factors.run_risk_items 可消费的因子字典
    # ------------------------------------------------------------------

    def compute_factors(
        self, task: str, seed: dict[str, Any], resources: dict[str, Any], st: dict[str, Any]
    ) -> dict[str, Any]:
        reward = _to_float(seed.get("eval_reward")) or 0.0
        cur_ts = _to_float(seed.get("timesteps")) or 0.0
        peak = st["peak_reward"]
        peak_valid = peak > 0
        drawdown = min(1.0, (peak - reward) / peak) if peak_valid else 0.0
        history = [h for h in (seed.get("history") or []) if isinstance(h, (int, float))]
        # 与离线同口径：仅取 history 尾部 recent_window 点（API 保留 20 点）
        recent_window = max(int(self.risk.get("neg_ratio", {}).get("recent_window", 5)), 1)
        recent = history[-recent_window:]
        neg_recent = (
            round(sum(1 for h in recent if h < 0) / len(recent), 4) if recent else None
        )
        # KL 状态（last_valid_kl / kl_divergent）由 update_kl_state 按 tb 行粒度维护；
        # 发散连续数按 eval 轮次计数（与离线 eval 对齐口径一致）
        if st.get("kl_divergent", False):
            st["kl_divergent_streak"] += 1
        else:
            st["kl_divergent_streak"] = 0
        stall = 0.0
        if st["stall_start_ts"] is not None:
            stall = (time.time() - st["stall_start_ts"]) / 60.0
        max_stall = max(st["max_stall_minutes"], stall)
        total = self._total_steps(task)
        early_low_reward = None
        eval_history = st.get("eval_history") or []
        if eval_history and total > 0:
            e = self.risk.get("early_low_reward") or {}
            min_pts = int(e.get("min_early_points", 3))
            cutoff = total * 0.25
            early = [r for _ts, r in eval_history if _ts <= cutoff]
            if early:
                if len(early) >= min_pts:
                    threshold = factors.early_low_reward_threshold(task, self.cfg)
                    early_low_reward = bool(max(early) < threshold)
                else:
                    early_low_reward = False
        f: dict[str, Any] = {
            "eval_last_reward": round(reward, 4),
            "eval_peak_reward": round(peak, 4) if peak_valid else None,
            "eval_drawdown": round(drawdown, 4),  # 恒为数值：规则用 > 比较
            "reward_peak_ratio": round(reward / peak, 4) if peak_valid else None,
            "progress_ratio": round(cur_ts / total, 4) if total > 0 else None,
            "eval_neg_ratio_recent": neg_recent,
            "eval_neg_ratio": round(st["total_neg_count"] / st["total_poll_count"], 4)
            if st["total_poll_count"]
            else None,
            "early_low_reward": early_low_reward,
            "neg_ratio_current": round(st["neg_count"] / st["poll_count"], 4)
            if st["poll_count"]
            else None,
            "approx_kl_last": round(st["last_valid_kl"], 4)
            if st["last_valid_kl"] is not None
            else None,
            "kl_divergent": bool(st.get("kl_divergent", False)),
            "kl_divergent_streak": st["kl_divergent_streak"],
            "std_last": _to_float(seed.get("tb_std")),
            "value_loss_divergent": False,  # API 无历史，恒 False
            "stall_minutes": round(max_stall, 1),
            "current_stall_minutes": round(stall, 1),
            "restart_count": st["restart_count"],
            "idle_minutes": 0,
            "cpu_percent_max": _to_float(resources.get("cpu_percent")),
            "mem_percent_max": _to_float(resources.get("mem_percent")),
            "swap_percent_max": _to_float(resources.get("swap_percent")),
            "completed": bool(seed.get("completed")),
            "eval_points": len(history) or 20,
            "eval_last_timesteps": int(cur_ts),
            "nan_count": 1 if bool(seed.get("nan")) else 0,
            "eval_slope_per_1e6": None,  # 规则未使用，置 None 安全
            "eval_std_recent": None,  # 规则有 is not None 守卫
            # 注意：ev_neg_streak 不写入 f——run_risk_items 用
            # f.get("ev_neg_streak", 0) >= n，显式 None 会 TypeError
        }
        return f

    # ------------------------------------------------------------------
    # 风控：复用 factors 规则 + stale/NaN 补充触发
    # ------------------------------------------------------------------

    def _supplement_risks(
        self, seed: dict[str, Any], f: dict[str, Any], risks: list[factors.RiskItem]
    ) -> list[factors.RiskItem]:
        risks = list(risks)
        stall = float(f.get("stall_minutes", 0.0))
        if bool(seed.get("stale")) and stall > self.risk["stall_minutes"]["warn"]:
            risks.append(
                factors.RiskItem(
                    "R2", "snapshots", "stall",
                    f"训练停滞（webpanel stale标志，已停滞{stall:.0f}分钟）",
                )
            )
        if bool(seed.get("nan")):
            risks.append(
                factors.RiskItem("R2", "eval_points", "nan", "检测到NaN（webpanel nan标志）")
            )
        return risks

    # ------------------------------------------------------------------
    # 单轮轮询
    # ------------------------------------------------------------------

    def poll_once(self) -> list[SeedStatus]:
        payload = self.fetch_state()
        if payload is None:
            return []
        viewers = self.fetch_viewers()
        viewers_by_key = {str(v.get("key")): v for v in viewers}
        seeds = payload.get("seeds") or []
        resources = payload.get("resources") or {}
        self._last_resources = resources
        self._last_alive = int(sum(1 for s in seeds if isinstance(s, dict) and s.get("alive")))
        rows: list[SeedStatus] = []
        for seed in seeds:
            if not isinstance(seed, dict):
                continue
            key = str(seed.get("key") or "")
            if not key or seed.get("eval_reward") is None:
                continue
            merged = {**(viewers_by_key.get(key) or {}), **seed}
            task, sid = self._task_seed(key)
            st = self.update_state(task, sid, merged)
            self.update_kl_state(st, merged.get("tb_kl"))
            f = self.compute_factors(task, merged, resources, st)
            risks = self._supplement_risks(merged, f, factors.run_risk_items(f, self.cfg))
            level = factors.max_level(risks)
            decision, _reasons = factors.decide(f, risks, self.cfg)
            st["last_factors"] = f
            self._log_row(task, sid, merged, f, level, decision, risks)
            rows.append(
                SeedStatus(
                    key=f"{task}/{sid}",
                    timesteps=float(f.get("eval_last_timesteps") or 0),
                    reward=float(f.get("eval_last_reward") or 0),
                    drawdown=float(f.get("eval_drawdown") or 0),
                    level=level,
                    decision=decision,
                    rules=sorted({i.factor for i in risks}),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # 日志 CSV（追加写，utf-8-sig）
    # ------------------------------------------------------------------

    def _log_row(
        self,
        task: str,
        seed_id: str,
        seed: dict[str, Any],
        f: dict[str, Any],
        level: str,
        decision: str,
        risks: list[factors.RiskItem],
    ) -> None:
        if not self.mon.get("enable_log", True):
            return
        try:
            path = Path(self.mon.get("log_csv", "data/monitor/realtime_log.csv"))
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            new_file = not path.exists()
            row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "task": task,
                "seed": seed_id,
                "timesteps": f.get("eval_last_timesteps"),
                "eval_reward": f.get("eval_last_reward"),
                "tb_reward": _to_float(seed.get("tb_reward")),
                "ep_len": _to_float(seed.get("ep_len")),
                "speed": _to_float(seed.get("speed")),
                "drawdown": f.get("eval_drawdown"),
                "neg_ratio_recent": f.get("eval_neg_ratio_recent"),
                "tb_kl_clean": f.get("approx_kl_last"),
                "tb_std": f.get("std_last"),
                "stall_minutes": f.get("stall_minutes"),
                "level": level,
                "decision": decision,
                "triggered_rules": "|".join(sorted({i.factor for i in risks})),
            }
            pd.DataFrame([row]).to_csv(
                path, mode="a", header=new_file, index=False, encoding="utf-8-sig"
            )
        except Exception as e:
            print(f"[WARN] 日志写入失败: {e}", flush=True)

    # ------------------------------------------------------------------
    # 控制台表格
    # ------------------------------------------------------------------

    def render_table(self, rows: list[SeedStatus]) -> None:
        cpu = _to_float(self._last_resources.get("cpu_percent"))
        mem = _to_float(self._last_resources.get("mem_percent"))
        swap = _to_float(self._last_resources.get("swap_percent"))
        cpu_s = f"{cpu:.1f}%" if cpu is not None else "?"
        mem_s = f"{mem:.1f}%" if mem is not None else "?"
        swap_s = f"{swap:.1f}%" if swap is not None else "?"
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"CPU {cpu_s} MEM {mem_s} SWAP {swap_s} | {self._last_alive} seeds alive",
            flush=True,
        )
        for row in rows:
            color = _LEVEL_COLORS.get(row.level, "")
            reset = _LEVEL_COLORS["RESET"] if color else ""
            if not self._color:
                color, reset = "", ""
            rules = ",".join(row.rules) if row.rules else "-"
            print(
                f"  {row.key:<24} {int(row.timesteps):>10,}  "
                f"reward={row.reward:>8.1f}  DD={row.drawdown:.0%}  "
                f"{color}[{row.level}]{reset} {row.decision:<8} {rules}",
                flush=True,
            )

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run(self) -> None:
        interval = float(self.mon.get("poll_interval_seconds", 5))
        print(
            f"[realtime_monitor] 启动：{self.base_url}，每 {interval:g} 秒轮询（本地建议制，不自动干预训练）",
            flush=True,
        )
        try:
            while True:
                try:
                    rows = self.poll_once()
                    self.render_table(rows)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"[WARN] 轮询异常: {e}", flush=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
        duration = time.time() - self.started_at
        print(f"监控已停止。运行时长: {duration:.0f} 秒。", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 实时训练监控（本地建议制）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--once", action="store_true", help="单轮轮询（连通性测试）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    monitor = RealtimeMonitor(cfg)

    if args.once:
        rows = monitor.poll_once()
        monitor.render_table(rows)
        return
    monitor.run()


if __name__ == "__main__":
    main()
