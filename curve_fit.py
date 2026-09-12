"""学习曲线拟合与外推（B 方案 Layer 2）。

单 run 奖励曲线拟合：
  - 幂律: R(t) = R_inf - A * t^(-alpha)
  - 指数: R(t) = R_inf - A * exp(-k * t)
RL 曲线非单调（会出现回撤），拟合前对奖励取 cummax 包络；
R_inf 受约束 >= 观测最大值。extrapolate_R_inf 只用训练进度 fraction
之前的数据，是"早期预测最终奖励"的核心接口。

用法：
  python curve_fit.py --config config.json                 # 全部 run
  python curve_fit.py --config config.json --task balance  # 指定任务
  python curve_fit.py --config config.json --validate      # completed run 外推 vs 实际末值
输出：data/modeling/curve_fits_YYYY-MM-DD.csv、data/modeling/validate_YYYY-MM-DD.csv、
      data/modeling/plots/*.png
"""

from __future__ import annotations

import argparse
import pathlib
from datetime import date as _Date

import numpy as np
import pandas as pd
from scipy import optimize, stats

from collector import PROJECT_ROOT, load_config
from modeling import resolve_out_dir
from quant import load_tables

MIN_POINTS = 4
VALIDATE_FRACTIONS = (0.25, 0.5)


# --------------------------------------------------------------------------
# 数据准备
# --------------------------------------------------------------------------

def _series(evals: pd.DataFrame, task: str, seed: str) -> pd.DataFrame:
    """提取单个 run 的 (timesteps, mean_reward)，按步数排序、去重。"""
    df = evals[(evals["task"] == task) & (evals["seed"] == seed)]
    out = pd.DataFrame(
        {
            "t": pd.to_numeric(df["timesteps"], errors="coerce"),
            "y": pd.to_numeric(df["mean_reward"], errors="coerce"),
        }
    ).dropna()
    return out.drop_duplicates(subset="t", keep="last").sort_values("t").reset_index(drop=True)


# --------------------------------------------------------------------------
# 拟合
# --------------------------------------------------------------------------

def _fit_power(tn: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """R(tn) = R_inf - A * tn^(-alpha)（tn = t/t_min 归一化），返回 (R_inf, A, alpha)。"""
    def f(tn, R_inf, A, alpha):
        return R_inf - A * tn ** (-alpha)

    span = max(1.0, float(y.max()) - float(y.min()))
    p0 = [float(y.max()) * 1.1 + 1.0, span, 0.5]
    bounds = ([float(y.max()), 0.0, 0.05], [np.inf, np.inf, 10.0])
    popt, _ = optimize.curve_fit(f, tn, y, p0=p0, bounds=bounds, maxfev=50000)
    return tuple(float(v) for v in popt)  # type: ignore[return-value]


def _fit_exp(tn: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """R(tn) = R_inf - A * exp(-k * tn)（tn = t/t_min 归一化），返回 (R_inf, A, k)。"""
    def f(tn, R_inf, A, k):
        return R_inf - A * np.exp(-k * tn)

    span = max(1.0, float(y.max()) - float(y.min()))
    p0 = [float(y.max()) * 1.1 + 1.0, span, 0.1]
    bounds = ([float(y.max()), 0.0, 1e-6], [np.inf, np.inf, 10.0])
    popt, _ = optimize.curve_fit(f, tn, y, p0=p0, bounds=bounds, maxfev=50000)
    return tuple(float(v) for v in popt)  # type: ignore[return-value]


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - ss_res / ss_tot


def fit_learning_curve(
    evals: pd.DataFrame, task: str, seed: str
) -> dict | None:
    """拟合单个 run 的奖励包络曲线，返回 best 模型参数；数据不足返回 None。"""
    s = _series(evals, task, seed)
    if len(s) < MIN_POINTS:
        return None
    t_all = s["t"].to_numpy(dtype=float)
    y_all = s["y"].to_numpy(dtype=float)
    t = t_all[t_all > 0]
    y = np.maximum.accumulate(y_all[t_all > 0])  # cummax 包络，只保留正步数
    if len(t) < MIN_POINTS:
        return None
    if float(np.ptp(y)) <= 1e-9 * max(1.0, abs(float(y.max()))):
        return None  # 包络为平线（曲线从未上升，或起点即峰值后一路下滑），学习曲线模型不适用

    tmin = float(t[0])
    tn = t / tmin  # 归一化改善数值条件（t 可达 8e6，直接拟合幂律会病态）
    results: list[tuple[str, tuple[float, float, float], float]] = []
    for name, fitter in (("power", _fit_power), ("exp", _fit_exp)):
        try:
            popt = fitter(tn, y)
        except Exception:
            continue  # 拟合失败（如常数序列）则跳过该模型
        if name == "power":
            yhat = popt[0] - popt[1] * tn ** (-popt[2])
            p_out = (popt[0], popt[1] * tmin ** popt[2], popt[2])  # A 还原到原单位
        else:
            yhat = popt[0] - popt[1] * np.exp(-popt[2] * tn)
            p_out = (popt[0], popt[1], popt[2] / tmin)  # k 还原到原单位
        results.append((name, p_out, _r2(y, yhat)))
    results = [r for r in results if r[2] > 0.0]  # r2<=0 的拟合劣于常数基线，弃用
    if not results:
        return None
    results.sort(key=lambda r: -r[2])

    out: dict = {
        "task": task,
        "seed": seed,
        "n_points": int(len(s)),
        "ok": True,
    }
    for name, popt, r2 in results:
        out[f"R_inf_{name}"] = round(popt[0], 4)
        out[f"r2_{name}"] = round(r2, 4)
    best_name, best_popt, best_r2 = results[0]
    out["model"] = best_name
    out["R_inf"] = round(best_popt[0], 4)
    out["A"] = round(best_popt[1], 4)
    out["alpha" if best_name == "power" else "k"] = round(best_popt[2], 6)
    out["r2"] = round(best_r2, 4)
    # 外推可信度：拟合质量合格，且剩余上升比例 (R_inf - 包络末值)/R_inf <= 30%
    # （曲线已开始饱和；否则"仍在上行"，R_inf 外推不可靠）
    y_last = float(y[-1])
    remaining_rise = (out["R_inf"] - y_last) / out["R_inf"] if out["R_inf"] > 0 else 1.0
    out["reliable"] = bool(best_r2 >= 0.3 and remaining_rise <= 0.3)
    return out


def extrapolate_R_inf(
    evals: pd.DataFrame, progress_fraction: float, total_steps: float | None = None
) -> dict | None:
    """只用训练进度 progress_fraction 之前的数据外推 R_inf。

    evals 必须只包含一个 (task, seed)；total_steps 缺省时用观测最大步数。
    返回 fit 结果并附带 cut_timesteps；数据不足返回 None。
    """
    if not 0 < progress_fraction <= 1:
        raise ValueError("progress_fraction 需在 (0, 1] 区间")
    if evals is None or evals.empty:
        return None
    keys = evals[["task", "seed"]].drop_duplicates()
    if len(keys) != 1:
        raise ValueError("extrapolate_R_inf 需要单个 (task, seed) 的数据")
    task, seed = keys.iloc[0]["task"], keys.iloc[0]["seed"]

    max_t = float(pd.to_numeric(evals["timesteps"], errors="coerce").max())
    cutoff = progress_fraction * (float(total_steps) if total_steps else max_t)
    prefix = evals[pd.to_numeric(evals["timesteps"], errors="coerce") <= cutoff]
    if prefix.empty:
        return None
    fit = fit_learning_curve(prefix, task, seed)
    if fit is None:
        return None
    fit["progress_fraction"] = progress_fraction
    fit["cut_timesteps"] = int(cutoff)
    fit["used_timesteps"] = int(prefix["timesteps"].max())
    return fit


# --------------------------------------------------------------------------
# 跨 seed 置信带
# --------------------------------------------------------------------------

def cross_seed_band(evals: pd.DataFrame, task: str) -> pd.DataFrame:
    """按 timesteps 对齐多 seed：均值/标准差/样本数 + t 分布 95% 置信带。

    n_seeds<2 的时点置信带为 NaN。
    """
    df = evals[evals["task"] == task]
    d = pd.DataFrame(
        {
            "timesteps": pd.to_numeric(df["timesteps"], errors="coerce"),
            "mean_reward": pd.to_numeric(df["mean_reward"], errors="coerce"),
        }
    ).dropna()
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("timesteps")["mean_reward"]
    agg = g.agg(["mean", "std", "count"]).reset_index()
    agg.columns = ["timesteps", "mean", "std", "n_seeds"]
    agg["task"] = task

    n = agg["n_seeds"].to_numpy()
    tval = np.full(len(n), np.nan)
    sem = np.full(len(n), np.nan)
    valid = n >= 2
    tval[valid] = stats.t.ppf(0.975, n[valid] - 1)
    sem[valid] = agg["std"].to_numpy()[valid] / np.sqrt(n[valid])
    agg["ci_low"] = agg["mean"] - tval * sem
    agg["ci_high"] = agg["mean"] + tval * sem
    return agg


# --------------------------------------------------------------------------
# 绘图
# --------------------------------------------------------------------------

def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_run_fit(evals: pd.DataFrame, fit: dict, out_dir: pathlib.Path) -> pathlib.Path | None:
    """保存单 run 学习曲线图：原始点、包络、拟合曲线、R_inf 水平线。"""
    if fit is None:
        return None
    plt = _plt()
    s = _series(evals, fit["task"], fit["seed"])
    t = s["t"].to_numpy(dtype=float)
    y = s["y"].to_numpy(dtype=float)

    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y, ".", alpha=0.4, ms=3, label="raw")
    ax.plot(t, np.maximum.accumulate(y), "-", alpha=0.7, label="cummax envelope")
    t_fit = np.linspace(t[t > 0].min(), t.max(), 200)
    if fit["model"] == "power":
        y_fit = fit["R_inf"] - fit["A"] * t_fit ** (-fit["alpha"])
    else:
        y_fit = fit["R_inf"] - fit["A"] * np.exp(-fit["k"] * t_fit)
    ax.plot(t_fit, y_fit, "--", label=f"{fit['model']} fit (R2={fit['r2']})")
    ax.axhline(fit["R_inf"], color="red", linestyle=":", label=f"R_inf={fit['R_inf']}")
    ax.set_xlabel("timesteps")
    ax.set_ylabel("mean_reward")
    ax.set_title(f"{fit['task']}/{fit['seed']}")
    ax.legend(fontsize=8)
    path = out_dir / f"run_fit_{fit['task']}_{fit['seed']}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def plot_task_band(evals: pd.DataFrame, task: str, out_dir: pathlib.Path) -> pathlib.Path | None:
    """保存跨 seed 置信带图（95% CI + 各 seed 原始曲线）。"""
    band = cross_seed_band(evals, task)
    if band is None or band.empty:
        return None
    plt = _plt()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(band["timesteps"], band["mean"], "-o", ms=3, label="mean")
    ax.fill_between(
        band["timesteps"], band["ci_low"], band["ci_high"], alpha=0.25, label="95% CI (t)"
    )
    for seed, g in evals[evals["task"] == task].groupby("seed"):
        ax.plot(
            pd.to_numeric(g["timesteps"], errors="coerce"),
            pd.to_numeric(g["mean_reward"], errors="coerce"),
            ".", alpha=0.35, ms=3, label=seed,
        )
    ax.set_xlabel("timesteps")
    ax.set_ylabel("mean_reward")
    ax.set_title(f"{task} (cross-seed)")
    ax.legend(fontsize=8)
    path = out_dir / f"band_{task}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _pairs(evals: pd.DataFrame, task: str | None) -> list[tuple[str, str]]:
    keys = evals[["task", "seed"]].drop_duplicates()
    if task:
        keys = keys[keys["task"] == task]
    return sorted(zip(keys["task"], keys["seed"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 学习曲线拟合（B 方案）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--task", default=None, help="只拟合指定任务（默认全部）")
    parser.add_argument("--validate", action="store_true", help="completed run 外推 vs 实际末值")
    parser.add_argument("--today", default=None, help="日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖输出目录（默认 config.modeling_dir）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tables = load_tables(cfg)
    evals = tables.get("eval_points")
    if evals is None or evals.empty:
        raise SystemExit("eval_points 无数据，先运行采集")
    today = args.today or _Date.today().isoformat()
    out_dir = resolve_out_dir(cfg, args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    fits = [f for f in (fit_learning_curve(evals, t, s) for t, s in _pairs(evals, args.task)) if f]
    fits_df = pd.DataFrame(fits)
    fits_path = out_dir / f"curve_fits_{today}.csv"
    fits_df.to_csv(fits_path, index=False, encoding="utf-8-sig")
    print(f"[go2w-quant] 学习曲线拟合 {today}：{len(fits)}/{len(_pairs(evals, args.task))} run 拟合成功")
    if len(fits_df):
        print(fits_df[["task", "seed", "model", "R_inf", "r2", "reliable"]].to_string(index=False))
    print(f"  输出: {fits_path}")

    plots_dir = out_dir / "plots"
    n_plots = 0
    for fit in fits:
        if plot_run_fit(evals, fit, plots_dir):
            n_plots += 1
    for task in sorted(evals["task"].unique()):
        if args.task and task != args.task:
            continue
        if plot_task_band(evals, task, plots_dir):
            n_plots += 1
    print(f"  图表: {n_plots} 张 -> {plots_dir}")

    if args.validate:
        runs_df = tables.get("runs")
        if runs_df is None:
            raise SystemExit("--validate 需要 runs 表")
        rows: list[dict] = []
        completed = runs_df[runs_df["completed"].astype(bool)]
        for _, r in completed.iterrows():
            task, seed = r["task"], r["seed"]
            sub = evals[(evals["task"] == task) & (evals["seed"] == seed)]
            if len(sub) < MIN_POINTS:
                continue
            actual = float(pd.to_numeric(sub["mean_reward"], errors="coerce").iloc[-1])
            total = (
                float(r["total_steps"])
                if pd.notna(r.get("total_steps"))
                else float(sub["timesteps"].max())
            )
            row: dict = {"task": task, "seed": seed, "total_steps": total,
                         "actual_final_reward": round(actual, 4)}
            for frac in VALIDATE_FRACTIONS:
                ext = extrapolate_R_inf(sub, frac, total_steps=total)
                key = f"p{int(frac * 100)}"
                row[f"R_inf_{key}"] = round(ext["R_inf"], 4) if ext else None
                row[f"err_{key}"] = round(ext["R_inf"] - actual, 2) if ext else None
                row[f"reliable_{key}"] = ext["reliable"] if ext else None
            rows.append(row)
        val_df = pd.DataFrame(rows)
        val_path = out_dir / f"validate_{today}.csv"
        val_df.to_csv(val_path, index=False, encoding="utf-8-sig")
        print(f"[validate] completed run 外推 vs 实际末值（{len(val_df)} 个 run）:")
        print(val_df.to_string(index=False))
        print(f"  输出: {val_path}")


if __name__ == "__main__":
    main()
