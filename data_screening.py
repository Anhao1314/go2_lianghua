"""数据筛选与异常归档：为建模数据集做客观、可复现的分层（B 方案）。

原则（参考梁文锋/幻方量化）：筛选是分层不是删除——
- clean 数据用于训练，anomaly 数据用于鲁棒性测试，full 数据用于最终回测；
- 绝不只在 screened 数据上报告指标：始终对比 screened 训练 vs full 训练，
  且测试集永远是 FULL（否则会掩盖幸存者偏差）。

筛选规则（只用训练过程可观测信号，不用 verdict/reports 等未来信息）：
  1. 足够评估点：eval_points 数 >= min_eval_points；
  2. 非平凡训练：max(最后 eval timesteps, total_steps) >= min_total_steps；
  3. 无解析异常：factors 清洗后的 approx_kl_last < max_kl
     （修正 1：用 factors.run_factors 的清洗值，不用原始 tb_points——
     原始日志可能出现 122376 这类脏值，清洗后 balance/seed00 可通过），
     且 eval mean_reward 无 NaN；
  4. 曲线可辨识：mean_reward 标准差 > min_reward_std（n<2 时不适用，视为通过）。

classify（修正 2：异常优先）：rule3/4 任一失败 -> anomalous（即使 1/2 也失败）；
仅 rule1/2 失败 -> insufficient；全过 -> good。

回测对比（修正 3）：Config A = screened 训练 + full 测试（逐样本 LOO，
任一测试样本不在自身训练折内，修复训练/测试重叠导致的虚高 R2）；
Config B = full 训练 + full 测试（baseline LOO）；A 差于 B -> 幸存者偏差警告；
有标签样本 <10 -> 标注"框架验证，不具统计显著性"。

本模块不修改 v2 风控/回测管线：factors/quant/backtest_* 继续使用全量数据。
"""

from __future__ import annotations

import argparse
import pathlib
from datetime import date as _Date
from typing import Any

import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

import baseline
from collector import PROJECT_ROOT, load_config
from factors import run_factors
from modeling import Y_COLUMNS, resolve_out_dir
from quant import load_tables

RULE_NAMES = ("rule1", "rule2", "rule3", "rule4")


# --------------------------------------------------------------------------
# 筛选规则（纯函数，无 I/O）
# --------------------------------------------------------------------------

def screening_checks(
    evals: pd.DataFrame,
    tbs: pd.DataFrame | None,
    runs_row: dict[str, Any] | None,
    cfg: dict[str, Any],
    factors_f: dict[str, Any] | None = None,
) -> tuple[dict[str, bool], list[str]]:
    """评估单条 run 的 4 条筛选规则；返回 (passed, fail_reasons)。

    factors_f 必须是 factors.run_factors 的产物（approx_kl_last 已按
    (0,1] 区间清洗）。绝不读取 verdict/reports 等未来信息。
    """
    sc = cfg.get("screening") or {}
    min_points = int(sc.get("min_eval_points", 10))
    min_steps = float(sc.get("min_total_steps", 500000))
    max_kl = float(sc.get("max_kl", 1.0))
    min_std = float(sc.get("min_reward_std", 1.0))

    passed: dict[str, bool] = {}
    reasons: list[str] = []

    # rule1: 足够评估点
    n = 0 if evals is None or evals.empty else len(evals)
    ok1 = n >= min_points
    passed["rule1"] = ok1
    if not ok1:
        reasons.append(f"rule1: eval 点数 {n} < {min_points}")

    # rule2: 非平凡训练（观测窗口与目标总步数取最大）
    last_eval = 0.0
    if evals is not None and len(evals):
        ts = pd.to_numeric(evals["timesteps"], errors="coerce").dropna()
        if len(ts):
            last_eval = float(ts.max())
    total = None
    if runs_row is not None:
        total = _to_float(runs_row.get("total_steps"))
    span = max(last_eval, total or 0.0)
    ok2 = span >= min_steps
    passed["rule2"] = ok2
    if not ok2:
        reasons.append(f"rule2: 训练规模 max(last_eval={last_eval:.0f}, total={total}) "
                       f"< {min_steps:.0f}")

    # rule3: 无解析异常（factors 清洗后的 approx_kl；eval 无 NaN）
    kl = (factors_f or {}).get("approx_kl_last")
    ok3a = kl is None or float(kl) < max_kl
    ok3b = True
    if evals is not None and len(evals):
        rw = pd.to_numeric(evals["mean_reward"], errors="coerce")
        ok3b = bool(rw.notna().all())
    ok3 = ok3a and ok3b
    passed["rule3"] = ok3
    if not ok3:
        if not ok3a:
            reasons.append(f"rule3: 清洗后 approx_kl_last={kl} >= {max_kl}")
        if not ok3b:
            reasons.append("rule3: eval mean_reward 存在 NaN")

    # rule4: 曲线可辨识（n<2 时无法计算标准差，不适用视为通过；
    #        数量不足由 rule1 负责，避免误标 anomalous）
    std = float("nan")
    if evals is not None and len(evals) >= 2:
        rw = pd.to_numeric(evals["mean_reward"], errors="coerce").dropna()
        if len(rw) >= 2:
            std = float(rw.std(ddof=0))
    if evals is None or len(evals) < 2:
        ok4 = True
    else:
        ok4 = bool((not pd.isna(std)) and std > min_std)
    passed["rule4"] = ok4
    if not ok4:
        if not pd.isna(std):
            reasons.append(f"rule4: mean_reward 标准差 {std:.3f} <= {min_std}（曲线不可辨识）")
        else:
            reasons.append("rule4: mean_reward 有效值不足无法计算标准差")

    return passed, reasons


def classify(passed: dict[str, bool]) -> str:
    """修正 2：rule3/4 任一失败 -> anomalous（优先）；仅 1/2 失败 -> insufficient。"""
    if not passed.get("rule3", True) or not passed.get("rule4", True):
        return "anomalous"
    if not passed.get("rule1", True) or not passed.get("rule2", True):
        return "insufficient"
    return "good"


# --------------------------------------------------------------------------
# run 级筛选
# --------------------------------------------------------------------------

def screen_run(
    tables: dict[str, pd.DataFrame], task: str, seed: str, cfg: dict[str, Any]
) -> dict[str, Any]:
    """组合：factors 清洗值 + 规则评估 + 分类。返回单 run 筛选结果。"""
    f = run_factors(task, seed, tables, cfg)
    evals = _filter(tables.get("eval_points"), task, seed)
    tbs = _filter(tables.get("tb_points"), task, seed)
    runs_row = _row(tables.get("runs"), task, seed)
    passed, reasons = screening_checks(evals, tbs, runs_row, cfg, factors_f=f)
    quality = classify(passed)
    return {
        "task": task,
        "seed": seed,
        "data_quality": quality,
        "passed": passed,
        "fail_reasons": ";".join(reasons),
        "verdict": (runs_row or {}).get("verdict") if runs_row else None,
        "eval_point_count": 0 if evals is None or evals.empty else int(len(evals)),
    }


# --------------------------------------------------------------------------
# 全量 vs 筛选回测对比（修正 3：测试集永远是 full）
# --------------------------------------------------------------------------

def _to_float(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _config_a_splits(
    test_df: pd.DataFrame, screened_df: pd.DataFrame
) -> list[tuple[tuple[str, str], set[tuple[str, str]]]]:
    """Config A 逐样本留一折：测试样本 i 的训练集 = screened 去掉 {i}（若 i 在 screened 中），
    否则训练集 = 全部 screened。保证任何测试样本都不在自身训练折内（无泄漏）。"""
    screened_keys = {
        (str(a), str(b)) for a, b in zip(screened_df["task"], screened_df["seed"])
    }
    splits: list[tuple[tuple[str, str], set[tuple[str, str]]]] = []
    for _, row in test_df.iterrows():
        key = (str(row["task"]), str(row["seed"]))
        train_keys = screened_keys - {key} if key in screened_keys else set(screened_keys)
        splits.append((key, train_keys))
    return splits


def _regression_a(train_df: pd.DataFrame, test_df: pd.DataFrame, target: str) -> dict:
    """Config A：screened 训练线性回归，full 测试（逐样本 LOO，无训练/测试重叠）。

    对 full 中每个样本 i：i 在 screened 中则训练集 = screened 去掉 {i}，否则 = 全部 screened；
    逐折独立做中位数填充与标准化后仅预测 i，汇总全部预测算 R2/MAE。
    训练折有效 y <3 的折跳过；可评估折 <2 时视为样本不足。
    """
    leaked = baseline.LEAKED_FEATURES.get(target, ())
    x_cols = [c for c in baseline.feature_matrix(train_df).columns if c not in leaked]
    common = [c for c in x_cols if c in test_df.columns]
    y_te = pd.to_numeric(test_df[target], errors="coerce")
    te_ok = y_te.notna()
    if not len(common) or int(te_ok.sum()) < 3:
        return {"status": "insufficient", "n_train": 0, "n_test": int(te_ok.sum())}
    valid_test = test_df.loc[te_ok]
    y_tr_all = pd.to_numeric(train_df[target], errors="coerce")
    n_pool = int(y_tr_all.notna().sum())
    y_true: list[float] = []
    y_pred: list[float] = []
    for (test_key, train_keys), (idx, row) in zip(
            _config_a_splits(valid_test, train_df), valid_test.iterrows()):
        mask = [(str(a), str(b)) in train_keys
                for a, b in zip(train_df["task"], train_df["seed"])]
        fold = train_df.loc[mask]
        y_tr = pd.to_numeric(fold[target], errors="coerce")
        tr_ok = y_tr.notna()
        if int(tr_ok.sum()) < 3:
            continue
        Xtr = fold.loc[tr_ok, common].apply(pd.to_numeric, errors="coerce")
        med = Xtr.median()
        cols = [c for c in Xtr.columns if pd.notna(med.get(c))]
        if not cols:
            continue
        filled = Xtr.loc[:, cols].fillna(med[cols]).to_numpy()
        scaler = StandardScaler().fit(filled)
        model = LinearRegression().fit(scaler.transform(filled), y_tr[tr_ok])
        xte = row[cols].apply(pd.to_numeric, errors="coerce").fillna(med[cols])
        y_true.append(float(y_te.loc[idx]))
        y_pred.append(float(model.predict(
            scaler.transform(xte.to_numpy().reshape(1, -1)))[0]))
    if len(y_true) < 2:
        return {"status": "insufficient", "n_train": n_pool, "n_test": len(y_true)}
    return {
        "status": "ok",
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 1),
        "n_train": n_pool,
        "n_test": len(y_true),
    }


def _verdict_a(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    """Config A：screened 训练逻辑回归，full 测试（逐样本 LOO，无训练/测试重叠）。

    折内门禁：训练标签 >=4 且正负样本各 >=2，不满足则跳过该折；
    可评估折 <2 时视为样本不足。
    """
    y_te = test_df["verdict"].map({"pass": 1, "fail": 0}).dropna()
    y_tr_all = train_df["verdict"].map({"pass": 1, "fail": 0}).dropna()
    n_pos = int((y_tr_all == 1).sum())
    n_neg = int((y_tr_all == 0).sum())
    if len(y_te) < 2:
        return {"status": "insufficient", "n_train": int(len(y_tr_all)),
                "n_test": int(len(y_te)), "n_pos": n_pos, "n_neg": n_neg}
    x_cols = [c for c in baseline.feature_matrix(train_df).columns]
    common = [c for c in x_cols if c in test_df.columns and c in train_df.columns]
    if not common:
        return {"status": "insufficient", "n_train": int(len(y_tr_all)),
                "n_test": int(len(y_te)), "n_pos": n_pos, "n_neg": n_neg}
    valid_test = test_df.loc[y_te.index]
    y_true: list[int] = []
    y_pred: list[int] = []
    for (test_key, train_keys), (idx, row) in zip(
            _config_a_splits(valid_test, train_df), valid_test.iterrows()):
        mask = [(str(a), str(b)) in train_keys
                for a, b in zip(train_df["task"], train_df["seed"])]
        fold = train_df.loc[mask]
        y_tr = fold["verdict"].map({"pass": 1, "fail": 0}).dropna()
        n_pos_f = int((y_tr == 1).sum())
        n_neg_f = int((y_tr == 0).sum())
        if len(y_tr) < 4 or min(n_pos_f, n_neg_f) < 2:
            continue
        Xtr = fold.loc[y_tr.index, common].apply(
            pd.to_numeric, errors="coerce").fillna(0).to_numpy()
        scaler = StandardScaler().fit(Xtr)
        model = LogisticRegression(max_iter=1000).fit(scaler.transform(Xtr), y_tr)
        xte = row[common].apply(pd.to_numeric, errors="coerce").fillna(0)
        y_true.append(int(y_te.loc[idx]))
        y_pred.append(int(model.predict(
            scaler.transform(xte.to_numpy().reshape(1, -1)))[0]))
    if len(y_true) < 2:
        return {"status": "insufficient", "n_train": int(len(y_tr_all)),
                "n_test": len(y_true), "n_pos": n_pos, "n_neg": n_neg}
    acc = sum(a == b for a, b in zip(y_true, y_pred)) / len(y_true)
    return {"status": "ok", "accuracy": round(acc, 4),
            "n_train": int(len(y_tr_all)), "n_test": len(y_true),
            "n_pos": n_pos, "n_neg": n_neg}


def compare_full_vs_screened(full_df: pd.DataFrame, screened_df: pd.DataFrame) -> dict:
    """修正 3：A=screened 训练+full 测试；B=full 训练+full 测试（LOO）。"""
    n_dur = int(pd.to_numeric(full_df["duration_seconds"], errors="coerce").notna().sum())
    b_dur = baseline.run_baselines(full_df)["duration_seconds"]
    b_verdict = baseline.run_baselines(full_df)["verdict"]
    a_dur = _regression_a(screened_df, full_df, "duration_seconds")
    a_verdict = _verdict_a(screened_df, full_df)
    significant = n_dur >= 10
    # 幸存者偏差：A 在 full 测试上差于 B（R2 更低）
    warning = False
    if a_dur["status"] == "ok" and b_dur["status"] == "ok":
        warning = a_dur["r2"] < b_dur["r2"]
    return {
        "n_labeled_duration": n_dur,
        "significant": significant,
        "survivorship_warning": warning,
        "duration": {"A": a_dur, "B": {
            "status": b_dur["status"],
            "r2": b_dur.get("r2"), "mae": b_dur.get("mae"),
            "n_train": b_dur.get("n"), "n_test": b_dur.get("n"),
        }},
        "verdict": {"A": a_verdict, "B": {
            "status": b_verdict["status"],
            "accuracy": b_verdict.get("accuracy"),
            "n_pos": b_verdict["n_pos"], "n_neg": b_verdict["n_neg"],
            "n_train": b_verdict.get("n_pos", 0) + b_verdict.get("n_neg", 0),
            "n_test": b_verdict.get("n_pos", 0) + b_verdict.get("n_neg", 0),
        }},
    }
# --------------------------------------------------------------------------
# 输出与 CLI
# --------------------------------------------------------------------------

def _filter(df: pd.DataFrame | None, task: str, seed: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df["task"] == task) & (df["seed"] == seed)]


def _row(runs_df: pd.DataFrame | None, task: str, seed: str) -> dict[str, Any] | None:
    if runs_df is None or runs_df.empty:
        return None
    rows = runs_df[(runs_df["task"] == task) & (runs_df["seed"] == seed)]
    return rows.iloc[0].to_dict() if len(rows) else None


def run_pairs(tables: dict[str, pd.DataFrame]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    runs = tables.get("runs")
    if runs is not None and len(runs):
        seen.update(zip(runs["task"], runs["seed"]))
    evals = tables.get("eval_points")
    if evals is not None and len(evals):
        seen.update(zip(evals["task"], evals["seed"]))
    return sorted(seen)


def screen_all(tables: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> pd.DataFrame:
    """筛选全部 run，返回逐 run 结果表。"""
    rows = [screen_run(tables, t, s, cfg) for t, s in run_pairs(tables)]
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values(["task", "seed"]).reset_index(drop=True)
    return df


def load_latest_dataset(out_dir: pathlib.Path, prefix: str) -> pd.DataFrame | None:
    candidates = sorted(out_dir.glob(f"{prefix}_*.csv"))
    if not candidates:
        return None
    return pd.read_csv(candidates[-1])


def render_summary(
    today: str,
    screen_df: pd.DataFrame,
    compare: dict[str, Any],
    screened_path: pathlib.Path,
    archive_path: pathlib.Path,
) -> str:
    lines: list[str] = []
    lines.append(f"# go2w-quant 数据筛选报告（分层建模数据）：{today}")
    lines.append("")
    counts = screen_df["data_quality"].value_counts()
    lines.append("## 一、筛选结果概览")
    lines.append("")
    lines.append(f"- 总 run 数：{len(screen_df)}；good {int(counts.get('good', 0))} / "
                 f"insufficient {int(counts.get('insufficient', 0))} / "
                 f"anomalous {int(counts.get('anomalous', 0))}")
    lines.append("")
    lines.append("## 二、逐规则通过率")
    lines.append("")
    lines.append("| 规则 | 说明 | 通过 | 失败 |")
    lines.append("|---|---|---|---|")
    rule_desc = {
        "rule1": "eval 点数 ≥ 阈值",
        "rule2": "训练规模 ≥ 阈值",
        "rule3": "无解析异常（清洗后 KL / NaN）",
        "rule4": "曲线可辨识（std > 阈值）",
    }
    for rule in RULE_NAMES:
        passed = screen_df["passed"].apply(lambda p: p.get(rule, True))
        lines.append(f"| {rule} | {rule_desc[rule]} | {int(passed.sum())} | "
                     f"{int((~passed).sum())} |")
    lines.append("")
    lines.append("## 三、异常/不足 run 归档")
    lines.append("")
    non_good = screen_df[screen_df["data_quality"] != "good"]
    if len(non_good):
        lines.append("| task | seed | 质量 | 失败原因 | verdict | eval 点数 |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in non_good.iterrows():
            lines.append(f"| {r['task']} | {r['seed']} | {r['data_quality']} | "
                         f"{r['fail_reasons']} | {r['verdict']} | {r['eval_point_count']} |")
    else:
        lines.append("（无不合格 run）")
    lines.append("")
    lines.append("## 四、全量 vs 筛选回测对比（测试集 = 全量）")
    lines.append("")
    lines.append("- Config A 采用逐样本留一（LOO）：任一测试样本不在自身训练折内，"
                 "无训练/测试重叠（修复虚高 R2）。")
    lines.append("")
    if not compare["significant"]:
        lines.append("> ⚠️ 有标签样本不足（n<10），以下对比仅作框架验证，不具统计显著性。")
    lines.append("")
    lines.append("### duration_seconds 回归")
    lines.append("")
    lines.append("| 配置 | 训练集 | 测试集 | R2 | MAE | 样本(n_train/n_test) |")
    lines.append("|---|---|---|---|---|---|")
    a, b = compare["duration"]["A"], compare["duration"]["B"]
    lines.append("| A | screened | **full**（LOO 无泄漏） | {} | {} | {} |".format(
        a.get("r2", "—") if a["status"] == "ok" else "未训练",
        a.get("mae", "—") if a["status"] == "ok" else "",
        f"{a['n_train']}/{a['n_test']}" if a["status"] == "ok" else
        f"{a['n_train']}/{a['n_test']}"))
    lines.append("| B | full | **full** | {} | {} | {} |".format(
        b.get("r2", "—") if b["status"] == "ok" else "未训练",
        b.get("mae", "—") if b["status"] == "ok" else "",
        f"{b['n_train']}/{b['n_test']}" if b["status"] == "ok" else "—"))
    lines.append("")
    lines.append("### verdict 分类")
    lines.append("")
    va, vb = compare["verdict"]["A"], compare["verdict"]["B"]
    lines.append(f"- A（screened 训练，full 测试 LOO 无泄漏）："
                 f"{'accuracy ' + str(va['accuracy']) if va['status'] == 'ok' else '样本不足未训练'}"
                 f"（训练 pass/fail = {va['n_pos']}/{va['n_neg']}，测试 n={va['n_test']}）")
    lines.append(f"- B（full 训练，full 测试 LOO）："
                 f"{'accuracy ' + str(vb['accuracy']) if vb['status'] == 'ok' else '样本不足未训练'}"
                 f"（pass/fail = {vb['n_pos']}/{vb['n_neg']}）")
    lines.append("")
    if compare["survivorship_warning"]:
        lines.append("## ⚠️ SURVIVORSHIP BIAS WARNING")
        lines.append("")
        lines.append("筛选训练（A）在 full 测试集上的表现差于全量训练（B）："
                     "筛选可能引入幸存者偏差，模型不应只在 clean 数据上评估。")
        lines.append("")
    lines.append("## 五、原则")
    lines.append("")
    lines.append("- 筛选 = 分层，非删除：clean 训练、anomaly 鲁棒性测试、full 最终回测。")
    lines.append("- v2 风控/回测管线（factors/quant/backtest_*）继续使用全量数据，不受筛选影响。")
    lines.append(f"- 输出：{screened_path.name}（good）、{archive_path.name}（非 good 归档）。")
    return "\n".join(lines) + "\n"


def screen_outputs(
    cfg: dict[str, Any], today: str, out_dir: pathlib.Path
) -> dict[str, Any]:
    """完整筛选流程：读表 -> 筛选 -> 归档 -> 对比 -> 写三个输出文件。

    供 CLI 与 modeling.py --screened 复用。
    """
    tables = load_tables(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)

    screen_df = screen_all(tables, cfg)
    good_df = screen_df[screen_df["data_quality"] == "good"]

    # 读全量 dataset（modeling 产物）与富化标签（label_enrichment 产物）
    full_df = load_latest_dataset(out_dir, "dataset")
    enriched = load_latest_dataset(out_dir, "enriched_labels")
    if full_df is None:
        raise SystemExit(f"未找到 dataset_*.csv（请先运行 modeling.py）：{out_dir}")
    if enriched is None:
        raise SystemExit("未找到 enriched_labels_*.csv（请先运行 label_enrichment.py）")

    # screened_dataset = good × 因子 × 富化标签
    good_meta = good_df[["task", "seed", "data_quality", "fail_reasons"]]
    screened = full_df.merge(good_meta, on=["task", "seed"], how="inner")
    if len(enriched):
        screened = screened.merge(enriched, on=["task", "seed"], how="left",
                                  suffixes=("", "_enriched"))
    # 富化列重复时（verdict 等）以 enriched 为准；data_quality 冗余列清理
    for c in ("verdict", "success_rate", "duration_seconds"):
        ec = f"{c}_enriched"
        if ec in screened.columns:
            screened[c] = screened[ec]
            screened = screened.drop(columns=[ec])
    if "data_quality_enriched" in screened.columns:
        screened = screened.drop(columns=["data_quality_enriched"])
    screened = screened.sort_values(["task", "seed"]).reset_index(drop=True)

    # anomaly archive：全部非 good
    archive_cols = ["task", "seed", "data_quality", "fail_reasons", "verdict",
                    "eval_point_count"]
    archive = screen_df[screen_df["data_quality"] != "good"][archive_cols].copy()
    archive["notes"] = "归档供鲁棒性测试，不删除"
    archive = archive.sort_values(["task", "seed"]).reset_index(drop=True)

    screened_path = out_dir / f"screened_dataset_{today}.csv"
    archive_path = out_dir / f"anomaly_archive_{today}.csv"
    summary_path = out_dir / f"screening_summary_{today}.md"
    screened.to_csv(screened_path, index=False, encoding="utf-8-sig")
    archive.to_csv(archive_path, index=False, encoding="utf-8-sig")

    compare = compare_full_vs_screened(full_df, screened)
    summary_path.write_text(
        render_summary(today, screen_df, compare, screened_path, archive_path),
        encoding="utf-8",
    )

    counts = screen_df["data_quality"].value_counts()
    print(f"[data_screening] 数据筛选 {today}")
    print(f"  runs={len(screen_df)}  good={int(counts.get('good', 0))}  "
          f"insufficient={int(counts.get('insufficient', 0))}  "
          f"anomalous={int(counts.get('anomalous', 0))}")
    c = compare
    a_d, b_d = c["duration"]["A"], c["duration"]["B"]
    print(f"  duration A(screened→full LOO): "
          f"{'R2 ' + str(a_d['r2']) if a_d['status'] == 'ok' else '未训练'} | "
          f"B(full→full): "
          f"{'R2 ' + str(b_d['r2']) if b_d['status'] == 'ok' else '未训练'}")
    if c["survivorship_warning"]:
        print("  [!] SURVIVORSHIP BIAS WARNING: 筛选训练在 full 测试上差于全量训练")
    if not c["significant"]:
        print("  注：有标签样本 <10，对比仅框架验证，不具统计显著性")
    print(f"  输出: {screened_path.name} / {archive_path.name} / {summary_path.name}")
    return {
        "screen_df": screen_df,
        "compare": compare,
        "screened_path": screened_path,
        "archive_path": archive_path,
        "summary_path": summary_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="go2w-quant 数据筛选与异常归档")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    parser.add_argument("--today", default=None, help="报告日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--out", default=None, help="覆盖输出目录（默认 config.modeling_dir）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    today = args.today or _Date.today().isoformat()
    out_dir = resolve_out_dir(cfg, args.out)
    screen_outputs(cfg, today, out_dir)


if __name__ == "__main__":
    main()