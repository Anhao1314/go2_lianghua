#!/usr/bin/env bash
# 定时一轮：采集 -> 提交并推送数据集。用 flock 防并发。
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
bash "$REPO/scripts/sync_github.sh" --once \
  >> "$REPO/data/sync.log" 2>&1 || true
