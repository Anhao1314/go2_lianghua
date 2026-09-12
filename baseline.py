"""基线模型：事后验收分类（verdict）与训练耗时回归（duration_seconds）。

数据量门槛（当前样本极少，结果仅作基线记录，不作为训练决策依据）：
  - verdict 分类：正负样本各 >= MIN_PER_CLASS 才启用留一交叉验证（LOO），
    否则只打印标签分布与单变量相关性；
  - success_rate / duration 回归：有效样本 >= MIN_REGRESSION 才启用 LOO，
    否则只打印单变量相关性。
当前特征含最终验收信息，不用于在线早停或 ETA 预测。

用法：
  python baseline.py --config config.json                 # 用最新数据集
  python baseline.py --dataset data/modeling/dataset_YYYY-MM-DD.csv
  python baseline.py --out data/modeling                  # 覆盖报告目录
"""

from __future__ import annotations

import argparse
import pathlib
from datetime import date as _Date

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import subprocess

from collector import PROJECT_ROOT, load_config
from modeling import Y_COLUMNS, resolve_out_dir

MIN_PER_CLASS = 2
MIN_REGRESSION = 6
TOP_CORR = 8

# y 与特征同源的泄漏列：duration_seconds 由快照时间跨度推算，
# time_span_minutes 是同一量的不同单位；snapshot_count / swap_percent_max
# 是随训练时长机械增长的累计/覆盖型代理（单变量 |r|>0.9），回归时一并剔除
LEAKED_FEATURES: dict[str, tuple[str, ...]] = {
    "duration_seconds": ("time_span_minutes", "snapshot_count", "swap_percent_max"),
}


def load_latest_dataset(
    cfg: dict, dataset: str | None, screened: bool = False
) -> tuple[pd.DataFrame, pathlib.Path]:
    out_dir = resolve_out_dir(cfg, None)
    if dataset:
        path = pathlib.Path(dataset)
        if not path.exists():
            raise SystemExit(f"数据集不存在: {path}")
    else:
        pattern = "screened_dataset_*.csv" if screened else "dataset_*.csv"
        hint = ("screened_dataset_*.csv（请先运行 modeling.py --screened）" if screened
                else "dataset_*.csv（请先运行 modeling.py）")
        candidates = sorted(out_dir.glob(pattern))
        if not candidates:
            raise SystemExit(f"未找到数据集: {out_dir / pattern}（{hint}）")
        path = candidates[-1]
    return pd.read_csv(path), path


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """X：除 task/seed/y 外的全部数值特征；全空列丢弃。"""
    x_cols = [c for c in df.columns if c not in ("task", "seed") + tuple(Y_COLUMNS)]
    X = df[x_cols].apply(pd.to_numeric, errors="coerce")
    return X.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")


def univariate_corrs(X: pd.DataFrame, y: pd.Series, top: int = TOP_CORR) -> pd.DataFrame:
    """单变量 Pearson 相关（仅信息性参考，不参与模型决策）。"""
    rows: list[dict] = []
    for col in X.columns:
        m = X[col].notna() & y.notna()
        if m.sum() < 3:
            continue
        x = X.loc[m, col]
        yv = y.loc[m]
        if x.std(ddof=0) == 0 or yv.std(ddof=0) == 0:
            continue  # 常量列无法计算相关性
        r = x.corr(yv)
        if pd.isna(r):
            continue
        rows.append({"feature": col, "n": int(m.sum()), "r": round(float(r), 3)})
    out = pd.DataFrame(rows)
    if len(out):
        out = out.reindex(out["r"].abs().sort_values(ascending=False).index).head(top)
    return out


def _model_pipeline(estimator):
    """预处理仅在每折训练样本上拟合；全空训练列以零填充。"""
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("model", estimator),
    ])


def _valid_fold(X, train_idx):
    return bool(X.iloc[train_idx].notna().any().any())


def verdict_baseline(df: pd.DataFrame, X: pd.DataFrame) -> dict:
    """事后验收分类基线：pass=1 / fail=0，留一交叉验证 vs 多数类 Dummy。"""
    X = X.replace([np.inf, -np.inf], np.nan)
    y = df["verdict"].map({"pass": 1, "fail": 0}).dropna()
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    out: dict = {"target": "verdict", "n_pos": n_pos, "n_neg": n_neg}
    if len(y) < 2 * MIN_PER_CLASS or min(n_pos, n_neg) < MIN_PER_CLASS:
        out["status"] = "insufficient"
        return out

    Xy = X.loc[y.index]
    if not Xy.shape[1]:
        out["status"] = "insufficient"
        out["reason"] = "有效样本内无可用特征"
        return out
    Xs, yv, cols = Xy, y.to_numpy(dtype=float), list(Xy.columns)

    model = _model_pipeline(LogisticRegression(max_iter=2000))
    dummy = DummyClassifier(strategy="most_frequent")
    loo = LeaveOneOut()
    y_pred: list[int] = []
    y_dummy: list[int] = []
    for train_idx, test_idx in loo.split(Xs):
        if not _valid_fold(Xs, train_idx):
            out.update(status="insufficient", reason="某折训练样本无可用特征")
            return out
        model.fit(Xs.iloc[train_idx], yv[train_idx].astype(int))
        dummy.fit(Xs.iloc[train_idx], yv[train_idx].astype(int))
        y_pred.append(int(model.predict(Xs.iloc[test_idx])[0]))
        y_dummy.append(int(dummy.predict(Xs.iloc[test_idx])[0]))
    out.update(
        {
            "status": "ok",
            "accuracy": round(accuracy_score(yv.astype(int), y_pred), 3),
            "f1": round(f1_score(yv.astype(int), y_pred, zero_division=0), 3),
            "dummy_accuracy": round(accuracy_score(yv.astype(int), y_dummy), 3),
            "n_features": len(cols),
        }
    )
    return out


def regression_baseline(df: pd.DataFrame, X: pd.DataFrame, target: str) -> dict:
    """回归基线：LOO 线性回归 vs 中位数 Dummy，输出 R2/MAE 与特征重要性。"""
    X = X.replace([np.inf, -np.inf], np.nan)
    y = pd.to_numeric(df[target], errors="coerce")
    mask = y.notna() & np.isfinite(y)
    n = int(mask.sum())
    out: dict = {"target": target, "n": n}
    if n < MIN_REGRESSION:
        out["status"] = "insufficient"
        return out

    Xy = X.loc[mask].drop(
        columns=[c for c in LEAKED_FEATURES.get(target, ()) if c in X.columns]
    )
    if not Xy.shape[1]:
        out["status"] = "insufficient"
        out["reason"] = "有效样本内无可用特征"
        return out
    Xs, yv, cols = Xy, y[mask].to_numpy(dtype=float), list(Xy.columns)

    model = _model_pipeline(LinearRegression())
    dummy = DummyRegressor(strategy="median")
    loo = LeaveOneOut()
    y_pred: list[float] = []
    y_dummy: list[float] = []
    for train_idx, test_idx in loo.split(Xs):
        if not _valid_fold(Xs, train_idx):
            out.update(status="insufficient", reason="某折训练样本无可用特征")
            return out
        model.fit(Xs.iloc[train_idx], yv[train_idx])
        dummy.fit(Xs.iloc[train_idx], yv[train_idx])
        y_pred.append(float(model.predict(Xs.iloc[test_idx])[0]))
        y_dummy.append(float(dummy.predict(Xs.iloc[test_idx])[0]))

    model.fit(Xs, yv)  # 全量拟合用于特征重要性（标准化系数）
    coefs = pd.Series(
        model.named_steps["model"].coef_, index=cols, name="coef"
    ).abs().sort_values(ascending=False).head(TOP_CORR)
    out.update(
        {
            "status": "ok",
            "r2": round(float(r2_score(yv, y_pred)), 3),
            "mae": round(float(mean_absolute_error(yv, y_pred)), 1),
            "dummy_mae": round(float(mean_absolute_error(yv, y_dummy)), 1),
            "n_features": len(cols),
            "top_features": {
                k: round(float(v), 3) for k, v in coefs.items()
            },
        }
    )
    return out


def run_baselines(df: pd.DataFrame) -> dict:
    X = feature_matrix(df)
    results: dict = {"n_runs": int(len(df)), "n_features": int(X.shape[1])}
    results["verdict"] = verdict_baseline(df, X)
    for target in ("success_rate", "duration_seconds"):
        results[target] = regression_baseline(df, X, target)
    # 单变量相关性（信息性参考）
    corrs: dict[str, pd.DataFrame] = {}
    for target in ("verdict", "success_rate", "duration_seconds"):
        if target == "verdict":
            y = df["verdict"].map({"pass": 1, "fail": 0})
        else:
            y = pd.to_numeric(df[target], errors="coerce")
        corrs[target] = univariate_corrs(X, y)
    results["corrs"] = corrs
    return results


def code_revision() -> str:
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True)
        return rev + (" (dirty)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render_markdown(res: dict, dataset_path: pathlib.Path) -> str:
    lines = [
        "# go2w-quant 基线模型报告",
        "",
        f"- 数据集: `{dataset_path.name}`（{res['n_runs']} runs，{res['n_features']} 特征）",
        f"- 生成时间: {_Date.today().isoformat()}",
        f"- 代码版本: {code_revision()}",
        "- 评估方式: 留一交叉验证；填充和标准化仅拟合每折训练样本。",
        "- 当前为全程数据事后分析，含最终验收特征；不证明在线预测或跨任务泛化。",
        "- 特征重要性来自单独全量拟合，不属于交叉验证结果。",
        "",
        "> 当前样本量及验证范围有限，结果只作事后分析与基线记录，不作为训练决策依据。",
        "",
        "## 一、verdict 分类（事后分析）",
        "",
    ]
    v = res["verdict"]
    lines.append(f"- 标签分布：pass {v['n_pos']} / fail {v['n_neg']}")
    if v["status"] == "ok":
        lines += [
            f"- LOO 逻辑回归：accuracy {v['accuracy']}，f1 {v['f1']}",
            f"- 多数类 Dummy：accuracy {v['dummy_accuracy']}",
            f"- 使用特征数：{v['n_features']}",
        ]
    else:
        lines.append(f"- 不可评估：{v.get('reason', '正负样本不足')}，未训练模型。")
    lines += ["", "## 二、回归（success_rate / duration_seconds）", ""]
    for t in ("success_rate", "duration_seconds"):
        r = res[t]
        lines.append(f"### {t}（有效样本 {r['n']}）")
        if r["status"] == "ok":
            lines += [
                f"- LOO 线性回归：R2 {r['r2']}，MAE {r['mae']}",
                f"- 中位数 Dummy：MAE {r['dummy_mae']}",
                f"- 使用特征数：{r['n_features']}；重要特征："
                + ", ".join(f"{k}({v})" for k, v in r["top_features"].items()),
            ]
        else:
            lines.append(f"- 不可评估：{r.get('reason', '有效样本不足')}，未训练模型。")
        lines.append("")
    lines.append("## 三、单变量相关性 Top（信息性参考）")
    for t, corr in res["corrs"].items():
        lines.append(f"\n### {t}")
        if len(corr):
            for _, row in corr.iterrows():
                lines.append(f"- {row['feature']}: r={row['r']}（n={row['n']}）")
        else:
            lines.append("- 无可计算相关性的特征。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 基线模型（B 方案）")
    parser.add_argument("--config", default=None)
    parser.add_argument("--dataset", default=None, help="指定数据集 CSV（默认最新）")
    parser.add_argument("--out", default=None, help="覆盖报告目录（默认 config.modeling_dir）")
    parser.add_argument("--screened", action="store_true",
                        help="使用筛选数据集（screened_dataset_*.csv）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    df, dataset_path = load_latest_dataset(cfg, args.dataset, screened=args.screened)
    res = run_baselines(df)

    out_dir = resolve_out_dir(cfg, args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_screened" if args.screened else ""
    md_path = out_dir / f"baseline_fold_safe_{_Date.today().isoformat()}{suffix}.md"
    md_path.write_text(render_markdown(res, dataset_path), encoding="utf-8")

    print(f"[go2w-quant] 基线模型：{res['n_runs']} runs × {res['n_features']} 特征（{dataset_path.name}）")
    v = res["verdict"]
    print(f"  verdict: pass {v['n_pos']} / fail {v['n_neg']} → "
          f"{'LOO accuracy ' + str(v.get('accuracy')) if v['status'] == 'ok' else '样本不足，未训练'}")
    for t in ("success_rate", "duration_seconds"):
        r = res[t]
        if r["status"] == "ok":
            print(f"  {t}: R2 {r['r2']} / MAE {r['mae']} / Dummy MAE {r['dummy_mae']}（n={r['n']}）")
        else:
            print(f"  {t}: 样本不足（n={r['n']}，门槛 ≥{MIN_REGRESSION}），未训练")
    print(f"  报告: {md_path}")


if __name__ == "__main__":
    main()
