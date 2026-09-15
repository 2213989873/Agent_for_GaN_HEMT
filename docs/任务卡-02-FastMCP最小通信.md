# 任务卡 02：FastMCP 最小通信

- **阶段**：Phase 1 · 线 A（Agent 工程）
- **布置时间**：2026-09-14（任务 01 验收通过后）
- **时间预算**：3–4 小时
- **前置条件**：任务 01 通过 ✅

## 为什么学这个

赛题里，组委会的 MeQLab 建模软件就是一台 **MCP Server**，你的 Agent 是 **MCP Client**。现在自己亲手搭一对 server/client，将来对接官方环境就是换个地址的事。这也是 Phase 2 自建 mock server 的直接预演。

## 学习目标

1. 理解 MCP 的本质：一套"工具暴露与调用"的标准协议（server 暴露工具，client 发现并调用）
2. 会用 FastMCP 写 server：装饰器暴露工具
3. 会用 FastMCP Client：列出工具清单、发起调用、读结果

## 步骤

### ① 读文档（20–30 分钟）

FastMCP 官方文档的 Quickstart（搜 "FastMCP quickstart"，认准 jlowin/fastmcp 或 gofastmcp.com）。

### ② 写 server（`examples/02_mcp_server.py`）

用 FastMCP 暴露两个工具：
- `greet(name: str)`：返回问候语
- `calc(expression: str)`：复用任务 01 的 ast 白名单计算（禁止 eval）

### ③ 写 client（`examples/02_mcp_client.py`）

用 FastMCP Client 连接你的 server（stdio 传输即可，不用搞 HTTP）：
- `list_tools()` 打印工具清单（名字 + 描述）
- 调用 `greet("小明")` 和 `calc("120 * 2")`，打印结果

### ④ 思考题（口答给 Kimi）

如果把 server 换成组委会的 MeQLab MCP Server、工具换成 `load_data / fit / qa / export_card`，**你的 client 代码大概要改几行？** 想清楚这个问题，你就明白 MCP 协议的价值了。

## 验收标准

1. client 的完整运行输出（工具清单 + 两次调用结果）
2. 思考题的回答

## 提示

- fastmcp 已在 requirements 里，确认已装：`pip show fastmcp`
- server 和 client 可以写在两个文件里分开跑，也可以 client 脚本里用 stdio 直接拉起 server 进程（推荐后者，一条命令跑通）

## 给 Kimi Code 的提示词（复制即用）

**Server：**

> 在 examples/ 下新建 02_mcp_server.py，用 FastMCP（已装在 conda 环境 gan-agent）写一个 MCP server：
> 1. 创建 FastMCP 实例，命名为 "demo-modeling-server"
> 2. 工具一 greet(name: str) -> str：返回中文问候语
> 3. 工具二 calc(expression: str) -> float：用 ast 模块白名单解析（只允许数字、括号和 +-*/），**禁止 eval**
> 4. 每个工具写清楚 docstring——MCP 会把 docstring 当作工具描述暴露给 client 和 LLM，描述质量直接决定 LLM 会不会正确选用工具
> 5. 用 stdio 方式运行（FastMCP 默认）
> 中文注释。

**Client：**

> 在 examples/ 下新建 02_mcp_client.py，用 FastMCP Client 以 stdio 方式连接并拉起同目录的 02_mcp_server.py（Client("02_mcp_server.py") 用法）：
> 1. 注意 FastMCP Client 是异步的，用 async with + asyncio.run 包一层
> 2. 先 list_tools() 打印工具清单（工具名 + 描述 + 参数签名）
> 3. 依次调用 greet("小明") 和 calc("120 * 2")，打印返回结果
> 4. 输出格式清晰，分"工具清单 / 调用1 / 调用2"三段
> 中文注释。写完运行确认，然后向我解释：client 是怎么"发现"server 上有哪些工具的？
