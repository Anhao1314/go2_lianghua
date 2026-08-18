"""curve_fit 单元测试：幂律/指数拟合、前缀外推、跨 seed 置信带、绘图冒烟。"""

import pathlib
import tempfile
import unittest

import numpy as np
import pandas as pd

import curve_fit


def make_evals(task: str = "balance", seed: str = "seed00", t=None, y=None) -> pd.DataFrame:
    t = t if t is not None else np.arange(10000, 1000001, 10000)
    if y is None:
        y = 100.0 - 50.0 * t ** (-0.5)
    return pd.DataFrame(
        {
            "task": task,
            "seed": seed,
            "timesteps": t,
            "mean_reward": y,
            "std_reward": 0.1,
            "mean_ep_len": 100.0,
        }
    )


class FitTest(unittest.TestCase):
    def test_fit_power_law_recovers_params(self):
        # t 从 1 开始，曲线动态范围 ~50，噪声不淹没信号
        t = np.arange(1, 100001, 2000)
        y = 100.0 - 50.0 * t ** (-0.5) + np.random.default_rng(0).normal(0, 0.3, len(t))
        fit = curve_fit.fit_learning_curve(make_evals(t=t, y=y), "balance", "seed00")
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["R_inf"], 100.0, delta=5.0)
        self.assertAlmostEqual(fit["alpha"], 0.5, delta=0.3)
        self.assertGreater(fit["r2"], 0.9)

    def test_fit_exponential_recovers_params(self):
        t = np.arange(10000, 1000001, 10000)
        y = 80.0 - 60.0 * np.exp(-1e-4 * t)
        fit = curve_fit.fit_learning_curve(make_evals(t=t, y=y), "balance", "seed00")
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["R_inf"], 80.0, delta=5.0)
        self.assertGreater(fit["r2"], 0.9)

    def test_fit_non_monotonic_uses_envelope(self):
        # 先升后跌：包络保证拟合不随回撤段下降，R_inf >= 观测峰值
        t = np.arange(10000, 1000001, 10000)
        y = np.concatenate([np.linspace(10, 90, len(t) // 2),
                            np.linspace(90, 30, len(t) - len(t) // 2)])
        fit = curve_fit.fit_learning_curve(make_evals(t=t, y=y), "balance", "seed00")
        self.assertIsNotNone(fit)
        self.assertGreaterEqual(fit["R_inf"], y.max() - 1e-6)
        self.assertGreater(fit["r2"], 0.7)

    def test_fit_flat_envelope_returns_none(self):
        # 起点即峰值后一路下滑：包络为平线，学习曲线模型不适用
        t = np.arange(10000, 200001, 10000)
        y = np.linspace(100.0, 30.0, len(t))
        self.assertIsNone(curve_fit.fit_learning_curve(make_evals(t=t, y=y), "b", "s"))

    def test_fit_linear_rise_marked_unreliable(self):
        # 线性上行：R_inf 趋向无穷，外推不可靠
        t = np.arange(1, 100001, 2000)
        y = t.astype(float) / 1000.0
        fit = curve_fit.fit_learning_curve(make_evals(t=t, y=y, task="b", seed="s"), "b", "s")
        self.assertIsNotNone(fit)
        self.assertFalse(fit["reliable"])

    def test_fit_saturating_curve_reliable(self):
        t = np.arange(1, 100001, 2000)
        y = 100.0 - 50.0 * t ** (-0.5)
        fit = curve_fit.fit_learning_curve(make_evals(t=t, y=y, task="b", seed="s"), "b", "s")
        self.assertIsNotNone(fit)
        self.assertTrue(fit["reliable"])

    def test_fit_insufficient_points(self):
        t = np.array([10000, 20000])
        y = np.array([10.0, 20.0])
        evals = make_evals(t=t, y=y, task="b", seed="s")
        self.assertIsNone(curve_fit.fit_learning_curve(evals, "b", "s"))

    def test_fit_reports_both_models(self):
        t = np.arange(10000, 500001, 10000)
        y = 100.0 - 50.0 * t ** (-0.5)
        evals = make_evals(t=t, y=y, task="b", seed="s")
        fit = curve_fit.fit_learning_curve(evals, "b", "s")
        self.assertIn("R_inf_power", fit)
        self.assertIn("R_inf_exp", fit)
        self.assertIn("r2_power", fit)
        self.assertIn("r2_exp", fit)


class ExtrapolateTest(unittest.TestCase):
    def test_extrapolate_uses_prefix_only(self):
        full = make_evals(t=np.arange(10000, 1000001, 10000))
        ext = curve_fit.extrapolate_R_inf(full, 0.5, total_steps=1000000)
        self.assertIsNotNone(ext)
        self.assertEqual(ext["cut_timesteps"], 500000)
        self.assertLessEqual(ext["used_timesteps"], 500000)
        self.assertAlmostEqual(ext["R_inf"], 100.0, delta=8.0)

    def test_extrapolate_without_total_steps_uses_observed_max(self):
        full = make_evals(t=np.arange(10000, 500001, 10000))
        ext = curve_fit.extrapolate_R_inf(full, 0.5)
        self.assertIsNotNone(ext)
        self.assertEqual(ext["cut_timesteps"], 250000)

    def test_extrapolate_rejects_multi_run(self):
        df = pd.concat([make_evals(), make_evals(task="traverse")])
        with self.assertRaises(ValueError):
            curve_fit.extrapolate_R_inf(df, 0.5)

    def test_extrapolate_insufficient_prefix(self):
        t = np.arange(10000, 100001, 10000)
        y = np.ones(len(t))
        self.assertIsNone(curve_fit.extrapolate_R_inf(make_evals(t=t, y=y), 0.05))


class BandTest(unittest.TestCase):
    def test_cross_seed_band(self):
        t = np.array([100000, 200000, 300000])
        df = pd.concat(
            [
                make_evals(task="balance", seed="seed00", t=t, y=[10.0, 20.0, 30.0]),
                make_evals(task="balance", seed="seed01", t=t, y=[12.0, 22.0, 32.0]),
            ]
        )
        band = curve_fit.cross_seed_band(df, "balance")
        self.assertEqual(len(band), 3)
        row = band[band["timesteps"] == 100000].iloc[0]
        self.assertAlmostEqual(row["mean"], 11.0)
        self.assertEqual(row["n_seeds"], 2)
        self.assertLess(row["ci_low"], row["mean"])
        self.assertGreater(row["ci_high"], row["mean"])

    def test_cross_seed_band_single_seed_ci_nan(self):
        t = np.array([100000, 200000, 300000])
        band = curve_fit.cross_seed_band(make_evals(t=t), "balance")
        self.assertEqual(len(band), 3)
        self.assertTrue(band["ci_low"].isna().all())
        self.assertTrue(band["ci_high"].isna().all())


class PlotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plot_run_fit_smoke(self):
        t = np.arange(10000, 500001, 10000)
        y = 100.0 - 50.0 * t ** (-0.5)
        evals = make_evals(t=t, y=y)
        fit = curve_fit.fit_learning_curve(evals, "balance", "seed00")
        path = curve_fit.plot_run_fit(evals, fit, self.dir)
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)

    def test_plot_task_band_smoke(self):
        t = np.array([100000, 200000, 300000])
        df = pd.concat(
            [
                make_evals(task="balance", seed="seed00", t=t, y=[10.0, 20.0, 30.0]),
                make_evals(task="balance", seed="seed01", t=t, y=[12.0, 22.0, 32.0]),
            ]
        )
        path = curve_fit.plot_task_band(df, "balance", self.dir)
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
