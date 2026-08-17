#!/usr/bin/env bash
# 安装本机定时任务：每 15 分钟执行一轮 采集+推送。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER="$REPO/scripts/cron_cycle.sh"
LINE="*/15 * * * * bash $MARKER"

(
  crontab -l 2>/dev/null | grep -vF "$MARKER" || true
  echo "$LINE"
) | crontab -

echo "已安装：每 15 分钟自动采集并推送数据集"
echo "当前定时任务："
crontab -l | grep -F "$MARKER" || true
