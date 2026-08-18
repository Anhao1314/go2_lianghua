"""数据集列定义与校验。

v1 只采集数据；schema 已预留建模标签（verdict / success_rate / duration_seconds），
后续 v2 的验收早停分类与耗时回归可直接消费这些字段。
"""

from __future__ import annotations

import pandas as pd

# 每张表：(列名, 类型, 中文说明)。顺序即 CSV 列顺序。
SCHEMA: dict[str, list[tuple[str, str, str]]] = {
    "runs": [
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号（seedNN）"),
        ("owner", "str", "训练负责机器：local / cloud"),
        ("status", "str", "state.json 中的运行状态"),
        ("attempts", "int", "启动/重试次数"),
        ("completed", "bool", "是否训练完成"),
        ("total_steps", "int", "目标总步数"),
        ("envs", "int", "并行环境数"),
        ("curriculum_steps", "int", "课程学习前 N 步关闭域随机化"),
        ("terrain", "str", "地形类型：hfield / boxes"),
        ("init_from", "str", "初始化权重路径"),
        ("verdict", "str", "验收结论 pass/fail（有报告时）"),
        ("success_rate", "float", "整体成功率（traverse 类）"),
        ("duration_seconds", "float", "训练时长秒（由 30s 快照起止时间推算，近似）"),
    ],
    "eval_points": [
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号"),
        ("timesteps", "int", "评估时总步数"),
        ("mean_reward", "float", "评估平均奖励"),
        ("std_reward", "float", "评估奖励标准差"),
        ("mean_ep_len", "float", "评估平均 episode 长度"),
    ],
    "tb_points": [
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号"),
        ("step", "int", "rollout 步数"),
        ("ep_rew_mean", "float", "rollout 平均奖励"),
        ("ep_len_mean", "float", "rollout 平均 episode 长度"),
        ("std", "float", "策略输出标准差"),
        ("value_loss", "float", "价值网络损失"),
        ("approx_kl", "float", "近似 KL 散度"),
        ("explained_variance", "float", "价值解释方差"),
        ("learning_rate", "float", "学习率"),
        ("n_updates", "int", "PPO 更新次数"),
    ],
    "snapshots": [
        ("time", "float", "采样 Unix 时间戳"),
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号"),
        ("timesteps", "float", "该 seed 当前总步数"),
        ("reward", "float", "该 seed 当前奖励值"),
        ("cpu_percent", "float", "整机 CPU 使用率"),
        ("mem_percent", "float", "整机内存使用率"),
        ("load1", "float", "1 分钟负载"),
        ("load5", "float", "5 分钟负载"),
        ("load15", "float", "15 分钟负载"),
        ("mem_available_mb", "float", "可用内存 MB"),
        ("mem_total_mb", "float", "总内存 MB"),
        ("swap_used_mb", "float", "Swap 已用 MB"),
        ("swap_total_mb", "float", "Swap 总量 MB"),
        ("swap_percent", "float", "Swap 使用率"),
    ],
    "reports": [
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号"),
        ("label", "str", "报告行标签（场景/整体）"),
        ("verdict", "str", "验收结论 pass/fail"),
        ("success", "bool", "该行是否达标"),
        ("success_rate", "float", "成功率"),
        ("max_dev", "float", "最大俯仰偏差 rad"),
        ("min_clear", "float", "最小前轮离地/基座高度 m"),
        ("dual_hold", "float", "双轮保持时长 s"),
        ("recovered", "bool", "是否恢复四轮"),
        ("settle_seconds", "float", "恢复后稳定时长 s"),
        ("distance", "float", "平均穿越距离 m"),
        ("time_to_goal", "float", "平均到达时间 s"),
        ("falls", "float", "平均摔倒次数"),
        ("total_reward", "float", "平均总奖励"),
        ("mean_base_reward", "float", "平均基础奖励"),
        ("nan", "bool", "是否出现 NaN"),
    ],
    "costs": [
        ("date", "str", "日期 YYYY-MM-DD"),
        ("thread_id", "str", "Codex 会话 thread"),
        ("turns", "int", "会话轮次数"),
        ("model", "str", "最近一次模型名"),
        ("input_tokens", "int", "输入 token 合计"),
        ("cached_tokens", "int", "缓存命中 token 合计"),
        ("output_tokens", "int", "输出 token 合计"),
        ("reasoning_tokens", "int", "推理 token 合计"),
        ("total_tokens", "int", "总 token 合计"),
        ("cost_yuan", "float", "估算成本（元）"),
    ],
    "labels": [
        ("task", "str", "任务名"),
        ("seed", "str", "seed 编号"),
        ("completed", "bool", "是否训练完成"),
        ("verdict", "str", "验收结论 pass/fail（建模标签，可人工修正）"),
        ("success_rate", "float", "整体成功率（建模标签，可人工修正）"),
        ("duration_seconds", "float", "训练时长秒（快照推算，可人工修正）"),
        ("label_source", "str", "auto=采集自动 / manual=人工锁定"),
        ("label_updated_at", "str", "标签更新时间 YYYY-MM-DD HH:MM:SS"),
    ],
}

# 幂等去重键：重复运行 collect 后行数不变
KEY_COLUMNS: dict[str, list[str]] = {
    "runs": ["task", "seed"],
    "eval_points": ["task", "seed", "timesteps"],
    "tb_points": ["task", "seed", "step"],
    "snapshots": ["time", "task", "seed"],
    "reports": ["task", "seed", "label"],
    "costs": ["date", "thread_id"],
    "labels": ["task", "seed"],
}


def table_columns(table: str) -> list[str]:
    return [col for col, _t, _d in SCHEMA[table]]


def validate_frame(frame: pd.DataFrame, table: str) -> None:
    """校验 DataFrame 列与 schema 完全一致。"""
    expected = table_columns(table)
    missing = [c for c in expected if c not in frame.columns]
    if missing:
        raise ValueError(f"{table} 缺少列: {missing}")
    extra = [c for c in frame.columns if c not in expected]
    if extra:
        raise ValueError(f"{table} 多余列: {extra}")
