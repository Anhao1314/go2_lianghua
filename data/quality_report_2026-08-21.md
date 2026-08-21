# 数据质量报告 2026-08-21

## 总体评分：D（较差：>10个问题，或有>2个严重问题）

- 问题总数：134（其中严重 16）

## 问题统计

| 类别 | 问题数 | 严重问题数 |
|---|---|---|
| A.缺失值 | 42 | 14 |
| B.异常值 | 51 | 0 |
| C.时间戳连续性 | 14 | 0 |
| D.重复数据 | 0 | 0 |
| E.标签一致性 | 3 | 2 |
| F.数据完整性 | 24 | 0 |
| **总计** | **134** | **16** |

## 严重问题（必须处理）

- **DQ029** [A] balance_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ030** [A] balance_v1/seed01：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ031** [A] balance_v1/seed02：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ032** [A] full_chain_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ033** [A] traverse_curve_curriculum/s1：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ034** [A] traverse_curve_curriculum/s2：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ035** [A] traverse_curve_curriculum/s3：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ036** [A] traverse_curve_curriculum/s4：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ037** [A] traverse_curve_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ038** [A] traverse_flat_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ039** [A] traverse_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ040** [A] traverse_v1/seed01：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ041** [A] traverse_v1/seed02：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ042** [A] traverse/seed02：verdict=fail 但无任何 eval 点（无法验证训练表现）（建议：补充 eval 数据或改为 unknown）
- **DQ108** [E] balance/seed00：三表 verdict 不一致: {'runs': 'fail', 'labels': 'fail', 'reports': 'pass'}（建议：以 manual_labels.csv 人工层为准修正）
- **DQ109** [E] traverse_curve_v2/seed00：三表 verdict 不一致: {'runs': 'fail', 'labels': 'fail', 'reports': 'pass'}（建议：以 manual_labels.csv 人工层为准修正）

## 详细问题列表

### A.缺失值（42）

- DQ001 | balance_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ002 | balance_v1/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ003 | balance_v1/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ004 | full_chain/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ005 | full_chain/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ006 | full_chain/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ007 | full_chain_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ008 | traverse/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ009 | traverse_curve/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ010 | traverse_curve/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ011 | traverse_curve_dagger/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ012 | traverse_curve_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ013 | traverse_curve_v2/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ014 | traverse_curve_v3/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ015 | traverse_flat_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ016 | traverse_flat_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ017 | traverse_flat_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ018 | traverse_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ019 | traverse_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ020 | traverse_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ021 | traverse_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ022 | traverse_v1/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ023 | traverse_v1/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ024 | full_chain_v1/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ025 | traverse_curve_dagger/seed00 | [warning] insufficient_eval_points：eval 点数仅 6（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ026 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ027 | full_chain_v1/seed00 | [warning] insufficient_tb_points：tb 点数仅 1（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ028 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_tb_points：tb 点数仅 27（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ029 | balance_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ030 | balance_v1/seed01 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ031 | balance_v1/seed02 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ032 | full_chain_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ033 | traverse_curve_curriculum/s1 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ034 | traverse_curve_curriculum/s2 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ035 | traverse_curve_curriculum/s3 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ036 | traverse_curve_curriculum/s4 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ037 | traverse_curve_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ038 | traverse_flat_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ039 | traverse_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ040 | traverse_v1/seed01 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ041 | traverse_v1/seed02 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ042 | traverse/seed02 | [critical] missing_eval_data：verdict=fail 但无任何 eval 点（无法验证训练表现） | 建议：补充 eval 数据或改为 unknown

### B.异常值（51）

- DQ043 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=501.9331 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ044 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=500.1802 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ045 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=510.8329 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ046 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=506.5604 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ047 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=507.7487 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ048 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=502.5579 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ049 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=506.1243 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ050 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=508.0516 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ051 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=500.83 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ052 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=514.8645 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ053 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=515.3718 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ054 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=521.6335 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ055 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=523.6896 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ056 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=519.5035 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ057 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=516.8789 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ058 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=518.4048 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ059 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=515.9738 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ060 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=517.9587 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ061 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=512.4451 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ062 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=503.8975 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ063 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=509.2973 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ064 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=503.0333 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ065 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=514.0091 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ066 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=513.7031 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ067 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=512.1712 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ068 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=514.0312 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ069 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=516.2096 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ070 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=517.1577 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ071 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=520.1718 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ072 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=510.4705 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ073 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=517.736 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ074 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=525.1246 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ075 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=520.2081 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ076 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=502.8749 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ077 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=505.9768 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ078 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=508.132 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ079 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=515.1157 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ080 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=509.6186 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ081 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=507.1906 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ082 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=507.5644 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ083 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=506.3502 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ084 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=517.4032 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ085 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=517.349 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ086 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=505.9798 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ087 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=510.4013 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ088 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=506.2571 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ089 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=507.438 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ090 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=506.4129 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ091 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=513.5442 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ092 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=512.6844 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算
- DQ093 | full_chain_simple/seed00 | [warning] reward_outlier：mean_reward=511.9575 超出 [-200.0, 500.0]（物理不合理） | 建议：检查 eval 采集或单位换算

### C.时间戳连续性（14）

- DQ094 | balance/seed00 | [warning] incomplete_training：末 eval 点 4000000 与 total_steps=8000000 偏差 50%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ095 | full_chain/seed00 | [info] missing_early_eval：首个 eval 点 @1950000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ096 | traverse/seed00 | [warning] incomplete_training：末 eval 点 700000 与 total_steps=8000000 偏差 91%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ097 | traverse_curve_curriculum/s2 | [info] missing_early_eval：首个 eval 点 @1200000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ098 | traverse_curve_curriculum/s2 | [warning] incomplete_training：末 eval 点 2150000 与 total_steps=1000000 偏差 115%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ099 | traverse_curve_curriculum/s3 | [info] missing_early_eval：首个 eval 点 @2350000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ100 | traverse_curve_curriculum/s3 | [warning] incomplete_training：末 eval 点 3300000 与 total_steps=1000000 偏差 230%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ101 | traverse_curve_curriculum/s4 | [info] missing_early_eval：首个 eval 点 @3500000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ102 | traverse_curve_curriculum/s4 | [warning] incomplete_training：末 eval 点 4450000 与 total_steps=1000000 偏差 345%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ103 | traverse_curve_dagger_ppo/seed00 | [warning] incomplete_training：末 eval 点 200000 与 total_steps=2000000 偏差 90%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ104 | traverse_flat_slope/seed00 | [info] missing_early_eval：首个 eval 点 @750000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ105 | traverse_slope/seed00 | [info] missing_early_eval：首个 eval 点 @700000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ106 | traverse_slope/seed00 | [warning] incomplete_training：末 eval 点 8000000 与 total_steps=4000000 偏差 100%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ107 | traverse_slope_v1/seed00 | [info] missing_early_eval：首个 eval 点 @1800000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期

### D.重复数据（0）

- 无

### E.标签一致性（3）

- DQ108 | balance/seed00 | [critical] verdict_mismatch：三表 verdict 不一致: {'runs': 'fail', 'labels': 'fail', 'reports': 'pass'} | 建议：以 manual_labels.csv 人工层为准修正
- DQ109 | traverse_curve_v2/seed00 | [critical] verdict_mismatch：三表 verdict 不一致: {'runs': 'fail', 'labels': 'fail', 'reports': 'pass'} | 建议：以 manual_labels.csv 人工层为准修正
- DQ110 | full_chain_simple/seed00 | [warning] completed_verdict_mismatch：completed=True 但 verdict=未设置（应为 pass/fail） | 建议：验收后补标或改 completed

### F.数据完整性（24）

- DQ111 | balance/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ112 | balance/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ113 | full_chain/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ114 | full_chain/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ115 | traverse/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ116 | traverse_curve/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ117 | traverse_curve/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ118 | traverse_flat_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ119 | traverse_flat_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ120 | traverse_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ121 | traverse_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ122 | balance/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 4000000 偏差 50%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ123 | traverse/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 700000 偏差 91%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ124 | traverse_curve_curriculum/s2 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 2150000 偏差 115%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ125 | traverse_curve_curriculum/s3 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 3300000 偏差 230%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ126 | traverse_curve_curriculum/s4 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 4450000 偏差 345%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ127 | traverse_curve_dagger_ppo/seed00 | [warning] total_steps_mismatch：total_steps=2000000 与 eval 末点 200000 偏差 90%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ128 | traverse_slope/seed00 | [warning] total_steps_mismatch：total_steps=4000000 与 eval 末点 8000000 偏差 100%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ129 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ130 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ131 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ132 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ133 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ134 | traverse_curve_curriculum/seed00 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据

## 建议处理优先级

1. [critical] missing_report（balance_v1/seed00）：补充正式验收报告或调整标签来源
2. [critical] missing_report（balance_v1/seed01）：补充正式验收报告或调整标签来源
3. [critical] missing_report（balance_v1/seed02）：补充正式验收报告或调整标签来源
4. [critical] missing_report（full_chain_v1/seed00）：补充正式验收报告或调整标签来源
5. [critical] missing_report（traverse_curve_curriculum/s1）：补充正式验收报告或调整标签来源
6. [critical] missing_report（traverse_curve_curriculum/s2）：补充正式验收报告或调整标签来源
7. [critical] missing_report（traverse_curve_curriculum/s3）：补充正式验收报告或调整标签来源
8. [critical] missing_report（traverse_curve_curriculum/s4）：补充正式验收报告或调整标签来源
9. [critical] missing_report（traverse_curve_v1/seed00）：补充正式验收报告或调整标签来源
10. [critical] missing_report（traverse_flat_slope_v1/seed00）：补充正式验收报告或调整标签来源
11. [critical] missing_report（traverse_slope_v1/seed00）：补充正式验收报告或调整标签来源
12. [critical] missing_report（traverse_v1/seed01）：补充正式验收报告或调整标签来源
13. [critical] missing_report（traverse_v1/seed02）：补充正式验收报告或调整标签来源
14. [critical] missing_eval_data（traverse/seed02）：补充 eval 数据或改为 unknown
15. [critical] verdict_mismatch（balance/seed00）：以 manual_labels.csv 人工层为准修正
16. [critical] verdict_mismatch（traverse_curve_v2/seed00）：以 manual_labels.csv 人工层为准修正
17. [warning] missing_total_steps（balance_v1/seed00）：补全训练步数（或用 eval 末点推算）
18. [warning] missing_total_steps（balance_v1/seed01）：补全训练步数（或用 eval 末点推算）
19. [warning] missing_total_steps（balance_v1/seed02）：补全训练步数（或用 eval 末点推算）
20. [warning] missing_total_steps（full_chain/seed00）：补全训练步数（或用 eval 末点推算）
21. [warning] missing_total_steps（full_chain/seed01）：补全训练步数（或用 eval 末点推算）
22. [warning] missing_total_steps（full_chain/seed02）：补全训练步数（或用 eval 末点推算）
23. [warning] missing_total_steps（full_chain_v1/seed00）：补全训练步数（或用 eval 末点推算）
24. [warning] missing_total_steps（traverse/seed02）：补全训练步数（或用 eval 末点推算）
25. [warning] missing_total_steps（traverse_curve/seed01）：补全训练步数（或用 eval 末点推算）
26. [warning] missing_total_steps（traverse_curve/seed02）：补全训练步数（或用 eval 末点推算）
27. [warning] missing_total_steps（traverse_curve_dagger/seed00）：补全训练步数（或用 eval 末点推算）
28. [warning] missing_total_steps（traverse_curve_v1/seed00）：补全训练步数（或用 eval 末点推算）
29. [warning] missing_total_steps（traverse_curve_v2/seed00）：补全训练步数（或用 eval 末点推算）
30. [warning] missing_total_steps（traverse_curve_v3/seed00）：补全训练步数（或用 eval 末点推算）
31. [warning] missing_total_steps（traverse_flat_slope/seed01）：补全训练步数（或用 eval 末点推算）
32. [warning] missing_total_steps（traverse_flat_slope/seed02）：补全训练步数（或用 eval 末点推算）
33. [warning] missing_total_steps（traverse_flat_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
34. [warning] missing_total_steps（traverse_slope/seed01）：补全训练步数（或用 eval 末点推算）
35. [warning] missing_total_steps（traverse_slope/seed02）：补全训练步数（或用 eval 末点推算）
36. [warning] missing_total_steps（traverse_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
37. [warning] missing_total_steps（traverse_v1/seed00）：补全训练步数（或用 eval 末点推算）
38. [warning] missing_total_steps（traverse_v1/seed01）：补全训练步数（或用 eval 末点推算）
39. [warning] missing_total_steps（traverse_v1/seed02）：补全训练步数（或用 eval 末点推算）
40. [warning] insufficient_eval_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
41. [warning] insufficient_eval_points（traverse_curve_dagger/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
42. [warning] insufficient_eval_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
43. [warning] insufficient_tb_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
44. [warning] insufficient_tb_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
45. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
46. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
47. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
48. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
49. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
50. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
51. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
52. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
53. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
54. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
55. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
56. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
57. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
58. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
59. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
60. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
61. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
62. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
63. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
64. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
65. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
66. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
67. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
68. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
69. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
70. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
71. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
72. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
73. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
74. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
75. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
76. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
77. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
78. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
79. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
80. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
81. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
82. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
83. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
84. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
85. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
86. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
87. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
88. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
89. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
90. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
91. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
92. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
93. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
94. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
95. [warning] reward_outlier（full_chain_simple/seed00）：检查 eval 采集或单位换算
96. [warning] incomplete_training（balance/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
97. [warning] incomplete_training（traverse/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
98. [warning] incomplete_training（traverse_curve_curriculum/s2）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
99. [warning] incomplete_training（traverse_curve_curriculum/s3）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
100. [warning] incomplete_training（traverse_curve_curriculum/s4）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
101. [warning] incomplete_training（traverse_curve_dagger_ppo/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
102. [warning] incomplete_training（traverse_slope/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
103. [warning] completed_verdict_mismatch（full_chain_simple/seed00）：验收后补标或改 completed
104. [warning] missing_eval_for_run（balance/seed01）：刚启动可接受，否则补采
105. [warning] missing_eval_for_run（balance/seed02）：刚启动可接受，否则补采
106. [warning] missing_eval_for_run（full_chain/seed01）：刚启动可接受，否则补采
107. [warning] missing_eval_for_run（full_chain/seed02）：刚启动可接受，否则补采
108. [warning] missing_eval_for_run（traverse/seed02）：刚启动可接受，否则补采
109. [warning] missing_eval_for_run（traverse_curve/seed01）：刚启动可接受，否则补采
110. [warning] missing_eval_for_run（traverse_curve/seed02）：刚启动可接受，否则补采
111. [warning] missing_eval_for_run（traverse_flat_slope/seed01）：刚启动可接受，否则补采
112. [warning] missing_eval_for_run（traverse_flat_slope/seed02）：刚启动可接受，否则补采
113. [warning] missing_eval_for_run（traverse_slope/seed01）：刚启动可接受，否则补采
114. [warning] missing_eval_for_run（traverse_slope/seed02）：刚启动可接受，否则补采
115. [warning] total_steps_mismatch（balance/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
116. [warning] total_steps_mismatch（traverse/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
117. [warning] total_steps_mismatch（traverse_curve_curriculum/s2）：确认续训口径（阶段 total_steps vs 累计步数）
118. [warning] total_steps_mismatch（traverse_curve_curriculum/s3）：确认续训口径（阶段 total_steps vs 累计步数）
119. [warning] total_steps_mismatch（traverse_curve_curriculum/s4）：确认续训口径（阶段 total_steps vs 累计步数）
120. [warning] total_steps_mismatch（traverse_curve_dagger_ppo/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
121. [warning] total_steps_mismatch（traverse_slope/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
122. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
123. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
124. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
125. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
126. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
127. [warning] report_without_eval（traverse_curve_curriculum/seed00）：补充 eval 数据
128. [info] missing_early_eval（full_chain/seed00）：可能是续训/BC 预热，确认符合预期
129. [info] missing_early_eval（traverse_curve_curriculum/s2）：可能是续训/BC 预热，确认符合预期
130. [info] missing_early_eval（traverse_curve_curriculum/s3）：可能是续训/BC 预热，确认符合预期
131. [info] missing_early_eval（traverse_curve_curriculum/s4）：可能是续训/BC 预热，确认符合预期
132. [info] missing_early_eval（traverse_flat_slope/seed00）：可能是续训/BC 预热，确认符合预期
133. [info] missing_early_eval（traverse_slope/seed00）：可能是续训/BC 预热，确认符合预期
134. [info] missing_early_eval（traverse_slope_v1/seed00）：可能是续训/BC 预热，确认符合预期
