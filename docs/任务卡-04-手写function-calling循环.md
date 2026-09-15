# 任务卡 04：手写 function calling 循环（裸机版 Agent）

- **阶段**：Phase 1 · 线 A 收尾
- **布置时间**：2026-09-15（任务 03 验收通过后）
- **时间预算**：2–3 小时
- **前置条件**：任务 01–03 通过 ✅

## 为什么

任务 01b 里 LangGraph 帮你转了"模型决策 → 工具执行 → 再决策"的循环。现在要**不用任何框架**手写同一个循环——拆过发动机的人，以后车坏了才会修。Phase 3 调试 Agent 时你会无数次感谢这个练习。

## 步骤（`examples/04_function_calling_loop.py`）

1. 用 `openai` SDK 的 `tools` 参数，以 JSON schema 声明两个工具：`lookup_glossary`、`calc`（函数体复用旧代码，calc 保持 ast 白名单）
2. 手写 while 循环：
   - messages + tools 发给 `deepseek-chat`
   - 若返回的 message 带 `tool_calls` → 逐个执行 → 每条结果以 `{"role": "tool", "tool_call_id": ..., "content": ...}` 追加进 messages → 继续循环
   - 不带 `tool_calls` → break，打印最终回答
3. 每轮打印：模型决策（调什么工具、什么参数）、工具回执
4. 测试问题："ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？"

## 思考题（口答给 Kimi）

把这个 while 循环的每个部分映射到任务 01b 的 LangGraph 结构：
- 循环体里的"发消息给模型" ≈ 哪个节点？
- "执行工具、追加 tool 消息" ≈ 哪个节点？
- "有没有 tool_calls" 这个 if ≈ 什么？
- messages 列表 ≈ 什么？

## 验收标准

1. 运行输出（能看到 2 轮工具调用 + 最终回答）
2. 映射问题的回答

## 给 Kimi Code 的提示词（复制即用）

> 在 examples/ 下新建 04_function_calling_loop.py：**不用 LangGraph**，只用 openai SDK 手写一个工具调用循环，让我看清 Agent 的底层原理：
> 1. client = OpenAI(base_url="https://api.deepseek.com", api_key 从 .env 读 DEEPSEEK_API_KEY，python-dotenv）
> 2. 用 chat.completions.create 的 tools 参数声明两个函数的 JSON schema：lookup_glossary(term: str)（读 docs/名词手册.md 查词）和 calc(expression: str)（ast 白名单计算，禁止 eval）
> 3. 手写 while 循环：messages + tools 发给 deepseek-chat → 若返回 message 带 tool_calls：逐个执行工具，把结果以 role="tool"、tool_call_id 对应的消息追加进 messages，继续循环；否则 break
> 4. 每轮打印模型的 tool_calls 决策和工具执行结果；循环结束打印最终回答
> 5. 测试问题："ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？"
> 中文注释。写完运行确认，然后向我解释 tool_call_id 起什么作用。
