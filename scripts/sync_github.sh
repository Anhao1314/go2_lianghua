#!/usr/bin/env bash
# 只提交数据；不覆盖远端、不自动解决冲突。
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
BRANCH="${GO2W_QUANT_BRANCH:-main}"
TRACKED=(data/datasets data/reports data/modeling)
case "${1:-}" in
  --check) git status --porcelain -- "${TRACKED[@]}"; exit 0 ;;
  --once) ;;
  *) echo "用法: $0 {--check|--once}" >&2; exit 1 ;;
esac
[ "$(git branch --show-current)" = "$BRANCH" ] || { echo "当前分支不匹配 $BRANCH" >&2; exit 1; }
git diff --cached --quiet || { echo "暂存区有改动，停止同步" >&2; exit 1; }
# 排除允许的数据目录后，任何改动（包括未跟踪文件）都阻止自动提交。
if [ -n "$(git status --porcelain -- . ':!data/datasets' ':!data/reports' ':!data/modeling')" ]; then
  echo "存在非数据改动，停止同步" >&2; exit 1
fi
git remote get-url origin >/dev/null 2>&1 || { echo "未配置 origin" >&2; exit 1; }
git fetch origin "$BRANCH"
git merge-base --is-ancestor FETCH_HEAD HEAD || { echo "远端领先或分叉，请人工同步" >&2; exit 1; }
if [ -n "$(git status --porcelain -- "${TRACKED[@]}")" ]; then
  git add -- "${TRACKED[@]}"
  git commit -m "data: 更新数据集与报告 $(date '+%Y-%m-%d %H:%M:%S')"
fi
git push origin "HEAD:refs/heads/$BRANCH"
