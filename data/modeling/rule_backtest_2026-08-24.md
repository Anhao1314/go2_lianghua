# go2w-quant 规则止损回测（B 方案 P0）：2026-08-24

⚠️ 框架验证报告。当前 n_pass=12, n_fail=23, n_unknown=13。赔率表仅验证管线正确性，不构成训练早停决策依据。待 n_pass≥5 且 n_fail≥10 后产出结论性报告。

## 一、数据覆盖

- 扫描粒度：10 分钟；回测 run 数：48（有快照者参与重放）
- 标签：pass 12 / fail 23 / unknown 13（unknown 不进命中率分母）
- 首次 stop 事件：11；首次 R2/R3 预警事件：15

## 二、止损赔率表（按 级别×因子 展开）

| 级别 | 触发因子 | 触发数 | pass | fail | unknown | 命中率 | 误杀数 | 误杀率 | 代理误杀率 | 平均节省min(fail) | 平均节省min(全部) | 期望净节省min | 单次节省估算(元) | t_end 方法分布 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2 | approx_kl | 2 | 0 | 2 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8941.8 | 8941.8 | 8941.8 | 372.57 | actual:2 |
| R2 | cpu | 4 | 0 | 4 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8971.8 | 8971.8 | 8971.8 | 373.82 | actual:4 |
| R2 | drawdown | 3 | 0 | 3 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8808.5 | 8808.5 | 8808.5 | 367.02 | actual:3 |
| R2 | early_low_reward | 8 | 0 | 7 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 2546.2 | 2227.9 | 2546.2 | 92.83 | no_snapshot:6;actual:2 |
| R2 | neg_ratio | 4 | 0 | 4 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8971.8 | 8971.8 | 8971.8 | 373.82 | actual:4 |
| R2 | neg_ratio_current | 4 | 0 | 4 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8971.8 | 8971.8 | 8971.8 | 373.82 | actual:4 |
| R2 | stall | 3 | 0 | 3 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8808.5 | 8808.5 | 8808.5 | 367.02 | actual:3 |
| R2 | std | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8601.8 | 8601.8 | 8601.8 | 358.41 | actual:1 |
| R2 | std_reward_collapse | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 8601.8 | 8601.8 | 8601.8 | 358.41 | actual:1 |
| R3 | drawdown | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 9511.8 | 9511.8 | 9511.8 | 396.32 | actual:1 |
| R3 | kl_divergent | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 9511.8 | 9511.8 | 9511.8 | 396.32 | actual:1 |
| R3 | neg_ratio | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 9511.8 | 9511.8 | 9511.8 | 396.32 | actual:1 |
| R3 | std | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 9511.8 | 9511.8 | 9511.8 | 396.32 | actual:1 |

## 三、逐 run 首次止损明细

| task | seed | 级别 | 触发因子 | 标签 | fail_score | 代理pass | 节省min | 节省估算(元) | t_end 方法 | 触发证据 |
|---|---|---|---|---|---|---|---|---|---|---|
| balance | seed00 | R3 | drawdown;kl_divergent;neg_ratio;std | fail | 0.5703 | False | 9511.8 | 396.33 | actual | 评估奖励较峰值回撤 78.0%（阈值 30%） | 近期评估奖励负值占比 80%（>50%），疑似策略崩溃 | 策略输出标准差 0.0101（<0.05），疑似塌缩 | approx_kl 持续 7 个 eval 点超界（>=5），疑似数据损坏/发散 |
| full_chain | seed00 | R2 | cpu;drawdown;neg_ratio;neg_ratio_current;stall;std;std_reward_collapse | fail | 0.3735 | False | 8601.8 | 358.41 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 近期评估奖励负值占比 100%（>50%），疑似策略崩溃 | 当前训练尝试负奖励占比 99%（>50%），疑似崩溃 | 策略输出标准差 0.0（<0.01），疑似确定性退化 | 策略输出标准差 0.0333（<0.05），疑似塌缩 | CPU 使用率峰值 100%（ |
| traverse_curve | seed00 | R2 | cpu;drawdown;early_low_reward;neg_ratio;neg_ratio_current;stall | fail | 0.7675 | False | 9401.8 | 391.74 | actual | 评估奖励较峰值回撤 86.4%（阈值 30%） | 评估奖励负值占比 33%（>30%） | 当前训练尝试负奖励占比 33%（>30%） | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） | CPU 使用率峰值 100%（>95%） | timesteps 连续 86 分钟无增长（>=60） |
| traverse_curve_curriculum | s1 | R2 | early_low_reward | fail | 0.5875 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_dagger_ppo | seed00 | R2 | early_low_reward | fail | 0.3704 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v1 | seed00 | R2 | early_low_reward | fail | 0.5637 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v2 | seed00 | R2 | early_low_reward | fail | 0.515 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v3 | seed00 | R2 | early_low_reward | fail | 0.5887 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_flat_slope | seed00 | R2 | approx_kl;cpu;drawdown;early_low_reward;neg_ratio;neg_ratio_current;stall | fail | 0.7833 | False | 8421.8 | 350.91 | actual | 评估奖励较峰值回撤 81.5%（阈值 30%） | 评估奖励负值占比 42%（>30%） | 当前训练尝试负奖励占比 42%（>30%） | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） | approx_kl=0.1219（>0.1） | CPU 使用率峰值 100%（>95%） | timesteps  |
| traverse_slope | seed00 | R2 | approx_kl;cpu;neg_ratio;neg_ratio_current | fail | 0.7333 | False | 9461.8 | 394.24 | actual | 近期评估奖励负值占比 100%（>50%），疑似策略崩溃 | 当前训练尝试负奖励占比 100%（>50%），疑似崩溃 | approx_kl=0.0791（>0.05） | CPU 使用率峰值 100%（>95%） |
| traverse_v1 | seed00 | R2 | early_low_reward | unknown | 0.3888 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |

## 四、首次 R2/R3 预警统计（不产生止损）

| 级别 | 触发因子 | 预警 run 数 |
|---|---|---|
| R2 | cpu | 14 |
| R2 | stall | 13 |
| R2 | stall_current | 13 |
| R2 | approx_kl | 1 |
| R2 | early_low_reward | 1 |
| R2 | neg_ratio | 1 |
| R2 | neg_ratio_current | 1 |
| R2 | std | 1 |

## 五、项目级 token 成本趋势（不逐 run 归因）

| 日期 | 总 token | 成本(元) |
|---|---|---|
| 2026-08-10 | 944544 | 0.1234 |
| 2026-08-13 | 2664405 | 0.39 |
| 2026-08-17 | 95600 | 0.042 |
| 2026-08-21 | 227544 | 0.1775 |
| 2026-08-22 | 337682187 | 40.2341 |

## 六、方法与假设

- **标签**：pass=completed 且 verdict=pass；fail=verdict=fail 或验收含失败场景；其余 unknown。
- **t_end**：completed run 用实际结束时间；incomplete 用 step_rate 外推（total_steps/(触发时进度/触发时已耗时)），缺失回退同 task 平均时长。
- **saved_yuan_compute** = 节省小时 × gpu_count × gpu_hourly_price（估算，config.compute 可调）；token 成本不做逐 run 归因。
- **期望净节省** = hit_rate × 平均节省(fail) − false_kill_rate × 平均浪费(pass)。
- **fail_score** 为软标签代理（0~1），仅辅助判断 potential_false_kill_rate，不参与命中率分母。
- 重放为在线模拟：reports 排除、runs.completed 强制 False；每 run 每规则只记首次触发。
