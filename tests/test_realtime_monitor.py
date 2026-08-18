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
        "feishu_webhook": "https://test.local/hook",
        "notify_min_level": "R2",
        "cooldown_minutes": 10,
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
        self.assertEqual(f["approx_kl_last"], 0.02)
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
            self.mon.poll_once()  # timesteps 变化：归零
        f = self.mon.state[("balance", "seed00")]["last_factors"]
        self.assertEqual(f["stall_minutes"], 0.0)

    # 4. 冷却：同因子 R2 三轮只发一条
    def test_cooldown(self):
        polls = [
            seed_payload(timesteps=1000000, eval_reward=100.0),  # 首轮：峰值
            seed_payload(timesteps=2000000, eval_reward=10.0),   # dd=0.9 -> R2 发送
            seed_payload(timesteps=3000000, eval_reward=10.0),   # 冷却期内：不再发
        ]
        with patch("realtime_monitor.requests.post",
                   return_value=MockResponse({"code": 0})) as post:
            for s in polls:
                with patch("realtime_monitor.requests.get",
                           side_effect=mock_get_side_effect(state_payload([s]))):
                    self.mon.poll_once()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(self.mon.notify_count, 1)

    # 5. 升级免冷却：R2 后 R3 同因子再发；再 R3 不发
    def test_level_escalation(self):
        task, sid = "balance", "seed00"
        self.mon.state[(task, sid)] = self.mon._new_state()
        st = self.mon.state[(task, sid)]
        seed = seed_payload()
        f = {"eval_drawdown": 0.9, "eval_last_reward": 10.0,
             "eval_last_timesteps": 1000000, "eval_peak_reward": 100.0}
        r2 = [factors.RiskItem("R2", "eval_points", "drawdown", "回撤90%")]
        r3 = [factors.RiskItem("R3", "eval_points", "drawdown", "回撤严重")]
        with (
            patch("realtime_monitor.time.time", return_value=1000.0),
            patch("realtime_monitor.requests.post",
                  return_value=MockResponse({"code": 0})) as post,
        ):
            self.assertTrue(self.mon._maybe_notify(task, sid, seed, f, r2, "R2", "stop"))
            self.assertTrue(self.mon._maybe_notify(task, sid, seed, f, r3, "R3", "stop"))
            self.assertFalse(self.mon._maybe_notify(task, sid, seed, f, r3, "R3", "stop"))
        self.assertEqual(post.call_count, 2)

    # 6. API 故障不崩溃
    def test_api_failure(self):
        with patch("realtime_monitor.requests.get",
                   side_effect=requests.ConnectionError("down")):
            rows = self.mon.poll_once()
        self.assertEqual(rows, [])

    # 7. 飞书消息格式
    def test_feishu_message_format(self):
        seed = seed_payload(timesteps=4000000, eval_reward=-18.8,
                            history=[10.0, 5.0, -5.0, -10.0, -18.8])
        f = {"eval_last_timesteps": 4000000, "eval_last_reward": -18.8,
             "eval_peak_reward": 100.0, "eval_drawdown": 1.0}
        items = [factors.RiskItem("R2", "eval_points", "neg_ratio", "负值占比高")]
        msg = self.mon._build_message("balance", "seed00", seed, f, items, "R2", "stop")
        for piece in ("训练告警 [R2]", "balance/seed00", "当前奖励：-18.80",
                      "回撤 100%", "决策建议：stop", "4,000,000 / 8,000,000"):
            self.assertIn(piece, msg)

    # 8. 新 run 检测：步数回退（<10k）与 alive 翻转均重置
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
        self.assertEqual(st["poll_count"], 1)
        # alive False->True 也重置
        with patch("realtime_monitor.requests.get",
                   side_effect=mock_get_side_effect(state_payload(
                       [seed_payload(timesteps=6000, eval_reward=12.0, alive=True)]))):
            self.mon.state[("balance", "seed00")]["prev_alive"] = False
            self.mon.poll_once()
        st = self.mon.state[("balance", "seed00")]
        self.assertEqual(st["peak_reward"], 12.0)

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


if __name__ == "__main__":
    unittest.main()
