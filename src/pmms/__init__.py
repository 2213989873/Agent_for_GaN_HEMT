"""PMMS MCP 客户端包装层（M7 子任务1）。

职责边界（只做包装，不做决策）：
- dict 通道调用 PMMS 工具
- 红线计数 + 审计日志（每次真实 MCP 调用落 JSONL，含 BUSY 重试）
- BUSY(9) 指数退避（PMMS 自己不重试，API 文档 §并发模型 明确要求客户端做）
- 错误码文本前缀解析（PMMS 返回值全是人可读文本，isError 不可靠）
- 异步 Job 轮询（start_optimize/start_qa → get_job_status）
"""
from .session import (
    JobResult,
    McpCallLedger,
    PmmsSession,
    ToolResult,
    parse_result_text,
)

__all__ = [
    "JobResult",
    "McpCallLedger",
    "PmmsSession",
    "ToolResult",
    "parse_result_text",
]
