# 数据质量报告 2026-08-21

## 总体评分：D（较差：>10个问题，或有>2个严重问题）

- 问题总数：85（其中严重 14）

## 问题统计

| 类别 | 问题数 | 严重问题数 |
|---|---|---|
| A.缺失值 | 45 | 14 |
| B.异常值 | 1 | 0 |
| C.时间戳连续性 | 14 | 0 |
| D.重复数据 | 0 | 0 |
| E.标签一致性 | 1 | 0 |
| F.数据完整性 | 24 | 0 |
| **总计** | **85** | **14** |

## 严重问题（必须处理）

- **DQ032** [A] balance_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ033** [A] balance_v1/seed01：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ034** [A] balance_v1/seed02：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ035** [A] full_chain_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ036** [A] traverse_curve_curriculum/s1：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ037** [A] traverse_curve_curriculum/s2：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ038** [A] traverse_curve_curriculum/s3：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ039** [A] traverse_curve_curriculum/s4：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ040** [A] traverse_curve_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ041** [A] traverse_flat_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ042** [A] traverse_slope_v1/seed00：verdict=fail 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ043** [A] traverse_v1/seed01：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ044** [A] traverse_v1/seed02：verdict=pass 但 reports.csv 无对应验收行（建议：补充正式验收报告或调整标签来源）
- **DQ045** [A] traverse/seed02：verdict=fail 但无任何 eval 点（无法验证训练表现）（建议：补充 eval 数据或改为 unknown）

## 详细问题列表

### A.缺失值（45）

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
- DQ013 | traverse_curve_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ014 | traverse_curve_v2/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ015 | traverse_curve_v3/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ016 | traverse_flat_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ017 | traverse_flat_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ018 | traverse_flat_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ019 | traverse_slope/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ020 | traverse_slope/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ021 | traverse_slope_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ022 | traverse_v1/seed00 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ023 | traverse_v1/seed01 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ024 | traverse_v1/seed02 | [warning] missing_total_steps：total_steps 为空 | 建议：补全训练步数（或用 eval 末点推算）
- DQ025 | full_chain_v1/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ026 | traverse_curve_dagger/seed00 | [warning] insufficient_eval_points：eval 点数仅 6（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ027 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ028 | traverse_curve_high_level/seed00 | [warning] insufficient_eval_points：eval 点数仅 4（<10） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ029 | full_chain_v1/seed00 | [warning] insufficient_tb_points：tb 点数仅 1（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ030 | traverse_curve_dagger_ppo/seed00 | [warning] insufficient_tb_points：tb 点数仅 27（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ031 | traverse_curve_high_level/seed00 | [warning] insufficient_tb_points：tb 点数仅 24（<50） | 建议：已知问题可接受（如 dagger 系列），否则补采数据
- DQ032 | balance_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ033 | balance_v1/seed01 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ034 | balance_v1/seed02 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ035 | full_chain_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ036 | traverse_curve_curriculum/s1 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ037 | traverse_curve_curriculum/s2 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ038 | traverse_curve_curriculum/s3 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ039 | traverse_curve_curriculum/s4 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ040 | traverse_curve_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ041 | traverse_flat_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ042 | traverse_slope_v1/seed00 | [critical] missing_report：verdict=fail 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ043 | traverse_v1/seed01 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ044 | traverse_v1/seed02 | [critical] missing_report：verdict=pass 但 reports.csv 无对应验收行 | 建议：补充正式验收报告或调整标签来源
- DQ045 | traverse/seed02 | [critical] missing_eval_data：verdict=fail 但无任何 eval 点（无法验证训练表现） | 建议：补充 eval 数据或改为 unknown

### B.异常值（1）

- DQ046 | traverse_curve_high_level/seed00 | [warning] falls_outlier：falls=20.0 超出 [0, 10] | 建议：检查验收记录

### C.时间戳连续性（14）

- DQ047 | balance/seed00 | [warning] incomplete_training：末 eval 点 4000000 与 total_steps=8000000 偏差 50%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ048 | full_chain/seed00 | [info] missing_early_eval：首个 eval 点 @1950000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ049 | traverse/seed00 | [warning] incomplete_training：末 eval 点 700000 与 total_steps=8000000 偏差 91%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ050 | traverse_curve_curriculum/s2 | [info] missing_early_eval：首个 eval 点 @1200000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ051 | traverse_curve_curriculum/s2 | [warning] incomplete_training：末 eval 点 2150000 与 total_steps=1000000 偏差 115%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ052 | traverse_curve_curriculum/s3 | [info] missing_early_eval：首个 eval 点 @2350000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ053 | traverse_curve_curriculum/s3 | [warning] incomplete_training：末 eval 点 3300000 与 total_steps=1000000 偏差 230%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ054 | traverse_curve_curriculum/s4 | [info] missing_early_eval：首个 eval 点 @3500000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ055 | traverse_curve_curriculum/s4 | [warning] incomplete_training：末 eval 点 4450000 与 total_steps=1000000 偏差 345%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ056 | traverse_curve_dagger_ppo/seed00 | [warning] incomplete_training：末 eval 点 200000 与 total_steps=2000000 偏差 90%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ057 | traverse_flat_slope/seed00 | [info] missing_early_eval：首个 eval 点 @750000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ058 | traverse_slope/seed00 | [info] missing_early_eval：首个 eval 点 @700000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期
- DQ059 | traverse_slope/seed00 | [warning] incomplete_training：末 eval 点 8000000 与 total_steps=4000000 偏差 100%（>20%） | 建议：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
- DQ060 | traverse_slope_v1/seed00 | [info] missing_early_eval：首个 eval 点 @1800000 步（>200000，前段无 eval） | 建议：可能是续训/BC 预热，确认符合预期

### D.重复数据（0）

- 无

### E.标签一致性（1）

- DQ061 | full_chain_simple/seed00 | [warning] completed_verdict_mismatch：completed=True 但 verdict=未设置（应为 pass/fail） | 建议：验收后补标或改 completed

### F.数据完整性（24）

- DQ062 | balance/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ063 | balance/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ064 | full_chain/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ065 | full_chain/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ066 | traverse/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ067 | traverse_curve/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ068 | traverse_curve/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ069 | traverse_flat_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ070 | traverse_flat_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ071 | traverse_slope/seed01 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ072 | traverse_slope/seed02 | [warning] missing_eval_for_run：runs 中有该 run 但 eval_points 无任何点 | 建议：刚启动可接受，否则补采
- DQ073 | balance/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 4000000 偏差 50%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ074 | traverse/seed00 | [warning] total_steps_mismatch：total_steps=8000000 与 eval 末点 700000 偏差 91%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ075 | traverse_curve_curriculum/s2 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 2150000 偏差 115%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ076 | traverse_curve_curriculum/s3 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 3300000 偏差 230%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ077 | traverse_curve_curriculum/s4 | [warning] total_steps_mismatch：total_steps=1000000 与 eval 末点 4450000 偏差 345%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ078 | traverse_curve_dagger_ppo/seed00 | [warning] total_steps_mismatch：total_steps=2000000 与 eval 末点 200000 偏差 90%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ079 | traverse_slope/seed00 | [warning] total_steps_mismatch：total_steps=4000000 与 eval 末点 8000000 偏差 100%（>20%） | 建议：确认续训口径（阶段 total_steps vs 累计步数）
- DQ080 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ081 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ082 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ083 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ084 | traverse/seed02 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据
- DQ085 | traverse_curve_curriculum/seed00 | [warning] report_without_eval：reports.csv 有验收行但 eval_points 无数据 | 建议：补充 eval 数据

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
15. [warning] missing_total_steps（balance_v1/seed00）：补全训练步数（或用 eval 末点推算）
16. [warning] missing_total_steps（balance_v1/seed01）：补全训练步数（或用 eval 末点推算）
17. [warning] missing_total_steps（balance_v1/seed02）：补全训练步数（或用 eval 末点推算）
18. [warning] missing_total_steps（full_chain/seed00）：补全训练步数（或用 eval 末点推算）
19. [warning] missing_total_steps（full_chain/seed01）：补全训练步数（或用 eval 末点推算）
20. [warning] missing_total_steps（full_chain/seed02）：补全训练步数（或用 eval 末点推算）
21. [warning] missing_total_steps（full_chain_v1/seed00）：补全训练步数（或用 eval 末点推算）
22. [warning] missing_total_steps（traverse/seed02）：补全训练步数（或用 eval 末点推算）
23. [warning] missing_total_steps（traverse_curve/seed01）：补全训练步数（或用 eval 末点推算）
24. [warning] missing_total_steps（traverse_curve/seed02）：补全训练步数（或用 eval 末点推算）
25. [warning] missing_total_steps（traverse_curve_dagger/seed00）：补全训练步数（或用 eval 末点推算）
26. [warning] missing_total_steps（traverse_curve_high_level/seed00）：补全训练步数（或用 eval 末点推算）
27. [warning] missing_total_steps（traverse_curve_v1/seed00）：补全训练步数（或用 eval 末点推算）
28. [warning] missing_total_steps（traverse_curve_v2/seed00）：补全训练步数（或用 eval 末点推算）
29. [warning] missing_total_steps（traverse_curve_v3/seed00）：补全训练步数（或用 eval 末点推算）
30. [warning] missing_total_steps（traverse_flat_slope/seed01）：补全训练步数（或用 eval 末点推算）
31. [warning] missing_total_steps（traverse_flat_slope/seed02）：补全训练步数（或用 eval 末点推算）
32. [warning] missing_total_steps（traverse_flat_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
33. [warning] missing_total_steps（traverse_slope/seed01）：补全训练步数（或用 eval 末点推算）
34. [warning] missing_total_steps（traverse_slope/seed02）：补全训练步数（或用 eval 末点推算）
35. [warning] missing_total_steps（traverse_slope_v1/seed00）：补全训练步数（或用 eval 末点推算）
36. [warning] missing_total_steps（traverse_v1/seed00）：补全训练步数（或用 eval 末点推算）
37. [warning] missing_total_steps（traverse_v1/seed01）：补全训练步数（或用 eval 末点推算）
38. [warning] missing_total_steps（traverse_v1/seed02）：补全训练步数（或用 eval 末点推算）
39. [warning] insufficient_eval_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
40. [warning] insufficient_eval_points（traverse_curve_dagger/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
41. [warning] insufficient_eval_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
42. [warning] insufficient_eval_points（traverse_curve_high_level/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
43. [warning] insufficient_tb_points（full_chain_v1/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
44. [warning] insufficient_tb_points（traverse_curve_dagger_ppo/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
45. [warning] insufficient_tb_points（traverse_curve_high_level/seed00）：已知问题可接受（如 dagger 系列），否则补采数据
46. [warning] falls_outlier（traverse_curve_high_level/seed00）：检查验收记录
47. [warning] incomplete_training（balance/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
48. [warning] incomplete_training（traverse/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
49. [warning] incomplete_training（traverse_curve_curriculum/s2）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
50. [warning] incomplete_training（traverse_curve_curriculum/s3）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
51. [warning] incomplete_training（traverse_curve_curriculum/s4）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
52. [warning] incomplete_training（traverse_curve_dagger_ppo/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
53. [warning] incomplete_training（traverse_slope/seed00）：确认是否提前停止/续训（续训 run 以阶段总步数为口径）
54. [warning] completed_verdict_mismatch（full_chain_simple/seed00）：验收后补标或改 completed
55. [warning] missing_eval_for_run（balance/seed01）：刚启动可接受，否则补采
56. [warning] missing_eval_for_run（balance/seed02）：刚启动可接受，否则补采
57. [warning] missing_eval_for_run（full_chain/seed01）：刚启动可接受，否则补采
58. [warning] missing_eval_for_run（full_chain/seed02）：刚启动可接受，否则补采
59. [warning] missing_eval_for_run（traverse/seed02）：刚启动可接受，否则补采
60. [warning] missing_eval_for_run（traverse_curve/seed01）：刚启动可接受，否则补采
61. [warning] missing_eval_for_run（traverse_curve/seed02）：刚启动可接受，否则补采
62. [warning] missing_eval_for_run（traverse_flat_slope/seed01）：刚启动可接受，否则补采
63. [warning] missing_eval_for_run（traverse_flat_slope/seed02）：刚启动可接受，否则补采
64. [warning] missing_eval_for_run（traverse_slope/seed01）：刚启动可接受，否则补采
65. [warning] missing_eval_for_run（traverse_slope/seed02）：刚启动可接受，否则补采
66. [warning] total_steps_mismatch（balance/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
67. [warning] total_steps_mismatch（traverse/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
68. [warning] total_steps_mismatch（traverse_curve_curriculum/s2）：确认续训口径（阶段 total_steps vs 累计步数）
69. [warning] total_steps_mismatch（traverse_curve_curriculum/s3）：确认续训口径（阶段 total_steps vs 累计步数）
70. [warning] total_steps_mismatch（traverse_curve_curriculum/s4）：确认续训口径（阶段 total_steps vs 累计步数）
71. [warning] total_steps_mismatch（traverse_curve_dagger_ppo/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
72. [warning] total_steps_mismatch（traverse_slope/seed00）：确认续训口径（阶段 total_steps vs 累计步数）
73. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
74. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
75. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
76. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
77. [warning] report_without_eval（traverse/seed02）：补充 eval 数据
78. [warning] report_without_eval（traverse_curve_curriculum/seed00）：补充 eval 数据
79. [info] missing_early_eval（full_chain/seed00）：可能是续训/BC 预热，确认符合预期
80. [info] missing_early_eval（traverse_curve_curriculum/s2）：可能是续训/BC 预热，确认符合预期
81. [info] missing_early_eval（traverse_curve_curriculum/s3）：可能是续训/BC 预热，确认符合预期
82. [info] missing_early_eval（traverse_curve_curriculum/s4）：可能是续训/BC 预热，确认符合预期
83. [info] missing_early_eval（traverse_flat_slope/seed00）：可能是续训/BC 预热，确认符合预期
84. [info] missing_early_eval（traverse_slope/seed00）：可能是续训/BC 预热，确认符合预期
85. [info] missing_early_eval（traverse_slope_v1/seed00）：可能是续训/BC 预热，确认符合预期
