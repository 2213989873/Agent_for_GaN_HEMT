# PMMS 接口映射与适配评估（M7 设计输入，待评审）

日期：2026-09-25。依据：`docs/pmms/MCP_API.md`（44 工具）、`docs/pmms/MCP_INTEGRATION.md`、
pmms.exe pyc 反编译事实（任务卡16）、`docs/agent架构设计.md` v1.1。
**本文档是设计输入，评审通过前不写适配代码。**

## 1. 六类接口 × PMMS 工具映射

| 架构六类 | PMMS 对应工具 | 适配要点 |
|---|---|---|
| 数据 I/O | `load_data`(data_type: 0=SWEEP/1=SPEC/2=WAT, path) / `list_data_sources` / `get_data_detail` / `remove_data_source` / `extract_spec` / `deem`（S 参数去嵌，需 dut/open/short 三组）/ `upload_file`（1MB base64 分块）/ `download_file` | 赛题明确**测试数据不下发本地**——path 是 server 侧路径，或 `projectdir/user/` 相对路径；S 参数去嵌链路我们从未练兵 |
| 模型选型 | `list_available_models` / `load_model`(path, format=hspice) / `add_model_source`(simulator=Nano) / `list_model_sources` / `remove_model_source` / `add_devicecopy` / `clear_devicecopy` / `save_model`（**模型卡导出通道**） | 我们的 ASM-HEMT 处方（.inc）要转 hspice 格式模型卡；`ModelSuite.id` 靠 `list_available_models` 反查（返回值是文本） |
| 参数操作 | `set_param`(name, value?, min?, max?, step?) / `get_param` / `list_params` / `remove_param` | 参数值全是**字符串**；提取空间 = 经 min/max/step 注册的参数集合 |
| 拟合执行 | `view`(view_fields 五元组：filter/source/page/**selection**/prop) / `get_view_group_error` / `optimize`（同步阻塞 ≤30min）/ `start_optimize`+`get_job_status`+`cancel_job`+`dump_report`（异步）/ `save_sim_result` / `dump_view_group` | **核心差异**：优化器在 server 端（NanoSpice），不是"给参数返曲线"的 oracle；optimize 前置必须 view 且带 selection_string |
| QA 检查 | `run_qa`（同步）/ `start_qa`（异步）/ `dump_report` | 官方 QA checklist 细则待赛题 Q&A；我们的 physics_qa 可叠加在导出模型卡上本地双保险 |
| 会话管理 | `generate_project` / `open_project` / `exist_project` / `save_current_project` / `close_current_project` / `get_variable` / `set_variable` / `list_variable` / `get_job_status` | 工程是强制前置（NO_PROJECT=1）；单 session 串行，同时只有一个异步 Job |

返回值全是**人可读文本**（`content[0].text`），失败也是 `isError:false`——靠文本前缀判错：
`错误：Tool 执行失败，错误码：<n>`（9=BUSY，客户端指数退避 0.5s→10s，PMMS 自己不重试）。

## 2. 架构冲击：oracle 假设作废

M1–M6 建的闭环假设"给定参数→返回曲线"的仿真 oracle，本地 scipy least_squares 驱动。
PMMS 自带优化器/QA/仿真，无法逐字映射。两条整合路线：

- **路线 A（主）——编排 PMMS 的 optimize**：我们的价值层上移为决策层：参数族进场顺序、
  view/selection 构造、`get_view_group_error` 误差判读、QA 驳回驱动 retune、双触发器、
  预算控制、外推风险记录。这是官方 Prompt 工作流（param_optimization/qa_workflow）的预期用法。
- **路线 B（备）——`set_param` + `save_sim_result` + `download_file` 当 oracle**：
  每次残差评估 3 次调用，1500 次评估 = 4500+ 调用，延迟风险大。只作兜底与对拍验证用。

## 3. 保留 / 重写 / 新增

| 处置 | 内容 |
|---|---|
| 保留 | LangGraph 状态机骨架、QA 驳回/双触发器决策逻辑、预算计数与日志审计、熔断 A–D 框架、checkpoint/resume、提交物 Schema 校验 |
| 重写 | 工具接口层实现（McpSession→PmmsSession，签名已在 M4 定为 dict 通道，只需换实现）、误差读数来源（本地 NRMSE 计算→`get_view_group_error` 文本解析）、模型卡导出（写 .inc→`save_model`/`download_file`） |
| 新增 | 文本解析器（错误码前缀/ID 正则反查）、BUSY 退避包装、异步 Job 轮询（1–3s）、**红线计数包装层**（PMMS 无内置计数器，客户端自数落日志）、预热+代理彩排 SOP（任务卡16 已交付）、运行总结生成器（赛题第三交付物，未做） |

## 4. 工作量粗估（单人，以验收判据为准）

| 子任务 | 估时 | 验收 |
|---|---|---|
| PmmsSession + 计数/退避/文本解析包装 | 0.5–1 天 | mock server 单测 + 真链路冒烟 |
| 数据 I/O 打通（甲乙 csv→server 可载格式→load_data→view→error 读数） | 0.5–1 天 | 真链路读出误差文本 |
| 编排闭环（view→start_optimize→轮询→dump_report→save_model） | 1 天 | 甲器件真链路最小闭环跑通 |
| S 参数/Pulse I-V 补课（赛题数据形态缺口） | 0.5–1 天 | deem 链路跑通 + Pulse I-V 形态入提取 |
| 运行总结生成器 | 0.25 天 | 三交付物齐过自检 |
| 缓冲 | 1 天 | —— |

总计约 3.5–4.5 天。**前提是拿到真数据或等效练习数据**——目前甲乙器件数据在本地，
`load_data` 的 server 端路径形态需要 `upload_file` 上行或组委会环境的既有路径。

## 5. 待组委会/用户确认项

1. 测试日形态：SSH 凭证（host/user/key 或 password）何时下发？（决定包装层是否退役）
2. 赛题 Q&A 文件：官方模型卡 Schema、QA checklist 细则、S 参数是否必用
3. 测试数据在 server 侧的预置路径形态（`projectdir/user/` 约定）
4. MS_MEQLAB_CLUSTER license 缺失是否影响 RF/S 参数功能
