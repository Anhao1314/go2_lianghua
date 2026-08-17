# go2w-quant

Go2w 机器狗强化训练项目的**数据量化采集项目**（v1：只采集，不建模）。

目标：把训练产生的全部可量化数据（评估曲线、TensorBoard 指标、30s 快照、
验收报告、token 成本）聚合成结构化 CSV 数据集，定期推送到 GitHub。
Windows 另一台设备 `git pull` 后可直接用 Excel 打开，或运行 `summary.py` 查看统计。

## 目录结构

```text
go2w-quant/
├── collector.py        # 数据采集（只在 Linux 数据源机器执行）
├── summary.py          # 数据集统计预览（Windows/Linux 通用）
├── schema.py           # 每张表的列定义与校验
├── data_dictionary.md  # 数据字典（列含义/单位/来源/频率）
├── config.json         # 数据源路径与成本价格配置
├── data/datasets/      # 结构化 CSV（随 GitHub 推送）
├── data/raw/           # 原始快照存档（不入库）
├── scripts/            # Linux 定时采集与 GitHub 同步
├── run_windows.bat     # Windows 一键运行入口
└── tests/              # 单元测试
```

## Linux（数据源机器）：采集

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python collector.py --config config.json   # 增量采集
.venv/bin/python summary.py                          # 查看统计
bash scripts/install_cron.sh                         # 每 15 分钟自动采集+推送
```

采集器**只读**机器狗仓库，不会修改训练代码或数据。

## Windows（另一台设备）：查看

```powershell
git clone <你的 GitHub 仓库地址> go2w-quant
cd go2w-quant
run_windows.bat
```

更新数据：`git pull` 后再运行 `run_windows.bat`。
CSV 均为 UTF-8 BOM 编码，双击即可用 Excel 打开，中文不乱码。
详细步骤见 `WINDOWS.md`。

## GitHub 数据同步

```bash
bash scripts/sync_github.sh --check   # 只打印待提交的数据改动
bash scripts/sync_github.sh --once    # 提交 data/datasets 并推送
```

首次使用前先添加远端：`git remote add origin <你的仓库地址>`。

## 建模预留（v2）

`runs.csv` 已包含建模标签：`verdict`（验收 pass/fail）、`success_rate`（成功率）、
`duration_seconds`（训练时长）。v2 将基于这些字段训练“验收早停分类”与“耗时/ETA 回归”，
模型以 joblib + `predict.py` 交付，Linux / Windows 均可运行。
