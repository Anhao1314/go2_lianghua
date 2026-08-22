# go2w-quant 规则止损回测（B 方案 P0）：2026-08-22

⚠️ 框架验证报告。当前 n_pass=6, n_fail=23, n_unknown=13。赔率表仅验证管线正确性，不构成训练早停决策依据。待 n_pass≥5 且 n_fail≥10 后产出结论性报告。

## 一、数据覆盖

- 扫描粒度：10 分钟；回测 run 数：42（有快照者参与重放）
- 标签：pass 6 / fail 23 / unknown 13（unknown 不进命中率分母）
- 首次 stop 事件：13；首次 R2/R3 预警事件：17

## 二、止损赔率表（按 级别×因子 展开）

| 级别 | 触发因子 | 触发数 | pass | fail | unknown | 命中率 | 误杀数 | 误杀率 | 代理误杀率 | 平均节省min(fail) | 平均节省min(全部) | 期望净节省min | 单次节省估算(元) | t_end 方法分布 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R2 | approx_kl | 5 | 0 | 4 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5640.6 | 4957.6 | 5640.6 | 206.57 | actual:4;task_mean:1 |
| R2 | cpu | 5 | 0 | 5 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5657.3 | 5657.3 | 5657.3 | 235.72 | actual:5 |
| R2 | drawdown | 6 | 0 | 5 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5657.3 | 5085.3 | 5657.3 | 211.89 | actual:5;task_mean:1 |
| R2 | early_low_reward | 9 | 0 | 8 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 2321.5 | 2063.5 | 2321.5 | 85.98 | no_snapshot:6;actual:3 |
| R2 | neg_ratio | 4 | 0 | 3 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5927.4 | 5002.0 | 5927.4 | 208.42 | actual:3;task_mean:1 |
| R2 | neg_ratio_current | 4 | 0 | 3 | 1 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5927.4 | 5002.0 | 5927.4 | 208.42 | actual:3;task_mean:1 |
| R2 | stagnation | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6514.1 | 6514.1 | 6514.1 | 271.42 | actual:1 |
| R2 | stall | 4 | 0 | 4 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6074.0 | 6074.0 | 6074.0 | 253.08 | actual:4 |
| R2 | std | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5724.1 | 5724.1 | 5724.1 | 238.5 | actual:1 |
| R2 | std_reward_collapse | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 5724.1 | 5724.1 | 5724.1 | 238.5 | actual:1 |
| R3 | cpu | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | drawdown | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | kl_divergent | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | neg_ratio | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | restart | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | stall | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |
| R3 | std | 1 | 0 | 1 | 0 | 1.0 | 0 | N/A (no pass samples) | 0.0 | 6633.3 | 6633.3 | 6633.3 | 276.39 | actual:1 |

## 三、逐 run 首次止损明细

| task | seed | 级别 | 触发因子 | 标签 | fail_score | 代理pass | 节省min | 节省估算(元) | t_end 方法 | 触发证据 |
|---|---|---|---|---|---|---|---|---|---|---|
| balance | seed00 | R3 | cpu;drawdown;kl_divergent;neg_ratio;restart;stall;std | fail | 0.5703 | False | 6633.3 | 276.39 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 近期评估奖励负值占比 80%（>50%），疑似策略崩溃 | 策略输出标准差 0.0101（<0.05），疑似塌缩 | approx_kl 持续 6 个 eval 点超界（>=5），疑似数据损坏/发散 | CPU 使用率峰值 100%（>95%） | timestep |
| full_chain | seed00 | R2 | cpu;drawdown;neg_ratio;neg_ratio_current;stall;std;std_reward_collapse | fail | 0.3735 | False | 5724.1 | 238.5 | actual | 评估奖励较峰值回撤 100.0%（阈值 30%） | 近期评估奖励负值占比 100%（>50%），疑似策略崩溃 | 当前训练尝试负奖励占比 99%（>50%），疑似崩溃 | 策略输出标准差 0.0（<0.01），疑似确定性退化 | 策略输出标准差 0.0333（<0.05），疑似塌缩 | CPU 使用率峰值 100%（ |
| traverse | seed00 | R2 | approx_kl;drawdown;neg_ratio;neg_ratio_current | unknown | 0.3978 | False | 2225.8 | 92.74 | task_mean | 评估奖励较峰值回撤 46.0%（阈值 30%） | 评估奖励负值占比 50%（>30%） | 当前训练尝试负奖励占比 50%（>30%） | approx_kl=0.0595（>0.05） |
| traverse | seed01 | R2 | approx_kl;cpu;drawdown | fail | 0.7764 | False | 3990.4 | 166.27 | actual | 评估奖励较峰值回撤 63.9%（阈值 30%） | approx_kl=0.1178（>0.1） | CPU 使用率峰值 100%（>95%） |
| traverse_curve | seed00 | R2 | approx_kl;cpu;drawdown;early_low_reward;stall | fail | 0.7675 | False | 6513.6 | 271.4 | actual | 评估奖励较峰值回撤 45.2%（阈值 30%） | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） | approx_kl=0.0578（>0.05） | CPU 使用率峰值 100%（>95%） | timesteps 连续 201 分钟无增长（>=60） |
| traverse_curve_curriculum | s1 | R2 | early_low_reward | fail | 0.5875 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_dagger_ppo | seed00 | R2 | early_low_reward | fail | 0.3704 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v1 | seed00 | R2 | early_low_reward | fail | 0.5637 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v2 | seed00 | R2 | early_low_reward | fail | 0.515 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_curve_v3 | seed00 | R2 | early_low_reward | fail | 0.5887 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |
| traverse_flat_slope | seed00 | R2 | approx_kl;cpu;drawdown;early_low_reward;neg_ratio;neg_ratio_current;stall | fail | 0.7833 | False | 5544.1 | 231.0 | actual | 评估奖励较峰值回撤 93.4%（阈值 30%） | 评估奖励负值占比 45%（>30%） | 当前训练尝试负奖励占比 45%（>30%） | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） | approx_kl=0.1145（>0.1） | CPU 使用率峰值 100%（>95%） | timesteps  |
| traverse_slope | seed00 | R2 | approx_kl;cpu;drawdown;early_low_reward;neg_ratio;neg_ratio_current;stagnation;stall | fail | 0.7333 | False | 6514.1 | 271.42 | actual | 评估奖励较峰值回撤 42.7%（阈值 30%） | 训练进度 81% 但奖励仅为峰值的 57%（<60%），疑似停滞 | 评估奖励负值占比 88%（>30%） | 当前训练尝试负奖励占比 88%（>50%），疑似崩溃 | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） | approx_kl=0.2469（> |
| traverse_v1 | seed00 | R2 | early_low_reward | unknown | 0.3888 | False | 0.0 | 0.0 | no_snapshot | 前25%训练步数内评估奖励始终低于阈值（从未学会型失败） |

## 四、首次 R2/R3 预警统计（不产生止损）

| 级别 | 触发因子 | 预警 run 数 |
|---|---|---|
| R2 | stall | 15 |
| R2 | stall_current | 14 |
| R2 | cpu | 3 |
| R2 | approx_kl | 1 |
| R2 | std | 1 |

## 五、项目级 token 成本趋势（不逐 run 归因）

| 日期 | 总 token | 成本(元) |
|---|---|---|
| 2026-08-10 | 944544 | 0.1234 |
| 2026-08-13 | 2664405 | 0.39 |
| 2026-08-17 | 95600 | 0.042 |
| 2026-08-21 | 227544 | 0.1775 |

## 六、方法与假设

- **标签**：pass=completed 且 verdict=pass；fail=verdict=fail 或验收含失败场景；其余 unknown。
- **t_end**：completed run 用实际结束时间；incomplete 用 step_rate 外推（total_steps/(触发时进度/触发时已耗时)），缺失回退同 task 平均时长。
- **saved_yuan_compute** = 节省小时 × gpu_count × gpu_hourly_price（估算，config.compute 可调）；token 成本不做逐 run 归因。
- **期望净节省** = hit_rate × 平均节省(fail) − false_kill_rate × 平均浪费(pass)。
- **fail_score** 为软标签代理（0~1），仅辅助判断 potential_false_kill_rate，不参与命中率分母。
- 重放为在线模拟：reports 排除、runs.completed 强制 False；每 run 每规则只记首次触发。
