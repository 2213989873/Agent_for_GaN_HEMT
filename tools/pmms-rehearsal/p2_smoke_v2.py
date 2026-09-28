# -*- coding: utf-8 -*-
"""P2 真链路冒烟 v2：验证 jia.inc 加 .lib 包装后 add_model_source 是否成功。"""
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
JIA_INC = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_with_lib.inc"
PROJECT = "pmms_rehearsal"
LOG = Path(__file__).parent / "p2_v2_ledger.jsonl"

CALLS_MADE = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None):
    global CALLS_MADE
    CALLS_MADE += 1
    r = await s.call(tool, args)
    print(f"--- [{CALLS_MADE}] {tool} ok={r.ok} code={r.error_code} wire={r.wire_calls}")
    print("    " + r.text.replace("\n", "\n    ")[:500])
    return r


def fail(msg: str) -> int:
    print(f"\n===== SMOKE FAIL: {msg} =====")
    return 1


async def try_add_source(s: PmmsSession, suite_id: int, label: str, extra: dict):
    print(f"\n>>> 尝试 {label}: add_model_source({extra})")
    r = await step(s, "add_model_source", {"model_suite_id": suite_id, **extra})
    if r.ok:
        m = re.search(r"名称：([^\n，]+)", r.text)
        if m:
            print(f"    >>> model_source_name = {m.group(1)}")
            return m.group(1)
    return None


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
            return fail("load_model 失败")

        r = await step(s, "list_available_models")
        pairs = re.findall(r"ID:\s*(\d+),\s*路径：([^\n]+)", r.text)
        suite_id = None
        for sid, p in pairs:
            if JIA_INC in p.strip():
                suite_id = int(sid)
        if suite_id is None and pairs:
            suite_id = int(pairs[-1][0])
        if suite_id is None:
            return fail("ModelSuite.id 反查失败")

        # 尝试多种参数组合
        src = None
        src = src or await try_add_source(s, suite_id, "默认参数", {})
        src = src or await try_add_source(s, suite_id, "显式 model_name", {"model_name": "jiamod"})
        src = src or await try_add_source(s, suite_id, "显式 lib+model", {"lib_name": "tt", "model_name": "jiamod"})
        src = src or await try_add_source(s, suite_id, "显式 lib+model+simulator", {"lib_name": "tt", "model_name": "jiamod", "simulator": "Nano"})

        if not src:
            return fail("add_model_source 所有参数组合均失败")

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


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
