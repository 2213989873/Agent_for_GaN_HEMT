# GaN HEMT 建模 Agent · 2026 创芯大赛 EDA 精英挑战赛

单人参赛项目仓库。目标：构建基于 LangGraph + 国产大模型的 AI Agent，通过 Primarius Modeling MCP Server 自动完成 GaN HEMT ASM-HEMT 紧凑模型的全流程参数提取。

## 进度看板

- [ ] Phase 0 · 立项准备（9/14–9/20）
- [ ] Phase 1 · 三线打基础（9/21–10/11）
- [ ] Phase 2 · 最小闭环（10/12–11/1）
- [ ] Phase 3 · Agent 化（11/2–11/29）
- [ ] Phase 4 · 冲刺（11/30–赛前）

## 目录结构

```
gan-hemt-agent/
├── docs/            # 学习笔记、名词手册、三张专家知识表、环境搭建指南
├── examples/        # 学习期 demo（00_hello_llm.py 等）
├── src/
│   ├── agent/       # LangGraph 状态机（Phase 3 主战场）
│   ├── tools/       # MCP client 封装
│   ├── pipeline/    # 确定性建模流水线（Phase 2 主战场）
│   └── eval/        # 自建评分脚本（模拟官方公式）
├── data/            # 合成训练数据（不进 git）
├── runs/            # 运行日志与 checkpoint（不进 git）
└── tests/           # 测试
```

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 `DEEPSEEK_API_KEY`
2. `pip install -r requirements.txt`
3. `python examples/00_hello_llm.py` 验证环境

## 协作约定

- 卡住不超过 2 小时，把报错/曲线/代码发给 Kimi
- 每周日写三行进展日志（模板见 `docs/学习日志.md`）
- 三张专家知识表在 `docs/` 下持续迭代
