"""任务卡 14：MCP 适配层 —— pipeline 与传输协议的切换开关

qa_loop 的 sim_fn 只需指向本模块的 mcp_output_sim，整条闭环
（粗调/精修/QA/扩空间）即从"本地直接调 ngspice"切换为"经 MCP 远程调用"，
pipeline 代码零改动。测试日把 SERVER_PATH 换成组委会的 Primarius MCP
地址（fastmcp 支持 HTTP/SSE 传输），同样零改动。

调用计数：每次 MCP 工具调用 = 1 次，server 端持久化到 .mcp_call_count，
reset_count() 在每个器件提取开始时清零（红线按器件统计）。
"""
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "src" / "tools" / "mcp_server_mock.py"
COUNT_FILE = ROOT / "data" / "sim" / ".mcp_call_count"


def reset_count() -> None:
    """器件提取开始时清零红线计数。"""
    COUNT_FILE.unlink(missing_ok=True)


def get_count() -> int:
    return int(COUNT_FILE.read_text().strip() or 0) if COUNT_FILE.exists() else 0


async def _call(params: dict) -> np.ndarray:
    async with Client(SERVER_PATH) as client:
        r = await client.call_tool("run_iv_simulation", params)
        payload = json.loads(r.content[0].text)
        return np.array(payload["id"])


def mcp_output_sim(params: dict, tag: str) -> np.ndarray:
    """sim_fn 适配器：经 mock MCP 调用输出特性仿真（847 点）。
    签名与 run_output_selfheat_params 一致（tag 仅作日志兼容，MCP 侧用调用序号）。"""
    return asyncio.run(_call(dict(params)))
