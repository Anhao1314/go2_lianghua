# go2w-quant 数据筛选报告（分层建模数据）：2026-08-19

## 一、筛选结果概览

- 总 run 数：30；good 17 / insufficient 13 / anomalous 0

## 二、逐规则通过率

| 规则 | 说明 | 通过 | 失败 |
|---|---|---|---|
| rule1 | eval 点数 ≥ 阈值 | 17 | 13 |
| rule2 | 训练规模 ≥ 阈值 | 20 | 10 |
| rule3 | 无解析异常（清洗后 KL / NaN） | 30 | 0 |
| rule4 | 曲线可辨识（std > 阈值） | 30 | 0 |

## 三、异常/不足 run 归档

| task | seed | 质量 | 失败原因 | verdict | eval 点数 |
|---|---|---|---|---|---|
| balance | seed01 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| balance | seed02 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| full_chain | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain_v1 | seed00 | insufficient | rule1: eval 点数 4 < 10;rule2: 训练规模 max(last_eval=4000, total=None) < 500000 | fail | 4 |
| traverse | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | fail | 0 |
| traverse_curve | seed00 | insufficient | rule1: eval 点数 8 < 10 | fail | 8 |
| traverse_curve | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_curve | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_flat_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_flat_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |

## 四、全量 vs 筛选回测对比（测试集 = 全量）

- Config A 采用逐样本留一（LOO）：任一测试样本不在自身训练折内，无训练/测试重叠（修复虚高 R2）。


### duration_seconds 回归

| 配置 | 训练集 | 测试集 | R2 | MAE | 样本(n_train/n_test) |
|---|---|---|---|---|---|
| A | screened | **full**（LOO 无泄漏） | -3.9619 | 197758.3 | 6/18 |
| B | full | **full** | -1.058 | 107409.8 | 18/18 |

### verdict 分类

- A（screened 训练，full 测试 LOO 无泄漏）：accuracy 0.7647（训练 pass/fail = 3/11，测试 n=17）
- B（full 训练，full 测试 LOO）：accuracy 0.882（pass/fail = 3/14）

## ⚠️ SURVIVORSHIP BIAS WARNING

筛选训练（A）在 full 测试集上的表现差于全量训练（B）：筛选可能引入幸存者偏差，模型不应只在 clean 数据上评估。

## 五、原则

- 筛选 = 分层，非删除：clean 训练、anomaly 鲁棒性测试、full 最终回测。
- v2 风控/回测管线（factors/quant/backtest_*）继续使用全量数据，不受筛选影响。
- 输出：screened_dataset_2026-08-19.csv（good）、anomaly_archive_2026-08-19.csv（非 good 归档）。
