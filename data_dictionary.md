# 数据字典

所有 CSV 位于 `data/datasets/`，UTF-8 BOM 编码，按 schema.py 列序输出。

## runs.csv（每个 (任务, seed) 一行）

| 列 | 类型 | 含义 | 来源 |
|---|---|---|---|
| task | str | 任务名 | 运行目录 |
| seed | str | seed 编号 | 运行目录 |
| owner | str | local / cloud | state.json |
| status | str | 运行状态 | state.json |
| attempts | int | 启动/重试次数 | state.json |
| completed | bool | 是否完成 | .completed 标记 |
| total_steps / envs / curriculum_steps / terrain / init_from | 混合 | 训练配置 | 训练日志（尽力解析，缺失为空） |
| verdict | str | 验收 pass/fail | summary.json |
| success_rate | float | 整体成功率 | summary.json |
| duration_seconds | float | 训练时长（近似） | snapshots 起止时间差 |

**建模标签**：verdict、success_rate、duration_seconds 是 v2 的目标变量。

## eval_points.csv

task、seed、timesteps（评估时步数）、mean_reward、std_reward、mean_ep_len。
来源：`rl/runs/<task>/seedNN/eval_log.csv`，每 50k 步一行。

## tb_points.csv

task、seed、step（rollout 步数）、ep_rew_mean、ep_len_mean、std、value_loss、
approx_kl、explained_variance、learning_rate、n_updates。
来源：TensorBoard 事件文件，每约 16k 步一个 rollout；每个 seed 取最新 run 目录。

## snapshots.csv

time（Unix 秒）、task、seed、timesteps、reward，以及整机资源：
cpu_percent、mem_percent、load1/5/15、mem_available_mb、mem_total_mb、
swap_used_mb、swap_total_mb、swap_percent。
来源：`rl/runs/_guard/snapshots.jsonl`，30 秒采样一次。

## reports.csv

task、seed、label（场景/整体）、verdict、success、success_rate、max_dev、
min_clear、dual_hold、recovered、settle_seconds、distance、time_to_goal、
falls、total_reward、mean_base_reward、nan。
来源：`reports/<task>/seedNN/metrics.csv` + `summary.json`。

## costs.csv（可选）

date、thread_id、turns、model、input/cached/output/reasoning/total_tokens、
cost_yuan（按 config.json 峰谷价格估算）。
来源：`~/文档/lianghua/data/usage.db`（只读）；数据库不存在时该表为空并在
summary.py 中标注。
