# early_low_reward 规则回测验证（2026-08-19）

规则：前 25% 训练步数内（total_steps 缺失用最后 eval 步长），early_points >= 3 且 max(mean_reward) < task 阈值 → 触发 R2 stop。阈值：traverse* = 30，balance*/full_chain* = 50，其他 = 30。

> 本报告为只读验证，未修改任何现有规则/配置，不代表上线决定。

## 一、逐 run 触发明细

| run | verdict | total_steps | 25% 步数 | early点数 | early_max | early_mean | 触发 | 触发步数 |
|---|---|---|---|---|---|---|---|---|
| balance/seed00 | fail | 8,000,000 | 2,000,000 | 40 | 99.98 | 99.46 | 否 | - |
| balance_v1/seed00 | fail | 1,350,000 | 337,500 | 6 | 60.95 | 10.99 | 否 | - |
| balance_v1/seed01 | fail | 3,100,000 | 775,000 | 15 | 99.92 | 99.73 | 否 | - |
| balance_v1/seed02 | fail | 5,300,000 | 1,325,000 | 26 | 99.97 | 99.84 | 否 | - |
| full_chain/seed00 | fail | 5,900,000 | 1,475,000 | 0 | - | - | 否 | - |
| full_chain_v1/seed00 | fail | 4,000 | 1,000 | 1 | 147.03 | 147.03 | 否 | - |
| traverse/seed00 | unknown | 8,000,000 | 2,000,000 | 14 | 124.63 | 27.02 | 否 | - |
| traverse/seed01 | fail | 8,000,000 | 2,000,000 | 40 | 139.76 | 110.37 | 否 | - |
| traverse_curve/seed00 | fail | 4,000,000 | 1,000,000 | 8 | 10.88 | -10.75 | 是 | 1,000,000 |
| traverse_curve_v1/seed00 | fail | 4,000,000 | 1,000,000 | 20 | 12.64 | -0.97 | 是 | 1,000,000 |
| traverse_curve_v2/seed00 | fail | 4,000,000 | 1,000,000 | 20 | 8.10 | -9.80 | 是 | 1,000,000 |
| traverse_curve_v3/seed00 | fail | 4,000,000 | 1,000,000 | 20 | 9.39 | -2.55 | 是 | 1,000,000 |
| traverse_flat_slope/seed00 | unknown | 4,000,000 | 1,000,000 | 16 | -8.08 | -12.46 | 是 | 1,000,000 |
| traverse_flat_slope_v1/seed00 | fail | 4,000,000 | 1,000,000 | 20 | 30.05 | 2.47 | 否 | - |
| traverse_slope/seed00 | fail | 4,000,000 | 1,000,000 | 20 | 13.85 | -8.78 | 是 | 1,000,000 |
| traverse_slope_v1/seed00 | fail | 4,000,000 | 1,000,000 | 0 | - | - | 否 | - |
| traverse_v1/seed00 | unknown | 700,000 | 175,000 | 3 | 9.09 | -15.96 | 是 | 175,000 |
| traverse_v1/seed01 | pass | 8,000,000 | 2,000,000 | 40 | 139.76 | 110.37 | 否 | - |
| traverse_v1/seed02 | pass | 8,000,000 | 2,000,000 | 40 | 139.82 | 99.50 | 否 | - |

## 二、触发统计

- 有 eval 数据 run：19；触发：7
- 触发 verdict 分布：pass 0 / fail 5 / unknown 2
- 命中率（fail / (fail+pass)）：1.00
- 误杀数（触发的 pass）：0
- 与现有 stop 事件重叠：3；新增命中：4（fail 3 / unknown 1）

## 三、阈值敏感性（traverse* 系列：20 / 30 / 50 / 80）

| 阈值 | 触发数 | 触发 run | 误杀 pass |
|---|---|---|---|
| 20 | 7 | traverse_curve/seed00、traverse_curve_v1/seed00、traverse_curve_v2/seed00、traverse_curve_v3/seed00、traverse_flat_slope/seed00、traverse_slope/seed00、traverse_v1/seed00 | 0 |
| 30 | 7 | traverse_curve/seed00、traverse_curve_v1/seed00、traverse_curve_v2/seed00、traverse_curve_v3/seed00、traverse_flat_slope/seed00、traverse_slope/seed00、traverse_v1/seed00 | 0 |
| 50 | 8 | traverse_curve/seed00、traverse_curve_v1/seed00、traverse_curve_v2/seed00、traverse_curve_v3/seed00、traverse_flat_slope/seed00、traverse_flat_slope_v1/seed00、traverse_slope/seed00、traverse_v1/seed00 | 0 |
| 80 | 8 | traverse_curve/seed00、traverse_curve_v1/seed00、traverse_curve_v2/seed00、traverse_curve_v3/seed00、traverse_flat_slope/seed00、traverse_flat_slope_v1/seed00、traverse_slope/seed00、traverse_v1/seed00 | 0 |

## 四、ep_len_stall 对比（连续 5 点 mean_ep_len < 50）

| run | verdict | 首个触发步数 | 是否同时命中 early_low_reward |
|---|---|---|---|
| balance/seed00 | fail | 2,750,000 | 否 |
| balance_v1/seed00 | fail | 300,000 | 否 |
| full_chain/seed00 | fail | 2,200,000 | 否 |

## 五、结论

建议上线：阈值 30 下触发 7 个 run（fail 5 / unknown 2），0 误杀，命中率 1.00，新增 fail 命中 3 个；敏感性分析中 20/30 一致、50/80 增加 traverse_flat_slope_v1（early_max=30.05，margin 小），推荐阈值 30。
