#!/usr/bin/env bash
# 采集成功后运行每日统一管线；任一步失败不标记、不发布。
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
LOCK="${TMPDIR:-/tmp}/go2w_quant_cycle.lock"
exec 9>"$LOCK"
flock -n 9 || exit 0
mkdir -p "$REPO/data"
trap 'echo "[$(date -Iseconds)] 失败: 行 ${LINENO}，未发布" >> "$REPO/data/cycle.log"' ERR
if [ ! -x "$PY" ]; then
  echo "请先创建 .venv 并安装 requirements.txt" >&2
  exit 1
fi
"$PY" "$REPO/collector.py" >> "$REPO/data/collect.log" 2>&1
MARKER="$REPO/data/.quant_last_date"
TODAY="$(date +%F)"
if [ ! -f "$MARKER" ] || [ "$(cat "$MARKER")" != "$TODAY" ]; then
  "$PY" "$REPO/run_pipeline.py" --today "$TODAY" >> "$REPO/data/quant.log" 2>&1
  printf '%s\n' "$TODAY" > "$MARKER"
fi
bash "$REPO/scripts/sync_github.sh" --once >> "$REPO/data/sync.log" 2>&1
