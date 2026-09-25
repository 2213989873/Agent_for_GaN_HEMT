# -*- coding: utf-8 -*-
"""mock PMMS server（单元测试用，mcp 2.x MCPServer API）：stdio MCP server。

用法：python mock_pmms_server.py <server_side_log.jsonl>
每个收到的调用写一行 JSONL（用于"计数器读数 == 实际调用次数"对拍）。

工具行为：
- echo：成功文本 + 参数回显
- busy_flaky：前 2 次 BUSY(9)，第 3 次成功
- busy_forever：永远 BUSY（测重试耗尽）
- biz_fail：业务错误码 4（MODEL_NOT_LOADED）
- exc_fail：异常型文本（无错误码）
- start_job / get_job_status：RUNNING×2 → DONE
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

LOG = Path(sys.argv[1])
CALLS = {"busy_flaky": 0, "get_job_status": 0}

server = MCPServer("mock-pmms")


def log_call(name: str, arguments: dict) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tool": name, "args": arguments}, ensure_ascii=False) + "\n")


@server.tool()
async def echo(param_name: str = "", param_value: str = "") -> str:
    """成功回显"""
    args = {"param_name": param_name, "param_value": param_value}
    log_call("echo", args)
    return "参数设置成功\n" + json.dumps(args, ensure_ascii=False)


@server.tool()
async def busy_flaky(x: int = 0) -> str:
    """前 2 次 BUSY，第 3 次成功"""
    log_call("busy_flaky", {"x": x})
    CALLS["busy_flaky"] += 1
    if CALLS["busy_flaky"] < 3:
        return "错误：Tool 执行失败，错误码：9，错误信息：另一个操作进行中，请稍后重试"
    return "参数设置成功"


@server.tool()
async def busy_forever() -> str:
    """永远 BUSY"""
    log_call("busy_forever", {})
    return "错误：Tool 执行失败，错误码：9，错误信息：另一个操作进行中，请稍后重试"


@server.tool()
async def biz_fail() -> str:
    """业务错误码 4"""
    log_call("biz_fail", {})
    return "错误：Tool 执行失败，错误码：4，错误信息：模型未加载"


@server.tool()
async def exc_fail() -> str:
    """异常型错误文本"""
    log_call("exc_fail", {})
    return "错误：参数无效"


@server.tool()
async def start_job() -> str:
    """异步任务启动"""
    log_call("start_job", {})
    return ("任务已启动\nJob ID: 11111111-2222-3333-4444-555555555555\n\n"
            "请使用 get_job_status 工具查询进度，job_status 不为 0(RUNNING) 时停止轮询")


@server.tool()
async def get_job_status(job_id: str = "") -> str:
    """RUNNING×2 后 DONE"""
    log_call("get_job_status", {"job_id": job_id})
    CALLS["get_job_status"] += 1
    if CALLS["get_job_status"] < 3:
        return "Job 状态: RUNNING\n进度: 45%\n启动时间: 1787654321000"
    return "Job 状态: DONE\n进度: 100%\n启动时间: 1787654321000\n结束时间: 1787654381000"


if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
