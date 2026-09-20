# Agent 架构设计（评审稿，审过才准进 M1）

> 版本 v1.1 · 2026-09-20 · 教练：Kimi ｜ 执行：zhengjp
> v1.1 修订记录（评审两条意见，均已源码核实成立）：① §4 对称性检查物理定义修正（镜像→相对一致性+默认不启用，证据 asmhemt.va 495/499/505/592 行源漏不对称+漏侧场板）；② §3 拟合执行接口签名修正（参数名出签名，统一 dict 通道）。
> 依据：全部结论来自任务卡 01–15 实战存档与仓库源码（各条注明出处），不接受凭记忆发挥。
> 目标：满足赛题硬要求——LangGraph 状态机、国产 LLM 在环、MCP 工具调用（≥10 次/器件）、多轮迭代、异常重试、状态持久化、日志可审计。

---

## 1. 状态 Schema（`S_agent`）

主图状态。字段即教训——每个字段都能指到一条实战存档：

| 字段 | 类型 | 为什么存在（出处） |
|---|---|---|
| `device_id` | str | 流程以器件为参数，同一套代码跑双器件不偏科（卡12 Part A） |
| `data_forms` | dict[str, dict] | 已加载数据形态注册表：`{form: {path, n_points, bias_spec}}`；load_data 产出，四类数据都要装（总体规划§1） |
| `active_form` | str | 当前提取用哪种数据形态；sim_fn 与数据形态解耦是卡12 的关键泛化 |
| `sim_handle` | object | 工具会话句柄（接口层§3），协议无关——本地 mock 与真 MCP 同签名（卡14） |
| `params_space` | list[str] | 当前提取参数集；子集拟合有"未建模差异天花板"，必须显式记录谁在空间里（卡10 事实核查） |
| `values` | dict | 当前参数值（初值/精修结果） |
| `fit_hist` | list[dict] | **拟合历史** `{params, nrmse, form}` 配对记录——无配对历史 LLM 必震荡（卡09 三件套事件） |
| `best_values` / `best_rmse` | dict / float | 历史最优交卷，不取末轮（卡09 三件套2） |
| `qa_pass` / `violations` / `qa_report` | bool / list / dict | QA 状态与驳回原因，路由依据（卡11） |
| `n_retry` | int | 本空间内重调次数；≥2=撞天花板，扩空间判据（卡11） |
| `budget` | dict | **预算计数** `{mcp_calls, llm_calls, sim_count, t0}`——红线每器件 MCP≥10 次要落盘自证（卡14），时间预算是卡13 旋钮的前提 |
| `rmse` | float | 当前 NRMSE |
| `log` | list[str] | 审计日志，write_logs 提交物的数据源（赛题提交物要求） |
| `final_card` | dict | 终局模型卡（finalize_card 产出） |

checkpoint 持久化：langgraph-checkpoint 4.2.0 已装未用（pip list 实测），M1 接入——中断续跑是 24h 作战的保命能力。

## 2. 节点图

### 2.1 主图（main_graph.py，新建）

```
START → session_open → load_data → analyze_data → init_params
      → extract_loop（子图，按数据形态轮转）
      → finalize_card → write_logs → session_close → END
```

| 节点 | 类型 | 职责 | 失败路由 |
|---|---|---|---|
| session_open | 确定性 | 开工具会话、预算计数清零（reset_count，卡14 模式） | 连不上→retry 指数退避 |
| load_data | 确定性 | 加载各形态数据入 data_forms，完整性检查（点数/量纲/符号约定） | 数据异常→abort 人工介入 |
| analyze_data | **LLM** | 看曲线特征做签名自检（自热下垂？陷阱迹象？知识表3 附表），决定参数族进场提示 | LLM 失效→跳过（默认顺序照样跑，卡11 证明不依赖 LLM 质量） |
| init_params | 规则+LLM | 给当前 params_space 初值；LLM 失败回退 DEFAULTS（qa_loop 已有此容错） | 回退默认初值 |
| extract_loop | **子图** | 见 2.2 | 见 2.2 |
| finalize_card | 确定性 | 取 best_values 生成 ASM-HEMT 模型卡 + Schema 校验 | 校验失败→回 best 上一档 |
| write_logs | 确定性 | 汇总 MCP 调用记录、LLM 统计、决策摘要（log 字段天然就是） | —— |
| session_close | 确定性 | 核对红线计数 ≥10，不足自动补外推验证点（卡14 §4 保底条款） | 计数不足→自动补测 |

### 2.2 extract 子图（复用 qa_loop.build，已三器件验证）

```
coarse(LLM粗调) → optimize(least_squares精修) → qa_check
  ├─ 通过 & NRMSE达标 ──→ 出子图（下一形态/ finalize）
  ├─ 通过 & 未达标 ────→ expand（触发器2，卡13）→ optimize
  ├─ 驳回 & n_retry<2 ─→ coarse（换初值兜底，卡11）
  └─ 驳回 & n_retry≥2 ─→ expand（撞天花板治本，卡11）→ optimize
```

- expand 按 PARAM_ENTRY_ORDER 进场，耗尽即停（qa_loop.py `_has_remaining` 已有）
- 数据形态轮转顺序：dc_transfer → dc_output → cv → pulse（知识表1 提参顺序的代码化；cv/pulse 为 M3 内容）
- 每节点 try/except → retry 节点：指数退避，预算计数 +1；连续 3 次失败 → 交 best_values 保底（卡15 熔断 B 的代码化）

## 3. 工具接口层（六类，对标赛题描述的 MeQLab 功能类别）

约定（卡14 验证过的模式）：**签名不变，只换实现**。mock 列=本地 ngspice 实现（现状），real 列=组委会 Primarius MCP（测试日按文档接线）。

| # | 类别 | 接口签名 | mock 实现（现状） | real 实现 |
|---|---|---|---|---|
| 1 | 数据I/O | `load_measurement(device_id, form, bias_spec) -> {x, y, meta}` | 读 `data/devices/<dev>/*.csv` | 待真 server 文档（未验证） |
| 2 | 模型选型 | `select_model(name="asmhemt", switches: dict) -> handle` | 渲染 .model 行开关（rdsmod/trapmod/shmod，sim_tools.py 模式） | 待真 server 文档（未验证） |
| 3 | 参数操作 | `set_params(handle, params: dict)` / `get_defaults(name) -> dict` | 渲染 .inc/.model 参数；DEFAULTS 读 asmhemt.va 默认值 | 待真 server 文档（未验证） |
| 4 | 拟合执行 | `run_simulation(handle, sim_spec: {form, sweep}) -> arrays`。**v1.1 修订（评审意见2）**：参数一律经第 3 行 `set_params(handle, dict)` 的 dict 通道进入，**参数名永不进工具签名**——卡14 的 `run_iv_simulation(voff, u0, rontr1?, rth0?)` 是 2 参数演示签名，扩到 120 参数就要重写一百次，违背本表"签名不变"约定，已废止；M4 时 mock server 工具相应重构为 `run_simulation(params: dict, sim_spec: dict)` | ngspice 网表生成+批跑（sim_tools.py 六函数） | 组委会远程仿真 |
| 5 | QA检查 | `qa_check(values, curves, level: "param"\|"curve") -> {pass, violations[]}` | 参数级在客户端确定性计算（qa_loop.physics_qa，已验证）；曲线级客户端自算（§4） | 若真 server 提供 QA 服务则对拍，否则纯客户端 |
| 6 | 会话管理 | `session_open(cfg)` / `session_close()` / `get_call_count() -> int` / `reset_count()` | 已实现：计数落盘 `data/sim/.mcp_call_count`（mcp_sim.py，卡14 验证 64 次） | 同签名接真 server |

## 4. QA Validator 设计

阈值一律从知识表3 来；已实战的标 ✅，未实战的标 ⚠️（阈值初定，M2/M3 标定后回填知识表3 待填行）。

| 检查项 | 级别 | 规则 | 状态 |
|---|---|---|---|
| 参数物理范围 | 参数 | voff(D-mode)∈[-4,-0.5]V；u0∈[100e-3,250e-3]m²/V·s；rontr1∈[-3,1]；rth0∈[0.5,100]K/W | ✅ 已实战（卡11/12/13） |
| 触优化边界告警 | 参数 | 解触 OPT_BOUNDS 边界=补偿解嫌疑（qa_loop.py BOUND_TOL=1e-3） | ✅ 已实战（卡10-bis 定稿） |
| 单调性 | 曲线 | 转移特性 Id-Vg 要求单调不降（容差相对峰值 0.1%）；**输出特性饱和区除外——自热下垂是合法负微分**（卡07③ -2.8% 签名），故单调性按形态分区执行 | ⚠️ 阈值初定，未实战 |
| 对称性 | 曲线 | **v1.1 修订（评审意见1，源码铁证）**：物理镜像定义已废弃——GaN HEMT 源漏本就不对称（asmhemt.va:495/496 ns0accs/ns0accd、499/500 u0accs/u0accd、505/506 lsg/ldg 分开建模；592/593 fp1mod=漏侧场板），±Vd 镜像会把"物理正确的不对称"误杀。新定义：**相对一致性**——模型卡的±Vd 不对称度须与实测数据的不对称度一致（模型有不对称自由度，不对称本身可拟合）；阈值待标定，且**默认不启用**，等赛题 Q&A 明确"对称性"确切含义后再开 | ⚠️ 定义已修订，未实战 |
| kink 检测 | 曲线 | 分段线性残差突变 >3σ 报警 | ⚠️ 阈值初定，未实战 |

设计约束：曲线级检查输出 violations 进与参数级同一条路（驳回→coarse/expand），不新增路由分支。

## 5. 里程碑分解（验收判据 = 跑什么命令、看什么数值）

| 里程碑 | 内容 | 验收判据（命令 + 预期数值） | 状态 | 验收证据 commit |
|---|---|---|---|---|
| **M1** | **甲器件最小全流程无人干预跑通**（主图+extract 子图+checkpoint，2–3 参数族 voff/u0[/rontr1]） | `python src/pipeline/run_agent.py --device jia` 全程无人干预；NRMSE ≤0.01%（卡12 基准 0.0000%/6 次仿真）；QA 全过；日志含预算计数；kill 后 `--resume` 续跑成功 | **已验收**（2026-09-20：0.0000%/QA ✅/计数 18≥10；强杀续跑成功；回归双器件绿） | `3e7196c` |
| M2 | 乙器件全流程（自热+陷阱，转移+输出两形态轮转） | `python src/pipeline/run_agent.py --device yi` 无人干预；NRMSE ≤0.6%（卡13/14 基准）；调用计数 ≥10 且落盘自证；expand 双触发器日志可审 | 未开始 | —— |
| M3 | C-V 形态纳入提取（电容族进场，知识表1/2 回填） | `--device jia --forms dc_transfer,cv` 双形态闭环；C-V 拟合 NRMSE 达标线 M3 开工时标定（当前未验证）；知识表1/2 电容行填写并 commit | 未开始 | —— |
| M4 | MCP 链路全流程（接口§3 不变，mock 切换演示） | `run_agent.py --device yi --via-mcp`：结果与 M2 本地直连一致（卡14 零偏差基准 0.6002%）；计数文件 ≥10 | 未开始 | —— |
| M5 | 双器件连跑 + 提交物生成 | `run_agent.py --devices jia,yi` 一条命令跑完；产出两份模型卡 + 运行日志包（MCP 记录/LLM 统计/决策摘要）；`finalize_card` Schema 校验通过 | 未开始 | —— |
| M6 | 24h 作战 dry run（按任务卡15 时间表压缩） | 作战手册 T0–T5 全块演练记录入档；熔断 A–D 各至少模拟触发一次并有处置证据 | 未开始 | —— |

## 6. 风险清单与熔断策略

| 风险 | 熔断/处置 | 出处 |
|---|---|---|
| LLM 输出非法 JSON | 解析失败回退 DEFAULTS 初值（qa_loop.coarse 已有容错） | qa_loop.py |
| LLM API 全挂 | coarse 降级默认初值，纯优化器+QA+expand 闭环 | 卡15 熔断 C |
| 补偿解吸引盆 | QA 物理范围兜底 + 撞天花板扩空间 | 卡10/11 |
| QA 漏网补偿解 | 触发器2（NRMSE 未达标也扩空间） | 卡12→13 |
| 无限扩空间死循环 | PARAM_ENTRY_ORDER 耗尽即停，交 best_values | qa_loop._has_remaining |
| 预算耗尽（时间/调用） | 每节点检查 budget，超限交 best_values + 风险记录 | 卡13 旋钮 + 卡15 熔断 B |
| MCP 传输差异 | 接口层§3 吸收，pipeline 不动 | 卡14 §5 |
| 真实器件新签名（kink/RF） | analyze_data 签名自检 + 残差分段归因法 | 卡10-bis 任务1 |
| 进程中断 | checkpoint 持久化 + --resume | M1 接入 |
| 曲线级 QA 误伤合法签名（自热下垂） | 单调性按形态分区，饱和区豁免 | §4 |

## 7. 现状盘点（复用 / 重写 / 新建）

**复用（已实战验证，不动）**：
- `src/agent/qa_loop.py`（185 行）——extract 子图本体，四节点+双触发器，三器件验证（卡11/12/13）
- `src/tools/sim_tools.py`（185 行）——mock 实现层，六函数覆盖转移/输出/自热/通用参数化
- `src/eval/metrics.py`（12 行）——NRMSE 口径与赛题同款
- `src/tools/mcp_server_mock.py` / `mcp_sim.py`——M4 的协议层与计数机制（卡14 验证）
- `run_qa.py / run_qa_output.py / run_qa_selfheat.py / run_qa_mcp.py`——降级为回归测试脚本（每次改 qa_loop 后必跑）

**重写（教学原型，存档不删、不再演进）**：
- `src/agent/mini_loop.py` / `dual_loop.py`——单/双参数 LLM 裸循环，被 qa_loop 取代（卡09/10 教学价值已入档）
- `src/pipeline/run_hybrid.py / run_hybrid3.py`——混合架构实验脚本，逻辑已吸收进 qa_loop

**新建（M1 范围）**：
- `src/agent/main_graph.py`——主图（§2.1）
- `src/tools/interface.py`——六类工具接口定义（§3），mock 实现先包 sim_tools
- `src/agent/qa_validator.py`——曲线级检查（§4），参数级仍用 qa_loop 内既有逻辑
- `src/pipeline/run_agent.py`——唯一入口（--device/--forms/--via-mcp/--resume）
- checkpoint 接入 langgraph-checkpoint（已装）
