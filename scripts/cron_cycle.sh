#!/usr/bin/env bash
# 定时一轮：采集 -> 量化日报（每日一次）-> 提交并推送数据集与报告。用 flock 防并发。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
LOCK="${TMPDIR:-/tmp}/go2w_quant_cycle.lock"

exec 9>"$LOCK"
flock -n 9 || exit 0

if [ ! -x "$PY" ]; then
  python3 -m venv "$REPO/.venv"
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r "$REPO/requirements.txt"
fi

mkdir -p "$REPO/data"
"$PY" "$REPO/collector.py" --config "$REPO/config.json" \
  >> "$REPO/data/collect.log" 2>&1 || true

# 量化风控日报：每日一次（用日期标记防重复，避免每 15 分钟重跑）
QUANT_MARKER="$REPO/data/.quant_last_date"
TODAY="$(date +%F)"
if [ ! -f "$QUANT_MARKER" ] || [ "$(cat "$QUANT_MARKER" 2>/dev/null)" != "$TODAY" ]; then
  "$PY" "$REPO/quant.py" --config "$REPO/config.json" \
    >> "$REPO/data/quant.log" 2>&1 || true
  # B 方案：每日一次特征固化（标签/样本随采集增长后由 baseline.py 手动/定时评估）
  "$PY" "$REPO/modeling.py" --config "$REPO/config.json" \
    >> "$REPO/data/quant.log" 2>&1 || true
  # B 方案：每日一次规则止损回测（赔率表，data/modeling/rule_backtest_*.csv/md）
  "$PY" "$REPO/backtest_rules.py" --config "$REPO/config.json" \
    >> "$REPO/data/quant.log" 2>&1 || true
  # B 方案：标签富化 + 数据筛选（分层建模数据，screened/anomaly_archive/screening_summary）
  "$PY" "$REPO/label_enrichment.py" --config "$REPO/config.json" \
    >> "$REPO/data/quant.log" 2>&1 || true
  "$PY" "$REPO/data_screening.py" --config "$REPO/config.json" \
    >> "$REPO/data/quant.log" 2>&1 || true
  printf '%s\n' "$TODAY" > "$QUANT_MARKER"
fi

bash "$REPO/scripts/sync_github.sh" --once \
  >> "$REPO/data/sync.log" 2>&1 || true