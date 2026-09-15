# AGENTS.md · 给任何 AI 编码助手的项目交接说明

> 任何 AI 工具（Kimi Code / Kimi Work / 其他）接手本仓库时，**先读本文件，再读 `docs/总体规划.md`**。
> 本文件随项目演进持续更新，最后更新：2026-09-14（Week 0）。

## 1. 项目目标（一句话）

2026 中国研究生创"芯"大赛·EDA 精英挑战赛（上海概伦电子命题）：构建基于 **LangGraph + 国产大模型 API** 的 AI Agent，通过组委会的 **Primarius Modeling MCP Server** 远程调用 MeQLab，在测试日 24 小时内对 2 个未知 GaN HEMT 器件**全自动**完成 ASM-HEMT 紧凑模型参数提取，交付模型卡 + 运行日志。

## 2. 三条总策略（任何代码改动不得违背）

1. **QA 全过 > 曲线极致贴合**（QA 通过率是评分乘性因子）
2. **不偏科**：流程对两个性格不同的器件都要稳健（总分含 0.3 × min 项）
3. **稳健 > 聪明**：LLM 只做"有限选项中的决策"；数值计算、流程控制、拟合调用一律用确定性代码

## 3. 红线（违反即 0 分）

- 每个测试器件 MCP 工具调用 ≥ 10 次，且日志可自证
- 全程必须真实调用指定国产大模型 API（DeepSeek / Qwen / GLM / Kimi / MiniMax）
- 测试日 24h 窗口内全自动；赛前交代码仓库 + 架构图

## 4. 目标架构（LangGraph 状态机）

```
load_data → analyze_data → init_params → extract_dc → extract_cv → extract_rf
    → physics_qa →（通过）→ finalize_card → write_logs
                 ↘（失败）→ retune_decide → 回退到对应 extract_* 节点
```

横切：checkpoint 持久化、指数退避重试、token/时间预算监控、全程日志。
详细节点职责见 `docs/总体规划.md` 第 1 节。

## 5. 当前状态与下一步

- **当前阶段**：Phase 2 启动（Phase 1 已于 9/15 提前收官：任务 01 LangGraph ✅ / 02 FastMCP ✅ / 03 器件知识 ✅ / 04 手写 function calling 循环 ✅）
- **基建**：服务器 conda 环境 `gan-agent`；GitHub 私有仓备份链 ✅；文档同步走"同步命令.txt"粘贴机制
- **进行中**：任务 05 · 仿真环境搭建 ngspice + OpenVAF + ASM-HEMT VA 模型（见 `docs/任务卡-05-仿真环境搭建.md`）
- **待办**：确认官方测试日日期（需本人查赛题 Q&A）
- **下一步**：任务 06 · 用 ASM-HEMT 合成 2 个"性格不同"的虚拟器件数据集
- **阶段定义与 Checkpoint**：见 `docs/总体规划.md` 第 2 节，完成一个勾一个

## 6. 目录与关键文档

| 路径 | 内容 |
|---|---|
| `docs/总体规划.md` | **主规划**：12 周 5 阶段、风险表、协作协议 |
| `docs/名词手册.md` | 器件/建模/AI 名词白话解释 |
| `docs/知识表1~3` | 提参顺序 / 参数-曲线映射 / QA 修复映射（Phase 3 填写，Agent 决策的核心知识） |
| `docs/学习日志.md` | 每周进展记录 |
| `src/agent/` | LangGraph 图（Phase 3） |
| `src/pipeline/` | 确定性建模流水线（Phase 2） |
| `src/tools/` | MCP client 封装（Phase 1–2） |
| `src/eval/` | 自建评分脚本，模拟官方公式 |

## 7. 编码约定

- 开发环境：**远程 Linux 服务器（A100，VS Code Remote-SSH）**，服务器上仓库路径 `~/projects/gan-hemt-agent`；GitHub 私有仓库为同步中枢
- Python 3.10+；依赖见 `requirements.txt`；一律在 `.venv` 虚拟环境中运行
- API key 只放 `.env`（已被 git 忽略），**绝不写进代码**；每台机器各自重建 `.env`
- 日志与 checkpoint 写 `runs/`；数据写 `data/`（均不入 git）
- 每个阶段完成时更新本文件第 5 节
