# 任务卡 01：LangGraph 入门实战

- **阶段**：Phase 1 · 线 A（Agent 工程）
- **布置时间**：2026-09-14（环境已提前打通，Phase 1 提前启动）
- **时间预算**：4–6 小时，可分两个晚上
- **前置条件**：`examples/00_hello_llm.py` 跑通 ✅

## 为什么先学这个

赛题限定 LangGraph / deepagents 二选一，我们选 LangGraph 状态机做主力架构——**评委要审阅你的 Agent 决策图**，状态机天然可读、可审计。本任务的四个概念（State / Node / Edge / 条件边）就是 Phase 3 全部架构的积木。

## 学习目标

亲手验证 LangGraph 四要素：

1. **State**：在节点间流转的共享数据（一个 TypedDict）
2. **Node**：干活的函数，输入 state，输出要合并进 state 的更新
3. **Edge**：固定的走向
4. **条件边（conditional edge）**：根据 state 内容动态决定走向——QA 失败回退就靠它

## 步骤

### ① 读文档（30–45 分钟）

LangGraph 官方文档的 Quickstart 和核心概念页（搜 "LangGraph quickstart"）。重点看 `StateGraph`、`add_node`、`add_edge`、`add_conditional_edges`、`compile`、`invoke` 这几个词。

### ② Demo A：纯代码状态机（无 LLM）

写 `examples/01a_state_machine.py`：

- state 里有一个数字
- 节点链：`input → double（数字翻倍）→ 判断奇偶（条件边）→ report_even / report_odd → 结束`
- 跑通并打印每一步后的 state，亲眼看到状态在流转

### ③ Demo B：LLM + 工具调用

写 `examples/01b_tool_agent.py`：

- 用 DeepSeek（OpenAI 兼容接口：`base_url="https://api.deepseek.com"`，`model="deepseek-chat"`）
- 给模型两个工具：
  - `lookup_glossary(term)`：在 `docs/名词手册.md` 里查名词，返回解释（读文件 + 字符串匹配即可，不用搞复杂）
  - `calc(expression)`：安全地计算一个算术表达式
- 测试问题：**"ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？"**
- 期望：Agent 自动先查名词手册、再调计算器、最后组织回答

### ④ 画出来

在两个脚本开头的注释里，用 ASCII 画出它们的状态图（节点 + 箭头 + 条件分支）。

## 验收标准（全部完成后发给 Kimi）

1. 两个脚本的运行输出截图/文本
2. 用 3–5 句话向 Kimi 解释：**state 是什么、它在节点间怎么流转、条件边怎么决定走向**
3. 回答一个问题：**为什么"中途崩溃后接着跑"在状态机里容易实现？**（想想 checkpoint）

## 规则与提示

- 可以用 Kimi Code 辅助写代码，但**每一行都要能讲出意思**，验收时我会抽查提问
- 卡住超过 2 小时，把报错和代码发我，别死磕
- 遇到问题先查 `docs/名词手册.md`，没有的名词补充进去

## 给 Kimi Code 的提示词（复制即用）

**Demo A：**

> 在 examples/ 下新建 01a_state_machine.py，用 LangGraph 写一个**不调用 LLM** 的纯状态机 demo：
> 1. State 用 TypedDict：value: int、log: list[str]（log 用 Annotated + operator.add 实现追加合并）
> 2. 节点链：set_input → double（value×2 并记 log）→ 条件边判断 value 奇偶 → report_even / report_odd → END
> 3. 用 7 作为输入运行，打印每个节点执行后的完整 state
> 4. 文件头部用 ASCII 注释画出节点图；中文注释；只用 langgraph 不引 langchain
> 写完运行一遍确认无误，然后用三句话向我解释 add_conditional_edges 是怎么决定走向的。

**Demo B：**

> 在 examples/ 下新建 01b_tool_agent.py，参照 LangGraph 官方 quickstart 的 Graph API 结构（llm_call 节点 + tool_node 节点 + 条件边循环）写一个工具调用 Agent：
> 1. 模型用 DeepSeek：init_chat_model("deepseek-chat", model_provider="openai", base_url="https://api.deepseek.com")，api_key 从 .env 的 DEEPSEEK_API_KEY 读取（python-dotenv）
> 2. 工具一 lookup_glossary(term: str)：读取 docs/名词手册.md，返回包含该词的行，找不到返回"未收录"
> 3. 工具二 calc(expression: str)：用 ast 模块做白名单解析（只允许数字、括号和 +-*/），**禁止用 eval**
> 4. 测试问题："ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？"
> 5. 打印每一轮的完整消息流：模型决策、工具调用参数、工具返回、最终回答
> 6. 文件头部 ASCII 画状态图；中文注释
> 写完用测试问题运行，逐行解释条件边和 ToolMessage 的作用。

**如果 AI 写的代码报 ImportError/弃用警告**：把报错原样贴回给它，补一句"我装的是最新版 langgraph，请按当前版本 API 修正"（AI 的训练数据里可能是旧版 API）。
