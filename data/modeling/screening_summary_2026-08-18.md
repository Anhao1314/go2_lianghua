# go2w-quant 数据筛选报告（分层建模数据）：2026-08-18

## 一、筛选结果概览

- 总 run 数：29；good 16 / insufficient 13 / anomalous 0

## 二、逐规则通过率

| 规则 | 说明 | 通过 | 失败 |
|---|---|---|---|
| rule1 | eval 点数 ≥ 阈值 | 16 | 13 |
| rule2 | 训练规模 ≥ 阈值 | 19 | 10 |
| rule3 | 无解析异常（清洗后 KL / NaN） | 29 | 0 |
| rule4 | 曲线可辨识（std > 阈值） | 29 | 0 |

## 三、异常/不足 run 归档

| task | seed | 质量 | 失败原因 | verdict | eval 点数 |
|---|---|---|---|---|---|
| balance | seed01 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| balance | seed02 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| full_chain | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| full_chain_v1 | seed00 | insufficient | rule1: eval 点数 4 < 10;rule2: 训练规模 max(last_eval=4000, total=None) < 500000 | nan | 4 |
| traverse | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | fail | 0 |
| traverse_curve | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_curve | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_flat_slope | seed00 | insufficient | rule1: eval 点数 0 < 10 | nan | 0 |
| traverse_flat_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_flat_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed01 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |
| traverse_slope | seed02 | insufficient | rule1: eval 点数 0 < 10;rule2: 训练规模 max(last_eval=0, total=None) < 500000 | nan | 0 |

## 四、全量 vs 筛选回测对比（测试集 = 全量）

- Config A 采用逐样本留一（LOO）：任一测试样本不在自身训练折内，无训练/测试重叠（修复虚高 R2）。


### duration_seconds 回归

| 配置 | 训练集 | 测试集 | R2 | MAE | 样本(n_train/n_test) |
|---|---|---|---|---|---|
| A | screened | **full**（LOO 无泄漏） | 0.1749 | 109269.3 | 6/18 |
| B | full | **full** | -10.563 | 280281.4 | 18/18 |

### verdict 分类

- A（screened 训练，full 测试 LOO 无泄漏）：样本不足未训练（训练 pass/fail = 1/5，测试 n=0）
- B（full 训练，full 测试 LOO）：accuracy 0.5（pass/fail = 2/2）

## 五、原则

- 筛选 = 分层，非删除：clean 训练、anomaly 鲁棒性测试、full 最终回测。
- v2 风控/回测管线（factors/quant/backtest_*）继续使用全量数据，不受筛选影响。
- 输出：screened_dataset_2026-08-18.csv（good）、anomaly_archive_2026-08-18.csv（非 good 归档）。
