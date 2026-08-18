# go2w-quant 基线模型报告

- 数据集: `screened_dataset_2026-08-18.csv`（14 runs，39 特征）
- 生成时间: 2026-08-18

> 当前样本量远低于可训练门槛，结果只作管线验证与基线记录，不作为训练决策依据。

## 一、verdict 分类（验收早停）

- 标签分布：pass 1 / fail 2
- 样本不足（门槛：正负样本各 ≥2），未训练模型。

## 二、回归（success_rate / duration_seconds）

### success_rate（有效样本 0）
- 样本不足（门槛：≥6），未训练模型。

### duration_seconds（有效样本 7）
- LOO 线性回归：R2 -0.856，MAE 162080.8
- 中位数 Dummy：MAE 203534.3
- 使用特征数：36；重要特征：mem_percent_max(43632.035), verdict_fail_ratio(31570.243), idle_minutes(27808.84), eval_slope_per_1e6(23117.72), collapse_ratio(18138.277), eval_std_recent(15414.346), max_dev_max(15198.002), timesteps_growth(13816.927)

## 三、单变量相关性 Top（信息性参考）

### verdict
- verdict_fail_ratio: r=-1.0（n=3）
- idle_minutes: r=0.999（n=3）
- snapshot_count: r=0.999（n=3）
- best_step: r=0.998（n=3）
- eval_neg_ratio_recent: r=0.982（n=3）
- approx_kl_last: r=-0.974（n=3）
- stall_minutes: r=0.941（n=3）
- std_last: r=-0.909（n=3）

### success_rate
- 无可计算相关性的特征。

### duration_seconds
- time_span_minutes: r=1.0（n=7）
- falls_mean: r=-0.998（n=3）
- success_rate_mean: r=0.998（n=3）
- mem_percent_max: r=0.989（n=7）
- swap_percent_max: r=0.989（n=7）
- snapshot_count: r=0.81（n=7）
- verdict_fail_ratio: r=-0.67（n=3）
- eval_peak_reward: r=0.585（n=7）