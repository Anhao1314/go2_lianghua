# AGENTS.md — go2w-quant 开发约定

> AI 助手（Codex 等）在本项目工作时必须遵守的约定。

## 编码约定

- **文件编码**：UTF-8 无 BOM（CSV 输出用 utf-8-sig 兼容 Excel）
- **行尾**：CRLF（Windows），用 Python 写文件时显式控制换行，避免 `\r\r\n`
- **纯函数优先**：factors.py 中的因子计算必须是纯函数，不依赖全局状态
- **不重命名现有因子**：下游引用太多，用 docstring 澄清 + 新增因子替代
- **配置驱动**：所有阈值放 `config.json`，不硬编码

## 质量门禁（提交前必须通过）

1. `pytest tests/` 全绿
2. 新增模块必须有对应测试文件（`tests/test_<module>.py`）
3. 真实数据冒烟通过（对 balance/seed00 等已知 run 跑通，产物入库）
4. 不改 factors.py / backtest_engine.py / config.json 的现有行为，除非明确要求
5. 产物文件（data/modeling/*.csv/md）随代码一起提交

## Git 提交流程

```bash
git add -A
git commit -m "<模块>: <简述>"
git pull --rebase origin main
git push
```

- 提交信息用中文简述，如 `factors: 新增 eval_neg_ratio 因子`
- 提交前确认工作区只有本次改动，不含临时文件
- data/monitor/ 下的日志文件已 .gitignore，不提交

## 新增模块 checklist

- [ ] 模块代码（纯函数优先）
- [ ] `tests/test_<module>.py`（覆盖正常/边界/异常）
- [ ] `config.json` 新增配置段（如需要）
- [ ] `run_windows.bat` 新增入口（如需要）
- [ ] `MATH_LIBRARY.md` 更新（如涉及因子公式）
- [ ] `QUANT_PLAN.md` 更新（如涉及路线图）
- [ ] `PROJECT_CONTEXT.md` 更新（如涉及文件清单/因子清单）
- [ ] 真实数据冒烟通过

## 数据更新后管线重跑顺序

collector → label_enrichment → data_screening → backtest_rules → quant → modeling → consistency_check（回归验证因子一致性）

## 安全边界

- 实时监控为建议制，不自动 stop 训练进程
- 飞书通知失败不阻塞主流程，仅控制台提示
- API 调用有超时（5s）和重试，不无限等待
- 回测为事后复盘工具，不自动干预训练

## 已知技术债

- `eval_std_recent` / `eval_slope_per_1e6` 在实时路径结构性不可用（API 无历史数据），一致性校验中标记为 N/A
- duration 回归 R² 为负/低（样本不足），仅作框架验证
- 11 个 run 无 eval_points（insufficient），待 Linux 端补采集
