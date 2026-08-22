# 数据质量报告 2026-08-22

## 总体评分：D（较差：>10个问题，或有>2个严重问题）

- 问题总数：109（其中严重 17）

## 问题统计

| 类别 | 问题数 | 严重问题数 |
|---|---|---|
| A.缺失值 | 65 | 17 |
| B.异常值 | 1 | 0 |
| C.时间戳连续性 | 16 | 0 |
| D.重复数据 | 0 | 0 |
| E.标签一致性 | 1 | 0 |
| F.数据完整性 | 26 | 0 |
| **总计** | **109** | **17** |

## 严重问题（必须处理）

- **DQ049** [A] balance_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ050** [A] balance_v1/seed01：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ051** [A] balance_v1/seed02：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ052** [A] full_chain_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ053** [A] traverse_curve_curriculum/s1：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ054** [A] traverse_curve_curriculum/s2：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ055** [A] traverse_curve_curriculum/s3：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ056** [A] traverse_curve_curriculum/s4：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ057** [A] traverse_curve_multi_segment/m1：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ058** [A] traverse_curve_multi_segment/m2：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ059** [A] traverse_curve_multi_segment/m3：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ060** [A] traverse_curve_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ061** [A] traverse_flat_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ062** [A] traverse_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ063** [A] traverse_v1/seed01：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ064** [A] traverse_v1/seed02：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ065** [A] traverse/seed02：verdict=fail 但无任何 eval 点（无法验证训练表现）（建议：补充 eval 数据或改为 unknown）

## 详细问题列表

### A.缺失值（65）

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
- DQ012 | traverse_curve_high_level/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ013 | traverse_curve_high_level/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ014 | traverse_curve_high_level/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ015 | traverse_curve_high_level_bplus/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ016 | traverse_curve_high_level_bplus_no_goal/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ017 | traverse_curve_multi_segment/m1 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ018 | traverse_curve_multi_segment/m2 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ019 | traverse_curve_multi_segment/m3 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ020 | traverse_curve_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ021 | traverse_curve_v2/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ022 | traverse_curve_v3/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ023 | traverse_flat_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ024 | traverse_flat_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ025 | traverse_flat_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ026 | traverse_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ027 | traverse_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ028 | traverse_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ029 | traverse_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ030 | traverse_v1/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ031 | traverse_v1/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ032 | full_chain_v1/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ033 | traverse_curve_dagger/seed00 | [warning] insufficient_eval_points：eval 点数仅 6（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ034 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ035 | traverse_curve_high_level/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ036 | traverse_curve_high_level/seed01 | [warning] insufficient_eval_points：eval 点数仅 3（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ037 | traverse_curve_high_level_bplus/seed00 | [warning] insufficient_eval_points：eval 点数仅 7（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ038 | traverse_curve_multi_segment/m1 | [warning] insufficient_eval_points：eval 点数仅 5（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ039 | traverse_curve_multi_segment/m2 | [warning] insufficient_eval_points：eval 点数仅 5（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ040 | traverse_curve_multi_segment/m3 | [warning] insufficient_eval_points：eval 点数仅 5（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ041 | full_chain_v1/seed00 | [warning] insufficient_tb_points：tb 点数仅 1（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ042 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_tb_points：tb 点数仅 27（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ043 | traverse_curve_high_level/seed00 | [warning] insufficient_tb_points：tb 点数仅 24（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ044 | traverse_curve_high_level/seed01 | [warning] insufficient_tb_points：tb 点数仅 18（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ045 | traverse_curve_high_level_bplus/seed00 | [warning] insufficient_tb_points：tb 点数仅 42（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ046 | traverse_curve_multi_segment/m1 | [warning] insufficient_tb_points：tb 点数仅 30（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ047 | traverse_curve_multi_segment/m2 | [warning] insufficient_tb_points：tb 点数仅 30（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ048 | traverse_curve_multi_segment/m3 | [warning] insufficient_tb_points：tb 点数仅 30（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ049 | balance_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ050 | balance_v1/seed01 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ051 | balance_v1/seed02 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ052 | full_chain_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ053 | traverse_curve_curriculum/s1 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ054 | traverse_curve_curriculum/s2 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ055 | traverse_curve_curriculum/s3 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ056 | traverse_curve_curriculum/s4 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ057 | traverse_curve_multi_segment/m1 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ058 | traverse_curve_multi_segment/m2 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ059 | traverse_curve_multi_segment/m3 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ060 | traverse_curve_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ061 | traverse_flat_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ062 | traverse_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ063 | traverse_v1/seed01 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ064 | traverse_v1/seed02 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ065 | traverse/seed02 | [critical] missing_eval_data：verdict=fail 但无任何 eval 点（无法验证训练表现） | 建议：补充 eval 数据或改为 unknown

### B.异常值（1）

- DQ066 | traverse_curve_high_level/seed00 | [warning] falls_outlier：falls=20.0 超出 [0, 10] | 建议：检查验收记录

### C.时间戳连续性（16）

- DQ067 | balance/seed00 | [warning] incomplete_training：末 eval 点 4000000 与 total_steps=8000000 偏差 50%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ068 | full_chain/seed00 | [info] missing_early_eval：首个 eval 点 @1950000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ069 | traverse/seed00 | [warning] incomplete_training：末 eval 点 700000 与 total_steps=8000000 偏差 91%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ070 | traverse_curve_curriculum/s2 | [info] missing_early_eval：首个 eval 点 @1200000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ071 | traverse_curve_curriculum/s2 | [warning] incomplete_training：末 eval 点 2150000 与 total_steps=1000000 偏差 115%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ072 | traverse_curve_curriculum/s3 | [info] missing_early_eval：首个 eval 点 @2350000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ073 | traverse_curve_curriculum/s3 | [warning] incomplete_training：末 eval 点 3300000 与 total_steps=1000000 偏差 230%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ074 | traverse_curve_curriculum/s4 | [info] missing_early_eval：首个 eval 点 @3500000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ075 | traverse_curve_curriculum/s4 | [warning] incomplete_training：末 eval 点 4450000 与 total_steps=1000000 偏差 345%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ076 | traverse_curve_dagger_ppo/seed00 | [warning] incomplete_training：末 eval 点 200000 与 total_steps=2000000 偏差 90%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ077 | traverse_curve_multi_segment/m2 | [info] missing_early_eval：首个 eval 点 @550000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ078 | traverse_curve_multi_segment/m3 | [info] missing_early_eval：首个 eval 点 @1300000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ079 | traverse_flat_slope/seed00 | [info] missing_early_eval：首个 eval 点 @750000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ080 | traverse_slope/seed00 | [info] missing_early_eval：首个 eval 点 @700000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ081 | traverse_slope/seed00 | [warning] incomplete_training：末 eval 点 8000000 与 total_steps=4000000 偏差 100%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ082 | traverse_slope_v1/seed00 | [info] missing_early_eval：首个 eval 点 @1800000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期

### D.重复数据（0）

- 无

### E.标签一致性（1）

- DQ083 | full_chain_simple/seed00 | [warning] completed_verdict_mismatch：completed=True 但 verdict=未设置（应为 pass/fail） | 建议：验收后补标或改 completed

### F.数据完整性（26）

- DQ084 | balance/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ085 | balance/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ086 | full_chain/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ087 | full_chain/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ088 | traverse/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ089 | traverse_curve/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ090 | traverse_curve/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ091 | traverse_flat_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ092 | traverse_flat_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ093 | traverse_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ094 | traverse_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ095 | balance/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 4000000 偏差 50%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ096 | traverse/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 700000 偏差 91%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ097 | traverse_curve_curriculum/s2 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 2150000 偏差 115%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ098 | traverse_curve_curriculum/s3 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 3300000 偏差 230%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ099 | traverse_curve_curriculum/s4 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 4450000 偏差 345%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ100 | traverse_curve_dagger_ppo/seed00 | [warning] total_steps_mismatch：total_steps=2000000 与 eval 末点 200000 偏差 90%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ101 | traverse_slope/seed00 | [warning] total_steps_mismatch：total_steps=4000000 与 eval 末点 8000000 偏差 100%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ102 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ103 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ104 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ105 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ106 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ107 | traverse_curve_curriculum/seed00 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ108 | traverse_curve_multi_segment/seed00 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ109 | traverse_curve_multi_segment/seed00_v2 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据

## 建议处理优先级

1. [critical] missing_report（balance_v1/seed00）：补充正式验收报告或调整标签来源
2. [critical] missing_report（balance_v1/seed01）：补充正式验收报告或调整标签来源
3. [critical] missing_report（balance_v1/seed02）：补充正式验收报告或调整标签来源
4. [critical] missing_report（full_chain_v1/seed00）：补充正式验收报告或调整标签来源
5. [critical] missing_report（traverse_curve_curriculum/s1）：补充正式验收报告或调整标签来源
6. [critical] missing_report（traverse_curve_curriculum/s2）：补充正式验收报告或调整标签来源
7. [critical] missing_report（traverse_curve_curriculum/s3）：补充正式验收报告或调整标签来源
8. [critical] missing_report（traverse_curve_curriculum/s4）：补充正式验收报告或调整标签来源
9. [critical] missing_report（traverse_curve_multi_segment/m1）：补充正式验收报告或调整标签来源
10. [critical] missing_report（traverse_curve_multi_segment/m2）：补充正式验收报告或调整标签来源
11. [critical] missing_report（traverse_curve_multi_segment/m3）：补充正式验收报告或调整标签来源
12. [critical] missing_report（traverse_curve_v1/seed00）：补充正式验收报告或调整标签来源
13. [critical] missing_report（traverse_flat_slope_v1/seed00）：补充正式验收报告或调整标签来源
14. [critical] missing_report（traverse_slope_v1/seed00）：补充正式验收报告或调整标签来源
15. [critical] missing_report（traverse_v1/seed01）：补充正式验收报告或调整标签来源
16. [critical] missing_report（traverse_v1/seed02）：补充正式验收报告或调整标签来源
17. [critical] missing_eval_data（traverse/seed02）：补充 eval 数据或改为 unknown
18. [warning] missing_total_steps（balance_v1/seed00）：补全训练步数（或用 eval 末点推算）
19. [warning] missing_total_steps（balance_v1/seed01）：补全训练步数（或用 eval 末点推算）
20. [warning] missing_total_steps（balance_v1/seed02）：补全训练步数（或用 eval 末点推算）
21. [warning] missing_total_steps（full_chain/seed00）：补全训练步数（或用 eval 末点推算）
22. [warning] missing_total_steps（full_chain/seed01）：补全训练步数（或用 eval 末点推算）
23. [warning] missing_total_steps（full_chain/seed02）：补全训练步数（或用 eval 末点推算）
24. [warning] missing_total_steps（full_chain_v1/seed00）：补全训练步数（或用 eval 末点推算）
25. [warning] missing_total_steps（traverse/seed02）：补全训练步数（或用 eval 末点推算）
26. [warning] missing_total_steps（traverse_curve/seed01）：补全训练步数（或用 eval 末点推算）
27. [warning] missing_total_steps（traverse_curve/seed02）：补全训练步数（或用 eval 末点推算）
28. [warning] missing_total_steps（traverse_curve_dagger/seed00）：补全训练步数（或用 eval 末点推算）
29. [warning] missing_total_steps（traverse_curve_high_level/seed00）：补全训练步数（或用 eval 末点推算）
30. [warning] missing_total_steps（traverse_curve_high_level/seed01）：补全训练步数（或用 eval 末点推算）
31. [warning] missing_total_steps（traverse_curve_high_level/seed02）：补全训练步数（或用 eval 末点推算）
32. [warning] missing_total_steps（traverse_curve_high_level_bplus/seed00）：补全训练步数（或用 eval 末点推算）
33. [warning] missing_total_steps（traverse_curve_high_level_bplus_no_goal/seed00）：补全训练步数（或用 eval 末点推算）
34. [warning] missing_total_steps（traverse_curve_multi_segment/m1）：补全训练步数（或用 eval 末点推算）
35. [warning] missing_total_steps（traverse_curve_multi_segment/m2）：补全训练步数（或用 eval 末点推算）
36. [warning] missing_total_steps（traverse_curve_multi_segment/m3）：补全训练步数（或用 eval 末点推算）
37. [warning] missing_total_steps（traverse_curve_v1/seed00）：补全训练步数（或用 eval 末点推算）
38. [warning] missing_total_steps（traverse_curve_v2/seed00）：补全训练步数（或用 eval 末点推算）
39. [warning] missing_total_steps（traverse_curve_v3/seed00）：补全训练步数（或用 eval 末点推算）
40. [warning] missing_total_steps（traverse_flat_slope/seed01）：补全训练步数（或用 eval 末点推算）
41. [warning] missing_total_steps（traverse_flat_slope/seed02）：补全训练步数（或用 eval 末点推算）
42. [warning] missing_total_steps（traverse_flat_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
43. [warning] missing_total_steps（traverse_slope/seed01）：补全训练步数（或用 eval 末点推算）
44. [warning] missing_total_steps（traverse_slope/seed02）：补全训练步数（或用 eval 末点推算）
45. [warning] missing_total_steps（traverse_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
46. [warning] missing_total_steps（traverse_v1/seed00）：补全训练步数（或用 eval 末点推算）
47. [warning] missing_total_steps（traverse_v1/seed01）：补全训练步数（或用 eval 末点推算）
48. [warning] missing_total_steps（traverse_v1/seed02）：补全训练步数（或用 eval 末点推算）
49. [warning] insufficient_eval_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
50. [warning] insufficient_eval_points（traverse_curve_dagger/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
51. [warning] insufficient_eval_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
52. [warning] insufficient_eval_points（traverse_curve_high_level/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
53. [warning] insufficient_eval_points（traverse_curve_high_level/seed01）：已知问题可接受（如 dagger 系列），否则补采数据
54. [warning] insufficient_eval_points（traverse_curve_high_level_bplus/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
55. [warning] insufficient_eval_points（traverse_curve_multi_segment/m1）：已知问题可接受（如 dagger 系列），否则补采数据
56. [warning] insufficient_eval_points（traverse_curve_multi_segment/m2）：已知问题可接受（如 dagger 系列），否则补采数据
57. [warning] insufficient_eval_points（traverse_curve_multi_segment/m3）：已知问题可接受（如 dagger 系列），否则补采数据
58. [warning] insufficient_tb_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
59. [warning] insufficient_tb_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
60. [warning] insufficient_tb_points（traverse_curve_high_level/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
61. [warning] insufficient_tb_points（traverse_curve_high_level/seed01）：已知问题可接受（如 dagger 系列），否则补采数据
62. [warning] insufficient_tb_points（traverse_curve_high_level_bplus/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
63. [warning] insufficient_tb_points（traverse_curve_multi_segment/m1）：已知问题可接受（如 dagger 系列），否则补采数据
64. [warning] insufficient_tb_points（traverse_curve_multi_segment/m2）：已知问题可接受（如 dagger 系列），否则补采数据
65. [warning] insufficient_tb_points（traverse_curve_multi_segment/m3）：已知问题可接受（如 dagger 系列），否则补采数据
66. [warning] falls_outlier（traverse_curve_high_level/seed00）：检查验收记录
67. [warning] incomplete_training（balance/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
68. [warning] incomplete_training（traverse/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
69. [warning] incomplete_training（traverse_curve_curriculum/s2）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
70. [warning] incomplete_training（traverse_curve_curriculum/s3）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
71. [warning] incomplete_training（traverse_curve_curriculum/s4）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
72. [warning] incomplete_training（traverse_curve_dagger_ppo/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
73. [warning] incomplete_training（traverse_slope/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
74. [warning] completed_verdict_mismatch（full_chain_simple/seed00）：验收后补标或改 completed
75. [warning] missing_eval_for_run（balance/seed01）：刚启动可接受，否则补采
76. [warning] missing_eval_for_run（balance/seed02）：刚启动可接受，否则补采
77. [warning] missing_eval_for_run（full_chain/seed01）：刚启动可接受，否则补采
78. [warning] missing_eval_for_run（full_chain/seed02）：刚启动可接受，否则补采
79. [warning] missing_eval_for_run（traverse/seed02）：刚启动可接受，否则补采
80. [warning] missing_eval_for_run（traverse_curve/seed01）：刚启动可接受，否则补采
81. [warning] missing_eval_for_run（traverse_curve/seed02）：刚启动可接受，否则补采
82. [warning] missing_eval_for_run（traverse_flat_slope/seed01）：刚启动可接受，否则补采
83. [warning] missing_eval_for_run（traverse_flat_slope/seed02）：刚启动可接受，否则补采
84. [warning] missing_eval_for_run（traverse_slope/seed01）：刚启动可接受，否则补采
85. [warning] missing_eval_for_run（traverse_slope/seed02）：刚启动可接受，否则补采
86. [warning] total_steps_mismatch（balance/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
87. [warning] total_steps_mismatch（traverse/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
88. [warning] total_steps_mismatch（traverse_curve_curriculum/s2）：确认续训口径（阶段 total_steps vs 累计步数）
89. [warning] total_steps_mismatch（traverse_curve_curriculum/s3）：确认续训口径（阶段 total_steps vs 累计步数）
90. [warning] total_steps_mismatch（traverse_curve_curriculum/s4）：确认续训口径（阶段 total_steps vs 累计步数）
91. [warning] total_steps_mismatch（traverse_curve_dagger_ppo/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
92. [warning] total_steps_mismatch（traverse_slope/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
93. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
94. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
95. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
96. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
97. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
98. [warning] report_without_eval（traverse_curve_curriculum/seed00）：补充 eval 数据
99. [warning] report_without_eval（traverse_curve_multi_segment/seed00）：补充 eval 数据
100. [warning] report_without_eval（traverse_curve_multi_segment/seed00_v2）：补充 eval 数据
101. [info] missing_early_eval（full_chain/seed00）：可能是续训/BC 预热，确认符合预期
102. [info] missing_early_eval（traverse_curve_curriculum/s2）：可能是续训/BC 预热，确认符合预期
103. [info] missing_early_eval（traverse_curve_curriculum/s3）：可能是续训/BC 预热，确认符合预期
104. [info] missing_early_eval（traverse_curve_curriculum/s4）：可能是续训/BC 预热，确认符合预期
105. [info] missing_early_eval（traverse_curve_multi_segment/m2）：可能是续训/BC 预热，确认符合预期
106. [info] missing_early_eval（traverse_curve_multi_segment/m3）：可能是续训/BC 预热，确认符合预期
107. [info] missing_early_eval（traverse_flat_slope/seed00）：可能是续训/BC 预热，确认符合预期
108. [info] missing_early_eval（traverse_slope/seed00）：可能是续训/BC 预热，确认符合预期
109. [info] missing_early_eval（traverse_slope_v1/seed00）：可能是续训/BC 预热，确认符合预期
