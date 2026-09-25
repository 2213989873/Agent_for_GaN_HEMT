# -*- coding: utf-8 -*-
"""P2 真链路冒烟（M7 子任务1 验收判据之二）。

链路：python → pmms.exe --local → meqlab-wrapper.exe(代理) → 预热 MeQLab(gRPC 2008)
前置：先跑 warm_start.sh 等到 GRPC_PORT_LISTENING。

动作（不调用 optimize；不动 ground truth 卡——jia.inc 只读）：
  exist_project → generate_project(若不存在) → load_model(jia.inc)
  → list_available_models → add_model_source → set_param(voff) → get_param(voff)
验收：建/开工程 + set/get 往返成功；审计日志含时间戳/工具名/参数/返回哈希；
  计数器读数 == 实际调用次数。
"""
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp import StdioServerParameters  # noqa: E402
from src.pmms import McpCallLedger, PmmsSession  # noqa: E402

PMMS = "/home/zhengjp2/MCP/mcp/pmms.exe"
WRAPPER_WIN = r"D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\meqlab-wrapper.exe"
JIA_INC = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia.inc"
MODEL_PATH = sys.argv[1] if len(sys.argv) > 1 else JIA_INC
PROJECT = "pmms_rehearsal"
LOG = Path(__file__).parent / "p2_ledger.jsonl"

CALLS_MADE = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None):
    global CALLS_MADE
    CALLS_MADE += 1
    r = await s.call(tool, args)
    print(f"--- [{CALLS_MADE}] {tool} ok={r.ok} code={r.error_code} wire={r.wire_calls}")
    print("    " + r.text.replace("\n", "\n    ")[:400])
    return r


async def main() -> int:
    params = StdioServerParameters(
        command=PMMS,
        args=["--local", "--meqlab-path", WRAPPER_WIN],
        cwd="/home/zhengjp2/MCP/mcp",
    )
    ledger = McpCallLedger(LOG)
    async with PmmsSession(params, ledger) as s:
        r = await step(s, "exist_project", {"project_name": PROJECT})
        if "否" in r.text:
            r = await step(s, "generate_project", {"project_name": PROJECT})
            if not r.ok:
                return fail("generate_project 失败")
        else:
            r = await step(s, "open_project", {"project_name": PROJECT})
            if not r.ok:
                return fail("open_project 失败")

        r = await step(s, "load_model", {"path": JIA_INC, "format": "hspice"})
        if not r.ok:
            return fail("load_model 失败（hspice 格式/asmhemt 模型名兼容性存疑）")

        r = await step(s, "list_available_models")
        pairs = re.findall(r"ID:\s*(\d+),\s*路径：([^\n]+)", r.text)
        suite_id = None
        for sid, p in pairs:
            if p.strip() == MODEL_PATH:
                suite_id = int(sid)
        if suite_id is None and pairs:
            suite_id = int(pairs[-1][0])  # 兜底取最后一个
        if suite_id is None:
            return fail("ModelSuite.id 反查失败")

        r = await step(s, "add_model_source", {"model_suite_id": suite_id})
        m = re.search(r"名称：([^\n，]+)", r.text)
        if not (r.ok and m):
            return fail("add_model_source 失败")
        src = m.group(1)
        print(f"    >>> model_source_name = {src}")

        # proto3 坑（API §6.2）：min/max/step 显式全传
        r = await step(s, "set_param", {
            "model_source_name": src, "param_name": "voff",
            "param_value": "-2.0", "param_min": -3.0,
            "param_max": 0.0, "param_step": 0.01})
        if not r.ok:
            return fail("set_param 失败")

        r = await step(s, "get_param", {"model_source_name": src, "param_name": "voff"})
        if not (r.ok and "-2" in r.text):
            return fail("get_param 回读不符")

    print(f"\n===== SMOKE PASS: ledger.count={ledger.count} calls_made={CALLS_MADE} =====")
    if ledger.count != CALLS_MADE:
        print("FAIL: 计数器与实际调用不一致")
        return 1
    return 0


def fail(msg: str) -> int:
    print(f"\n===== SMOKE FAIL: {msg} =====")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
