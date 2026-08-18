#!/usr/bin/env bash
# 把 data/datasets 与 data/reports 提交并推送到 GitHub；--check 只打印不写。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
BRANCH="${GO2W_QUANT_BRANCH:-main}"

# 显式使用 GitHub 私钥，避免 crontab/systemd 环境无 ssh-agent 导致推送失败
if [ -f "$HOME/.ssh/id_ed25519_github" ]; then
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519_github -o IdentitiesOnly=yes"
fi

TRACKED="data/datasets data/reports data/modeling"

case "${1:-}" in
  --check)
    git status --porcelain -- $TRACKED
    ;;
  --once)
    if git status --porcelain -- $TRACKED | grep -q .; then
      git add data/datasets data/reports data/modeling
      git commit -m "[data] $(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
      echo "已提交数据集与报告更新"
    else
      echo "数据集与报告无改动"
    fi
    if ! git remote get-url origin >/dev/null 2>&1; then
      echo "未配置远端 origin，跳过推送（可在 GitHub 建仓后 git remote add origin ...）"
      exit 0
    fi
    git push origin "$BRANCH"
    echo "已推送到 $BRANCH"
    ;;
  *)
    echo "用法: $0 {--check|--once}" >&2
    exit 1
    ;;
esac