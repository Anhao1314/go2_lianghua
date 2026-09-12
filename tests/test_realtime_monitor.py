"""realtime_monitor 单元测试：全部 mock requests，无真实网络。"""

import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import factors
import realtime_monitor
from collector import load_config
from realtime_monitor import RealtimeMonitor

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_cfg() -> dict:
    cfg = load_config(PROJECT_ROOT / "config.json")
    cfg["monitor"] = {
        "webpanel_url": "http://test.local:8787",
        "poll_interval_seconds": 5,
        "log_csv": "data/monitor/realtime_log.csv",
        "enable_log": False,
        "total_steps_default": 8000000,
        "total_steps": {},
    }
    return cfg


class MockResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self._payload, (dict, list)):
            return json.loads(json.dumps(self._payload))
        return self._payload


def seed_payload(
    key="balance/seed00",
    timesteps=4000000,
    eval_reward=100.0,
    history=None,
    tb_kl=0.02,
    tb_std=0.9,
    stale=False,
    nan=False,
    alive=True,
    completed=False,
    speed=120.0,
    eta_seconds=100.0,
):
    return {
        "key": key, "timesteps": timesteps, "eval_reward": eval_reward,
        "tb_reward": 95.0, "ep_len": 500.0, "speed": speed,
        "eta_seconds": eta_seconds, "completed": completed, "alive": alive,
        "stale": stale, "nan": nan, "history": history or [],
        "tb_std": tb_std, "tb_value_loss": 0.5, "tb_kl": tb_kl,
        "tb_curve": [[0, 1.0]],
    }


def state_payload(seeds, resources=None):
    return {
        "time": time.time(),
        "resources": resources or {"cpu_percent": 80.0, "mem_percent": 60.0,
                                   "swap_percent": 10.0, "load": [1.0, 1.0, 1.0]},
        "seeds": seeds,
    }


def mock_get_side_effect(state_json, viewers=None):
    viewers = viewers if viewers is not None else []

    def _get(url, timeout=5):
        if url.endswith("/api/state"):
            return MockResponse(state_json)
        return MockResponse(viewers)

    return _get


class RealtimeMonitorTest(unittest.TestCase):
    def setUp(self):
        self.mon = RealtimeMonitor(make_cfg())

    # 1. 因子计算：drawdown / neg_ratio_recent / stall_minutes
    def test_factor_computation(self):
        with (
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload(
                      [seed_payload(timesteps=3000000, eval_reward=100.0,
                                    history=[10.0, -5.0, -20.0])]))),
            patch("realtime_monitor.time.time", return_value=1000.0),
        ):
            self.mon.poll_once()  # 首轮：峰值=100
        with (
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload(
                      [seed_payload(timesteps=4000000, eval_reward=80.0,
                                    history=[10.0, -5.0, -20.0])]))),
            patch("realtime_monitor.time.time", return_value=1000.0),
        ):
            self.mon.poll_once()  # 回落：dd=0.2
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertAlmostEqual(f["eval_drawdown"], 0.2, places=4)  # (100-80)/100
        self.assertAlmostEqual(f["eval_neg_ratio_recent"], 2 / 3, places=4)
        self.assertEqual(f["stall_minutes"], 0.0)
        self.assertEqual(f["current_stall_minutes"], 0.0)
        self.assertEqual(f["approx_kl_last"], 0.02)
        self.assertEqual(f["kl_divergent"], False)
        self.assertEqual(f["kl_divergent_streak"], 0)
        self.assertEqual(f["restart_count"], 0)
        self.assertEqual(f["eval_neg_ratio"], 0.0)  # 两轮奖励 100/80 均为正
        self.assertEqual(f["neg_ratio_current"], 0.0)
        self.assertEqual(f["nan_count"], 0)

    # 2. 峰值跨轮保持（先升后降不重置）
    def test_peak_tracking(self):
        seeds1 = [seed_payload(timesteps=1000000, eval_reward=100.0)]
        seeds2 = [seed_payload(timesteps=2000000, eval_reward=150.0)]
        seeds3 = [seed_payload(timesteps=3000000, eval_reward=60.0)]
        for s in (seeds1, seeds2, seeds3):
            with patch("realtime_monitor.requests.get",
                       side_effect=mock_get_side_effect(state_payload(s))):
                self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        self.assertEqual(st["peak_reward"], 150.0)
        f = st["last_factors"]
        self.assertAlmostEqual(f["eval_drawdown"], (150.0 - 60.0) / 150.0, places=4)

    # 3. 停滞累积与归零
    def test_stall_detection(self):
        t0 = 5000.0
        s = seed_payload(timesteps=4000000, eval_reward=100.0)
        with (
            patch("realtime_monitor.time.time", return_value=t0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s]))),
        ):
            self.mon.poll_once()  # 首轮：仅记录 timesteps
        with (
            patch("realtime_monitor.time.time", return_value=t0 + 1800.0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s]))),
        ):
            self.mon.poll_once()  # 同 timesteps：stall 起点 = 本轮
        with (
            patch("realtime_monitor.time.time", return_value=t0 + 3600.0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s]))),
        ):
            self.mon.poll_once()  # 仍同 timesteps：stall=30 分钟
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertEqual(f["stall_minutes"], 30.0)
        s2 = seed_payload(timesteps=4001000, eval_reward=100.0)
        with (
            patch("realtime_monitor.time.time", return_value=t0 + 3600.0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s2]))),
        ):
            self.mon.poll_once()  # timesteps 变化：current 归零，max 持久
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertEqual(f["stall_minutes"], 30.0)  # max-so-far 持久
        self.assertEqual(f["current_stall_minutes"], 0.0)  # 当前停滞归零

    def test_api_failure(self):
        with patch("realtime_monitor.requests.get",
                   side_effect=requests.ConnectionError("down")):
            rows = self.mon.poll_once()
        self.assertEqual(rows, [])

    def test_new_run_detection(self):
        with patch("realtime_monitor.requests.get",
                   side_effect=mock_get_side_effect(
                       state_payload([seed_payload(timesteps=4000000, eval_reward=100.0)]))):
            self.mon.poll_once()
        with patch("realtime_monitor.requests.get",
                   side_effect=mock_get_side_effect(
                       state_payload([seed_payload(timesteps=5000, eval_reward=10.0)]))):
            self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        self.assertEqual(st["peak_reward"], 10.0)  # 已重置，不再是 100
        self.assertEqual(st["poll_count"], 1)  # 当前尝试计数已重置
        self.assertEqual(st["total_poll_count"], 2)  # 全部尝试计数保留
        self.assertEqual(st["restart_count"], 1)  # 规格回退 +1
        # alive False->True 也重置（不计 restart_count）
        with patch("realtime_monitor.requests.get",
                   side_effect=mock_get_side_effect(state_payload(
                       [seed_payload(timesteps=6000, eval_reward=12.0, alive=True)]))):
            self.mon.state[("balance", "seed00")]["prev_alive"] = False
            self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        self.assertEqual(st["peak_reward"], 12.0)
        self.assertEqual(st["restart_count"], 1)

    # 9. stale/NaN 补充触发
    def test_stale_nan_triggers(self):
        t0 = 10000.0
        s = seed_payload(timesteps=4000000, eval_reward=100.0)
        with (
            patch("realtime_monitor.time.time", return_value=t0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s]))),
        ):
            self.mon.poll_once()  # 首轮：记录 timesteps
        with (
            patch("realtime_monitor.time.time", return_value=t0 + 60.0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s]))),
        ):
            self.mon.poll_once()  # 同 timesteps：stall 起点 = t0+60
        s_bad = seed_payload(timesteps=4000000, eval_reward=100.0,
                             stale=True, nan=True)
        with (
            patch("realtime_monitor.time.time", return_value=t0 + 3720.0),
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload([s_bad]))),
            patch("realtime_monitor.requests.post",
                  return_value=MockResponse({"code": 0})),
        ):
            self.mon.poll_once()  # 距 stall 起点 61 分钟 + stale + nan
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertGreater(f["stall_minutes"], 60.0)
        # 直接复核补充触发逻辑
        risks = self.mon._supplement_risks(s_bad, f, [])
        factors_seen = {i.factor for i in risks}
        self.assertIn("stall", factors_seen)
        self.assertIn("nan", factors_seen)
        self.assertTrue(all(i.level == "R2" for i in risks))
        self.assertTrue(any("stale" in i.message for i in risks))
        self.assertTrue(any("NaN" in i.message for i in risks))




    # 10. early_low_reward 实时计算（低奖励触发/高奖励不触发/同点去重/重启清空）
    def test_early_low_reward_online_low(self):
        seeds = [
            seed_payload(timesteps=100000, eval_reward=5.0),
            seed_payload(timesteps=300000, eval_reward=10.0),
            seed_payload(timesteps=300000, eval_reward=10.0),  # 同点重复轮询去重
            seed_payload(timesteps=700000, eval_reward=15.0),
        ]
        for s in seeds:
            with (
                patch("realtime_monitor.requests.get",
                      side_effect=mock_get_side_effect(state_payload([s]))),
                patch("realtime_monitor.requests.post",
                      return_value=MockResponse({"code": 0})),
            ):
                self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        f = st["last_factors"]
        self.assertEqual(len(st["eval_history"]), 3)  # 去重后 3 个 eval 点
        self.assertTrue(f["early_low_reward"])  # max=15 < balance 阈值 50

    def test_early_low_reward_online_high(self):
        seeds = [
            seed_payload(timesteps=100000, eval_reward=40.0),
            seed_payload(timesteps=300000, eval_reward=45.0),
            seed_payload(timesteps=700000, eval_reward=50.0),
        ]
        for s in seeds:
            with (
                patch("realtime_monitor.requests.get",
                      side_effect=mock_get_side_effect(state_payload([s]))),
                patch("realtime_monitor.requests.post",
                      return_value=MockResponse({"code": 0})),
            ):
                self.mon.poll_once()
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertFalse(f["early_low_reward"])  # max=50 >= 50

    def test_early_low_reward_restart_resets_history(self):
        with (
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload(
                      [seed_payload(timesteps=4000000, eval_reward=10.0)]))),
            patch("realtime_monitor.requests.post",
                  return_value=MockResponse({"code": 0})),
        ):
            self.mon.poll_once()
        with (
            patch("realtime_monitor.requests.get",
                  side_effect=mock_get_side_effect(state_payload(
                      [seed_payload(timesteps=9000, eval_reward=-5.0)]))),
            patch("realtime_monitor.requests.post",
                  return_value=MockResponse({"code": 0})),
        ):
            self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        self.assertEqual(st["restart_count"], 1)  # 4M -> 9k 规格回退
        self.assertEqual(len(st["eval_history"]), 1)  # 重启后当前尝试仅 1 点
        f = st["last_factors"]
        self.assertFalse(f["early_low_reward"])  # 早段仅 1 点，不足 3


if __name__ == "__main__":
    unittest.main()
