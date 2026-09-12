# go2w-quant 基线模型报告

- 数据集: `dataset_2026-09-06.csv`（48 runs，36 特征）
- 生成时间: 2026-09-12
- 代码版本: 567b3ba2b898cbfa9da8af94670dba139cc63233 (dirty)
- 评估方式: 留一交叉验证；填充和标准化仅拟合每折训练样本。
- 当前为全程数据事后分析，含最终验收特征；不证明在线预测或跨任务泛化。
- 特征重要性来自单独全量拟合，不属于交叉验证结果。

> 当前样本量及验证范围有限，结果只作事后分析与基线记录，不作为训练决策依据。

## 一、verdict 分类（事后分析）

- 标签分布：pass 12 / fail 23
- LOO 逻辑回归：accuracy 0.943，f1 0.909
- 多数类 Dummy：accuracy 0.657
- 使用特征数：36

## 二、回归（success_rate / duration_seconds）

### success_rate（有效样本 35）
- LOO 线性回归：R2 -123.221，MAE 1.6
- 中位数 Dummy：MAE 0.4
- 使用特征数：36；重要特征：eval_drawdown(0.294), std_last(0.284), eval_last_timesteps(0.214), max_dev_max(0.191), progress_ratio(0.184), early_low_reward(0.169), eval_last_reward(0.157), eval_neg_ratio_recent(0.137)

### duration_seconds（有效样本 6）
- LOO 线性回归：R2 -10.103，MAE 1368361.8
- 中位数 Dummy：MAE 1037075.6
- 使用特征数：33；重要特征：eval_std_recent(148384.738), eval_neg_ratio_recent(136874.476), reward_peak_ratio(119066.722), neg_ratio_current(99027.211), eval_neg_ratio(99027.211), progress_ratio(52524.284), eval_last_timesteps(49621.945), eval_points(47217.088)

## 三、单变量相关性 Top（信息性参考）

### verdict
- reward_peak_ratio: r=0.764（n=27）
- eval_last_reward: r=0.757（n=34）
- verdict_fail_ratio: r=-0.745（n=16）
- std_last: r=0.645（n=32）
- success_rate_mean: r=0.644（n=16）
- eval_peak_reward: r=0.631（n=34）
- eval_drawdown: r=-0.566（n=34）
- eval_std_recent: r=0.515（n=34）

### success_rate
- reward_peak_ratio: r=0.776（n=27）
- eval_last_reward: r=0.754（n=34）
- success_rate_mean: r=0.732（n=16）
- eval_peak_reward: r=0.647（n=34）
- std_last: r=0.602（n=32）
- verdict_fail_ratio: r=-0.567（n=16）
- eval_drawdown: r=-0.554（n=34）
- eval_neg_ratio_recent: r=-0.55（n=34）

### duration_seconds
- eval_neg_ratio_recent: r=-0.971（n=6）
- reward_peak_ratio: r=0.803（n=6）
- neg_ratio_current: r=-0.787（n=6）
- eval_neg_ratio: r=-0.787（n=6）
- eval_std_recent: r=0.731（n=6）
- eval_drawdown: r=-0.707（n=6）
- falls_mean: r=0.57（n=5）
- progress_ratio: r=0.508（n=5）