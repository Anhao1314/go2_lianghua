> 当前状态：飞书通知已移除；机器参数使用 config.local.json。全程特征基线仅用于事后分析，不能用于在线早停或 ETA 预测；历史指标保留原始口径。

# Windows 使用说明

go2w-quant 在 Windows 上用于**查看数据集与运行统计**；数据采集只在
Linux 训练机器上执行。

## 1. 安装 Python 与 Git

- Python 3.10 及以上：https://www.python.org/downloads/
  （安装时勾选 “Add Python to PATH”）
- Git for Windows：https://git-scm.com/download/win

## 2. 获取项目与数据

```bat
git clone <你的 GitHub 仓库地址> go2w-quant
cd go2w-quant
git pull
```

## 3. 一键运行

双击 `run_windows.bat`，或在命令行执行：

```bat
run_windows.bat
```

首次运行会自动创建 `.venv` 并安装依赖，然后显示数据集统计。

## 4. 用 Excel 打开数据

进入 `data\datasets\`，双击任意 CSV：

- `runs.csv`：每个 (任务, seed) 一行，含验收标签与训练时长
- `eval_points.csv`：每 50k 步一条评估曲线
- `tb_points.csv`：每个 rollout 一条细粒度指标
- `snapshots.csv`：30 秒一次的资源与进度快照
- `reports.csv`：验收报告明细
- `costs.csv`：每日/每会话 token 与成本

所有文件均为 UTF-8 带 BOM，中文可直接显示。

## 5. 更新数据

Linux 机器会自动把新数据推送到 GitHub，Windows 端执行：

```bat
git pull
run_windows.bat
```

## 隔离离线分析

运行 `run_windows.bat --pipeline --today 2026-09-06 --out data/modeling/local_review`，再使用 `run_windows.bat --baseline --dataset data/modeling/local_review/dataset_2026-09-06.csv --out data/modeling/local_review`。无需训练端；本地配置优先，--config 可以显式覆盖。
