# go2w-quant 数据筛选报告（分层建模数据）：2026-08-26

## 一、筛选结果概览

- 总 run 数：48；good 26 / insufficient 17 / anomalous 5

## 二、逐规则通过率

| 规则 | 说明 | 通过 | 失败 |
|---|---|---|---|
| rule1 | eval 点数 ≥ 阈值 | 26 | 22 |
| rule2 | 训练规模 ≥ 阈值 | 33 | 15 |
| rule3 | 无解析异常（清洗后 KL / NaN） | 48 | 0 |
| rule4 | 曲线可辨识（std > 阈值） | 43 | 5 |

## 三、异常/不足 run 归档

| task | seed | 质量 | 失败原因 | verdict | eval 点数 |
|---|---|---|---|---|---|
| balance | seed01 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| balance | seed02 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| full_chain | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain_v1 | seed00 | insufficient | rule1: eval 点数 4 < 10;rule2: 训练规模 max(last_eval=4000, total=None) < 500000 | fail | 4 |
| traverse | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | fail | 0 |
| traverse_curve | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_curve | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_curve_dagger | seed00 | anomalous | rule1: eval 点数 6 < 10;rule4: mean_reward 标准差 0.262 <= 1.0（曲线不可辨识） | fail | 6 |
| traverse_curve_dagger_ppo | seed00 | insufficient | rule1: eval 点数 4 < 10 | fail | 4 |
| traverse_curve_high_level | seed00 | anomalous | rule1: eval 点数 4 < 10;rule2: 训练规模 max(last_eval=200000, total=None) < 500000;rule4: mean_reward 标准差 0.190 <= 1.0（曲线不可辨识） | fail | 4 |
| traverse_curve_high_level | seed01 | anomalous | rule1: eval 点数 3 < 10;rule2: 训练规模 max(last_eval=150000, total=None) < 500000;rule4: mean_reward 标准差 0.696 <= 1.0（曲线不可辨识） | pass | 3 |
| traverse_curve_high_level_bplus | seed00 | insufficient | rule1: eval 点数 7 < 10;rule2: 训练规模 max(last_eval=350000, total=None) < 500000 | pass | 7 |
| traverse_curve_junction | j1 | anomalous | rule1: eval 点数 5 < 10;rule2: 训练规模 max(last_eval=250000, total=None) < 500000;rule4: mean_reward 标准差 0.051 <= 1.0（曲线不可辨识） | pass | 5 |
| traverse_curve_junction | j3 | anomalous | rule1: eval 点数 5 < 10;rule4: mean_reward 标准差 0.548 <= 1.0（曲线不可辨识） | pass | 5 |
| traverse_curve_multi_segment | m1 | insufficient | rule1: eval 点数 5 < 10;rule2: 训练规模 max(last_eval=250000, total=None) < 500000 | pass | 5 |
| traverse_curve_multi_segment | m2 | insufficient | rule1: eval 点数 5 < 10 | pass | 5 |
| traverse_curve_multi_segment | m3 | insufficient | rule1: eval 点数 5 < 10 | pass | 5 |
| traverse_flat_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_flat_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |

## 四、全量 vs 筛选回测对比（测试集 = 全量）

- Config A 采用逐样本留一（LOO）：任一测试样本不在自身训练折内，无训练/测试重叠（修复虚高 R2）。

> ⚠️ 有标签样本不足（n<10），以下对比仅作框架验证，不具统计显著性。

### duration_seconds 回归

| 配置 | 训练集 | 测试集 | R2 | MAE | 样本(n_train/n_test) |
|---|---|---|---|---|---|
| A | screened | **full**（LOO 无泄漏） | -1.0228 | 258188.8 | 6/6 |
| B | full | **full** | -0.068 | 249055.3 | 6/6 |

### verdict 分类

- A（screened 训练，full 测试 LOO 无泄漏）：accuracy 0.8857（训练 pass/fail = 5/18，测试 n=35）
- B（full 训练，full 测试 LOO）：accuracy 0.914（pass/fail = 12/23）

## ⚠️ SURVIVORSHIP BIAS WARNING

筛选训练（A）在 full 测试集上的表现差于全量训练（B）：筛选可能引入幸存者偏差，模型不应只在 clean 数据上评估。

## 五、原则

- 筛选 = 分层，非删除：clean 训练、anomaly 鲁棒性测试、full 最终回测。
- v2 风控/回测管线（factors/quant/backtest_*）继续使用全量数据，不受筛选影响。
- 输出：screened_dataset_2026-08-26.csv（good）、anomaly_archive_2026-08-26.csv（非 good 归档）。
