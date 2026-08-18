# MATH_LIBRARY：公式与因子口径库（go2w-quant）

> 2026-08-18 全量公式审计结论：1 个关键 bug（screening Config A 数据泄漏）已修复、4 处命名歧义已澄清、1 个缺失因子（eval_neg_ratio）已补齐。
> 本文是 factors/quant/modeling/label_enrichment/data_screening/backtest_* 全部公式的权威口径说明；代码注释与本文不一致时以本文为准。

## 一、审计状态与修复记录（2026-08-18）

| 类别 | 内容 | 处理 |
|---|---|---|
| 关键 bug | `data_screening.py` Config A 训练集（screened 7 样本）与测试集（full 17 样本）重叠，R2=0.7526 为虚高 | 改为逐样本留一（LOO）：任一测试样本不在自身训练折内；R2 可能显著下降，属正确结果 |
| 命名歧义 1 | `ev_neg_streak` 易被理解为历史最长负值段，实为**尾部连续**为负个数 | 已写清 docstring，不重命名 |
| 命名歧义 2 | `reward_peak_ratio` 易被理解为峰值占比，实为**最终奖励/峰值奖励**，可负可 >1 | 已写清 docstring，不重命名 |
| 命名歧义 3 | `eval_std_recent` 易被理解为 mean_reward 的 std，实为 **std_reward 列（评估内策略输出 std）最近 5 点均值** | 已写清 docstring，并激活为风控规则 |
| 命名歧义 4 | `eval_slope_per_1e6` 原为首末差分，噪声敏感 | 改为最近 N 点最小二乘斜率（默认 N=5） |
| 缺失因子 | 崩溃早期信号缺失：drawdown 需等奖励跌破 50% 峰值才报警 | 新增 `eval_neg_ratio` / `eval_neg_ratio_recent`（负奖励占比），先于回撤报警 |

## 二、因子公式总表（六类 30 因子 + 富化标签）

### 收敛/稳定（eval_points，每 50k 步评估）
| 因子 | 公式 | 说明 |
|---|---|---|
| eval_points | len(eval 点) | 评估点总数 |
| eval_last_timesteps | 末点 timesteps | 观测窗口末端 |
| eval_last_reward / eval_peak_reward | 末值 / 全局最大 mean_reward | 单点值 |
| eval_drawdown | min(1, (peak-last)/peak)，peak<=0 时 0 | 裁剪到 [0,1]，末值为负不再出现 >1 伪回撤 |
| reward_peak_ratio | last / peak | **最终奖励/峰值奖励**，可负可 >1 |
| eval_slope_per_1e6 | polyfit(timesteps, mean_reward, 1)[0] × 1e6（最近 N=5 点） | 最小二乘斜率，抗单点噪声；有效点 <2 或步长无变化时为 0 |
| eval_std_recent | mean(tail(5, std_reward)) | **std_reward 列均值**（评估内策略输出 std），非 mean_reward 的 std |
| eval_neg_ratio | mean(mean_reward < 0)，全部有效点 | 负奖励占比 |
| eval_neg_ratio_recent | mean(mean_reward < 0)，最近 5 点 | 崩溃早期信号，先于回撤报警 |
| progress_ratio | eval_last_timesteps / total_steps | 训练进度 |

### 健康（tb_points，TensorBoard rollout）
| 因子 | 公式 | 说明 |
|---|---|---|
| approx_kl_last | 过滤 (0,1] 后最后一个有效 approx_kl | 脏值（<=0 或 >1，如日志损坏 122376）置空 |
| std_last | 最后一个 rollout 策略输出 std | 与 eval_std_recent 不同源（rollout vs 评估） |
| ev_neg_streak | 从尾部开始连续为负的 explained_variance 个数 | **非历史最长** |
| value_loss_divergent | 尾部连续上升 ≥10 点且末值 > 前 20 点均值 ×2 | 发散判定 |

### 验收（reports）
report_rows / verdict_fail_ratio / success_rate_mean / max_dev_max / min_clear_min / falls_mean / nan_count（NaN 行数）。

### 资源（snapshots，30s 采样）
snapshot_count / time_span_minutes（起止时间差）/ timesteps_growth / stall_minutes（timesteps 无增长持续分钟）/ idle_minutes（CPU 低于阈值持续分钟）/ cpu_percent_max / mem_percent_max / swap_percent_max。

### 成本（costs）
daily_cost / weekly_cost / monthly_cost / total_cost（元）、cache_rate = cached/(input+cached) token 缓存率。

### 富化标签（label_enrichment.py）
| 标签 | 公式 | 说明 |
|---|---|---|
| training_collapsed | 峰值后存在 reward < 0.5×peak，且其后至末尾 max < 0.8×peak，且塌缩段跨度 ≥20% 观测窗口 | V 形恢复不算塌缩 |
| best_step | 全局最大 mean_reward 的 timesteps | |
| best_step_ratio | best_step / 最后 eval timesteps（无 eval 回退 total_steps） | balance/seed00 = 1.9M/4M = 0.475 |
| collapse_step | 首个 reward < 0.5×peak 的 timesteps | 未塌缩为 None |
| collapse_ratio | collapse_step / 最后 eval timesteps | |
| stop_justified | verdict=fail 或（塌缩 且 best_step_ratio<0.7 且 collapse_ratio<0.8） | 末段塌缩不可早停 |
| data_quality | data_screening.classify() | good / insufficient / anomalous |

## 三、关键公式定义

- **回撤裁剪**：`eval_drawdown = clip((peak - last) / peak, 0, 1)`；末值为负时旧公式产出 >1 的伪回撤（1.1884、1.735），已裁剪。
- **最小二乘斜率**：对最近 N 点 (timesteps, mean_reward) 做 1 阶多项式拟合，斜率 ×1e6；比首末差分抗噪（审计案例：首末 7.5e6 → LS -1e6）。
- **KL 合理性过滤**：`0 < approx_kl <= 1`（PPO 域内合理区间）；日志损坏值（122376 等）置空不入库、不进因子。
- **负奖励占比**：`eval_neg_ratio = mean(reward < 0)`；recent 版取最近 5 点。balance/seed00 = 37/80 = 0.4625（R1），recent = 1.0（R2 → stop）。
- **停滞判定**：进度 ≥60% 且 最终奖励 < 峰值 ×60% → R2 stagnation。
- **stall/idle**：timesteps 无增长持续 ≥30/60 分钟（watch/warn）；CPU <20% 且训练未完成持续 ≥60 分钟疑似卡死。
- **fail_score（软标签代理，backtest_rules）**：`0.2×(1-completed) + 0.3×(verdict=='fail') + 0.2×stagnation_score + 0.2×divergence_score + 0.1×(1-reward_rank)`；仅辅助指标，不进命中率分母。
- **t_end 外推**：completed run 用实际结束时间；incomplete 优先 `total_steps / (触发时 timesteps / 触发时已耗时)`（step_rate），缺失回退同 task completed 平均时长；`t_end_method ∈ {actual, step_rate, task_mean}`。
- **成本拆分**：`saved_yuan_compute = 节省小时 × gpu_count × gpu_hourly_price`；token 成本仅做项目级日趋势，不逐 run 归因。
- **筛选规则（data_screening）**：① eval 点数 ≥10；② max(末 timesteps, total_steps) ≥500k；③ factors 清洗后 approx_kl_last <1.0 且 eval 无 NaN；④ std(mean_reward) >1.0（n<2 视为通过）。rule3/4 任一失败 → anomalous（异常优先），仅 1/2 失败 → insufficient。
- **Config A 无泄漏 LOO**：full 中每个样本 i 的训练集 = screened \ {i}（i∈screened）或全部 screened（i∉screened）；逐折独立填充/标准化/拟合，汇总 full 全部样本的 R2/MAE 与 accuracy；verdict 折内门禁：训练 ≥4 标签且正负各 ≥2。

## 四、风控阈值总表（config.json risk 段）

| 配置键 | watch | warn/severe | 说明 |
|---|---|---|---|
| drawdown | 0.15 | stop 0.30 | 峰值回撤 |
| neg_ratio | 0.30 | severe 0.50（recent_window=5） | 负奖励占比，R1/R2 |
| std_reward.collapse | 0.01 | - | 评估内策略输出 std 塌缩（R1，eval 点数 ≥5） |
| std (tb) | collapse 0.05 | explode 1.50 | rollout 策略 std |
| approx_kl | watch 0.05 | warn 0.10 | 过滤后末值 |
| explained_variance | - | neg_points 10 | 尾部连续为负 |
| stagnation | progress 0.60 | reward_ratio 0.60 | 高进度低奖励 |
| stall_minutes | 30 | 60 | timesteps 无增长 |
| resources | cpu 95 / mem 95 / swap 50→80 / idle 60 分钟 | | 过载与卡死 |
| nan | warn 1 | severe 3 | 验收 NaN 行数 |
| budget | 80% | 100% / 150% | 日/周/月预算 |
| cache_rate_watch | 0.30 | - | token 缓存率 |
| eval_slope.window | 5 | - | 斜率窗口（P1b） |

## 五、命名歧义澄清表（不重命名）

| 因子 | 实际含义 | 易误解为 |
|---|---|---|
| ev_neg_streak | 尾部连续为负个数（非历史最长） | 历史最长负值段 |
| reward_peak_ratio | 最终奖励/峰值奖励，可负可 >1 | 峰值占比 |
| eval_std_recent | std_reward 列（评估内策略输出 std）最近 5 点均值 | mean_reward 的 std |
| eval_slope_per_1e6 | 最近 N 点最小二乘斜率 ×1e6 | 首末差分斜率 |
| best_step_ratio | best_step / 观测窗口末 timesteps | best_step / total_steps |
| collapse_ratio | collapse_step / 观测窗口末 timesteps | 塌缩段长度占比 |
