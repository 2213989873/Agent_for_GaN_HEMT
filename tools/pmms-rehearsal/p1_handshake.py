# -*- coding: utf-8 -*-
"""彩排 P1：真 PMMS MCP 握手 + 工具清单核对
链路：Python(mcp stdio client) -> pmms.exe(Win, WSL interop) -> wrapper.bat -> wsl.exe -> Linux MeQLab(gRPC 127.0.0.1)
"""
import asyncio
import sys
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

WRAPPER_WIN = r"D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\meqlab-wrapper.exe"


async def main() -> int:
    params = StdioServerParameters(
        command="/home/zhengjp2/MCP/mcp/pmms.exe",
        args=["--local", "--meqlab-path", WRAPPER_WIN],
        cwd="/home/zhengjp2/MCP/mcp",
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=120) as session:
            print("[P1] initializing (timeout 120s)...", flush=True)
            init = await session.initialize()
            print(f"[P1] initialize OK: server={init.server_info.name} version={init.server_info.version}", flush=True)
            print(f"[P1] protocolVersion={init.protocol_version}", flush=True)

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"[P1] tools count = {len(names)}", flush=True)
            for n in sorted(names):
                print(f"  - {n}", flush=True)

            # 顺手核对 prompts / resources
            try:
                prompts = await session.list_prompts()
                print(f"[P1] prompts = {[p.name for p in prompts.prompts]}", flush=True)
            except Exception as e:
                print(f"[P1] list_prompts failed: {e}", flush=True)
            try:
                res = await session.list_resources()
                print(f"[P1] resources = {[str(r.uri) for r in res.resources]}", flush=True)
            except Exception as e:
                print(f"[P1] list_resources failed: {e}", flush=True)
    print("[P1] session closed cleanly", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
