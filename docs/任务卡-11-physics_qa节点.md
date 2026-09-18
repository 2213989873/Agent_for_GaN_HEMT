# 任务卡 11：physics_qa 节点 —— 评分公式另一半的落地

- **阶段**：Phase 3 · pipeline 雏形闭环
- **布置时间**：2026-09-18
- **前置条件**：任务卡 10-bis（QA 阈值定稿 + 撞天花板判据）
- **状态**：✅ 已完成（实战全自动走完预期剧情）

## 目标

把任务卡 10-bis 定稿的 QA 物理范围检查做成 LangGraph 正式节点，并实现完整战术链：
**QA 驳回 → 换初值重调 → 反复驳回 → 自动扩提取空间**。

## 架构（src/agent/qa_loop.py）

```
START → coarse(LLM粗调) → optimize(least_squares精修) → physics_qa
  ├─ 通过 ───────────────────────────────→ END
  ├─ 驳回(重调<2次) ──带驳回原因──→ coarse（换初值，兜底）
  └─ 驳回(≥2次=撞天花板) → expand（新参数族进场，治本）→ optimize
```

QA 规则（任务卡10-bis 任务4c）：u0∈[100e-3,250e-3]、voff∈[-4,-0.5]、rontr1∈[-3,1]，
外加"触及优化边界=补偿解嫌疑"通用告警。参数族进场顺序读知识表1。

## ✅ 实战存档（run_qa.py，乙器件，两参数起步）

```
coarse:    初值 {'voff': -2.2, 'u0': 0.15}（首轮）
optimize:  11次仿真 → voff=-2.517 u0=0.08402, NRMSE=2.70%
physics_qa: ❌ 驳回——u0 超出物理范围 [0.1, 0.25]
coarse:    初值 {'voff': -2.1, 'u0': 0.15}（带驳回史换方向）
optimize:  11次仿真 → voff=-2.518 u0=0.08397, NRMSE=2.70%（同一吸引盆）
physics_qa: ❌ 驳回——u0 超界
expand:    QA 反复驳回 → 新参数族进场 ['rontr1']（撞天花板判据）
optimize:  45次仿真 → voff=-2.2 u0=0.15 rontr1=-0.9999, NRMSE=0.00%
physics_qa: ✅ 通过
最终：NRMSE=0.0002%，三参数全部命中真值
```

## 关键观察（铁证级）

**LLM 首轮就给了真值初值 (-2.2, 0.15)，优化器仍滑向补偿解 (-2.517, 84e-3)**——
补偿解吸引盆的"引力"极强，换初值也逃不掉。这证明：
1. QA 兜底不是摆设，是必需品（没有 QA，2.70% 的补偿解就交卷了，外推还要翻倍）
2. "换初值重调"对吸引盆无效，只有"扩提取空间"能治本——战术链顺序（先兜底后治本）
   正是任务卡10-bis 规范优先级的代码化
3. 评分公式 Card = QA通过率 × (1−NRMSE) 现已完整落地为可运行代码

## 产物

- `src/agent/qa_loop.py` — physics_qa 闭环（coarse/optimize/physics_qa/expand 四节点）
- `src/pipeline/run_qa.py` — 入口
- `src/tools/sim_tools.py` 新增 `run_transfer_params`（通用参数化，含 rontr1 自动开 trapmod=2）

## 思考题

1. 如果乙器件的陷阱差异不是 rontr1 而是 a1（lexp 斜率），expand 该把它排第几顺位？
   判据该看什么？（提示：残差的 Vg 分段形状，任务10-bis 任务1的方法）
2. n_retry 阈值取 2 是拍脑袋。赛题 24h、120 参数下，这个值和时间预算怎么挂钩？
3. 当前 QA 只查单参数范围。赛题 QA 若查"曲线级"指标（单调性/kink），
   physics_qa 节点要加什么输入？
