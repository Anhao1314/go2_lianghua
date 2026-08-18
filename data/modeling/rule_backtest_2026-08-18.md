# go2w-quant 规则止损回测（B 方案 P0）：2026-08-18

⚠️ 框架验证报告。当前 n_pass=0, n_fail=3, n_unknown=23。赔率表仅验证管线正确性，不构成训练早停决策依据。待 n_pass≥5 且 n_fail≥10 后产出结论性报告。

## 一、数据覆盖

- 扫描粒度：10 分钟；回测 run 数：26（有快照者参与重放）
- 标签：pass 0 / fail 3 / unknown 23（unknown 不进命中率分母）
- 首次 stop 事件：7；首次 R2/R3 预警事件：16

## 二、止损赔率表（按 级别×因子 展开）

| 级别 | 触发因子 | 触发数 | pass | fail | unknown | 命中率 | 误杀数 | 误杀率 | 代理误杀率 | 平均节省min(fail) | 平均节省min(全部) | 期望净节省min | 单次节省估算(元) | t_end 方法分布 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2 | approx_kl | 3 | 0 | 1 | 2 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 3986.5 | 3211.7 | 3986.5 | 133.82 | actual:1;step_rate:1;task_mean:1 |
| R2 | cpu | 4 | 0 | 1 | 3 | 1.0 | 0 | N/A (no pass samples) | 0.5 | 3986.5 | 8103.7 | 3986.5 | 337.66 | actual:3;step_rate:1 |
| R2 | drawdown | 7 | 0 | 2 | 5 | 1.0 | 0 | N/A (no pass samples) | 0.2857 | 2527.5 | 5590.3 | 2527.5 | 232.93 | actual:4;step_rate:2;task_mean:1 |
| R2 | stall | 5 | 0 | 1 | 4 | 1.0 | 0 | N/A (no pass samples) | 0.4 | 3986.5 | 6497.4 | 3986.5 | 270.72 | actual:3;step_rate:2 |
| R2 | std | 2 | 0 | 0 | 2 | — | 0 | N/A (no pass samples) | 1.0 | — | 497.6 | — | 20.74 | actual:2 |

## 三、逐 run 首次止损明细

| task | seed | 级别 | 触发因子 | 标签 | fail_score | 代理pass | 节省min | 节省估算(元) | t_end 方法 | 触发证据 |
|---|---|---|---|---|---|---|---|---|---|---|
| balance | seed00 | R2 | cpu;drawdown;stall;std | unknown | 0.2703 | False | 956.3 | 39.85 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 策略输出标准差 0.0095（<0.05），疑似塌缩 | CPU 使用率峰值 100%（>95%） | timesteps 连续 359 分钟无增长（>=60） |
| full_chain | seed00 | R2 | cpu;drawdown;stall;std | unknown | 0.0735 | False | 39.0 | 1.63 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 策略输出标准差 0.0333（<0.05），疑似塌缩 | CPU 使用率峰值 100%（>95%） | timesteps 连续 319 分钟无增长（>=60） |
| traverse | seed00 | R2 | approx_kl;drawdown | unknown | 0.3978 | False | 5576.5 | 232.36 | task_mean | 评估奖励较峰值回撤 46.0%（阈值 30%） | approx_kl=0.0595（>0.05） |
| traverse | seed01 | R2 | approx_kl;cpu;drawdown;stall | fail | 0.7764 | False | 3986.5 | 166.11 | actual | 评估奖励较峰值回撤 63.9%（阈值 30%） | approx_kl=0.1178（>0.1） | CPU 使用率峰值 100%（>95%） | timesteps 连续 134 分钟无增长（>=60） |
| traverse_curve | seed00 | R2 | drawdown | fail | 0.55 | False | 1068.5 | 44.52 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） |
| traverse_flat_slope | seed00 | R2 | cpu;drawdown;stall | unknown | 0.3297 | False | 27433.1 | 1143.04 | step_rate | 评估奖励较峰值回撤 100.0%（阈值 30%） | CPU 使用率峰值 100%（>95%） | timesteps 连续 1044 分钟无增长（>=60） |
| traverse_slope | seed00 | R2 | approx_kl;drawdown;stall | unknown | 0.6356 | False | 72.1 | 3.0 | step_rate | 评估奖励较峰值回撤 88.1%（阈值 30%） | approx_kl=0.3057（>0.1） | timesteps 连续 67 分钟无增长（>=60） |

## 四、首次 R2/R3 预警统计（不产生止损）

| 级别 | 触发因子 | 预警 run 数 |
|---|---|---|
| R2 | stall | 16 |
| R2 | cpu | 2 |

## 五、项目级 token 成本趋势（不逐 run 归因）

| 日期 | 总 token | 成本(元) |
|---|---|---|
| 2026-08-10 | 944544 | 0.1234 |
| 2026-08-13 | 2664405 | 0.39 |
| 2026-08-17 | 95600 | 0.042 |

## 六、方法与假设

- **标签**：pass=completed 且 verdict=pass；fail=verdict=fail 或验收含失败场景；其余 unknown。
- **t_end**：completed run 用实际结束时间；incomplete 用 step_rate 外推（total_steps/(触发时进度/触发时已耗时)），缺失回退同 task 平均时长。
- **saved_yuan_compute** = 节省小时 × gpu_count × gpu_hourly_price（估算，config.compute 可调）；token 成本不做逐 run 归因。
- **期望净节省** = hit_rate × 平均节省(fail) − false_kill_rate × 平均浪费(pass)。
- **fail_score** 为软标签代理（0~1），仅辅助判断 potential_false_kill_rate，不参与命中率分母。
- 重放为在线模拟：reports 排除、runs.completed 强制 False；每 run 每规则只记首次触发。
