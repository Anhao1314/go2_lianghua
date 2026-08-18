# go2w-quant 规则止损回测（B 方案 P0）：2026-08-18

⚠️ 框架验证报告。当前 n_pass=2, n_fail=2, n_unknown=24。赔率表仅验证管线正确性，不构成训练早停决策依据。待 n_pass≥5 且 n_fail≥10 后产出结论性报告。

## 一、数据覆盖

- 扫描粒度：10 分钟；回测 run 数：28（有快照者参与重放）
- 标签：pass 2 / fail 2 / unknown 24（unknown 不进命中率分母）
- 首次 stop 事件：6；首次 R2/R3 预警事件：15

## 二、止损赔率表（按 级别×因子 展开）

| 级别 | 触发因子 | 触发数 | pass | fail | unknown | 命中率 | 误杀数 | 误杀率 | 代理误杀率 | 平均节省min(fail) | 平均节省min(全部) | 期望净节省min | 单次节省估算(元) | t_end 方法分布 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2 | approx_kl | 2 | 0 | 1 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 3986.5 | 3487.7 | 3986.5 | 145.32 | actual:1;task_mean:1 |
| R2 | cpu | 3 | 1 | 1 | 1 | 0.5 | 1 | 0.3333 | 0.6667 | 3986.5 | 1860.7 | 1574.5 | 77.53 | actual:3 |
| R2 | drawdown | 6 | 2 | 1 | 3 | 0.3333 | 2 | 0.3333 | 0.5 | 3986.5 | 1892.6 | 891.3 | 78.86 | actual:4;step_rate:1;task_mean:1 |
| R2 | neg_ratio | 4 | 1 | 0 | 3 | 0.0 | 1 | 0.25 | 0.5 | — | 1528.2 | — | 63.67 | actual:2;step_rate:1;task_mean:1 |
| R2 | stall | 4 | 1 | 1 | 2 | 0.5 | 1 | 0.25 | 0.5 | 3986.5 | 1749.5 | 1679.2 | 72.9 | actual:3;step_rate:1 |
| R2 | std | 2 | 1 | 0 | 1 | 0.0 | 1 | 0.5 | 1.0 | — | 797.8 | — | 33.24 | actual:2 |
| R2 | std_reward_collapse | 1 | 0 | 0 | 1 | — | 0 | N/A (no pass samples) | 1.0 | — | 339.1 | — | 14.13 | actual:1 |

## 三、逐 run 首次止损明细

| task | seed | 级别 | 触发因子 | 标签 | fail_score | 代理pass | 节省min | 节省估算(元) | t_end 方法 | 触发证据 |
|---|---|---|---|---|---|---|---|---|---|---|
| balance | seed00 | R2 | cpu;drawdown;stall;std | pass | 0.2703 | False | 1256.4 | 52.35 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 策略输出标准差 0.0095（<0.05），疑似塌缩 | CPU 使用率峰值 100%（>95%） | timesteps 连续 359 分钟无增长（>=60） |
| full_chain | seed00 | R2 | cpu;drawdown;neg_ratio;stall;std;std_reward_collapse | unknown | 0.0735 | False | 339.1 | 14.13 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 近期评估奖励负值占比 100%（>50%），疑似策略崩溃 | 策略输出标准差 0.0（<0.01），疑似确定性退化 | 策略输出标准差 0.0333（<0.05），疑似塌缩 | CPU 使用率峰值 100%（>95%） | timesteps 连续 319 分钟无增 |
| traverse | seed00 | R2 | approx_kl;drawdown;neg_ratio | unknown | 0.3978 | False | 2988.9 | 124.54 | task_mean | 评估奖励较峰值回撤 46.0%（阈值 30%） | 评估奖励负值占比 50%（>30%） | approx_kl=0.0595（>0.05） |
| traverse | seed01 | R2 | approx_kl;cpu;drawdown;stall | fail | 0.7764 | False | 3986.5 | 166.11 | actual | 评估奖励较峰值回撤 63.9%（阈值 30%） | approx_kl=0.1178（>0.1） | CPU 使用率峰值 100%（>95%） | timesteps 连续 134 分钟无增长（>=60） |
| traverse_curve | seed00 | R2 | drawdown;neg_ratio | pass | 0.215 | False | 1368.6 | 57.02 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 评估奖励负值占比 50%（>30%） |
| traverse_slope | seed00 | R2 | drawdown;neg_ratio;stall | unknown | 0.3338 | False | 1416.1 | 59.0 | step_rate | 评估奖励较峰值回撤 100.0%（阈值 30%） | 近期评估奖励负值占比 67%（>50%），疑似策略崩溃 | timesteps 连续 67 分钟无增长（>=60） |

## 四、首次 R2/R3 预警统计（不产生止损）

| 级别 | 触发因子 | 预警 run 数 |
|---|---|---|
| R2 | stall | 15 |
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
