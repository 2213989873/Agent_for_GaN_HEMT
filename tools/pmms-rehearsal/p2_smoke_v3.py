# -*- coding: utf-8 -*-
"""P2 真链路冒烟 v3：add_model_source 成功后 list_params，再测 set/get。"""
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
LOG = Path(__file__).parent / "p2_v3_ledger.jsonl"

CALLS_MADE = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None):
    global CALLS_MADE
    CALLS_MADE += 1
    r = await s.call(tool, args)
    print(f"--- [{CALLS_MADE}] {tool} ok={r.ok} code={r.error_code} wire={r.wire_calls}")
    print("    " + r.text.replace("\n", "\n    ")[:800])
    return r


def fail(msg: str) -> int:
    print(f"\n===== SMOKE FAIL: {msg} =====")
    return 1


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

        r = await step(s, "add_model_source", {
            "model_suite_id": suite_id,
            "lib_name": "tt",
            "model_name": "jiamod",
        })
        if not r.ok:
            return fail("add_model_source 失败")
        m = re.search(r"名称：([^\n，]+)", r.text)
        src = m.group(1).strip() if m else "jiamod_tt_N"
        print(f"    >>> model_source_name = {src}")

        r = await step(s, "list_params", {"model_source_name": src})
        if not r.ok:
            return fail("list_params 失败")

        # 从返回里抓前几个参数名，挑一个试写
        params_found = re.findall(r"-\s*(\w+):", r.text)
        print(f"    >>> 发现参数: {params_found[:20]}")

        # 优先试这些常见 ASM-HEMT 参数
        candidates = ["vto", "voff", "u0", "tbar", "rth0", "cgd0", "cgs0", "mm", "beta"]
        test_param = None
        for c in candidates:
            if c in params_found:
                test_param = c
                break
        if not test_param and params_found:
            test_param = params_found[0]
        if not test_param:
            return fail("没有可用参数")

        print(f"\n>>> 测试参数: {test_param}")
        r = await step(s, "get_param", {"model_source_name": src, "param_name": test_param})
        original = r.text.strip() if r.ok else ""

        r = await step(s, "set_param", {
            "model_source_name": src, "param_name": test_param,
            "param_value": "1.23", "param_min": 0.0,
            "param_max": 10.0, "param_step": 0.01})
        if not r.ok:
            return fail("set_param 失败")

        r = await step(s, "get_param", {"model_source_name": src, "param_name": test_param})
        if not (r.ok and "1.23" in r.text):
            return fail(f"get_param 回读不符 (原值={original}, 回读={r.text.strip()})")

    print(f"\n===== SMOKE PASS: ledger.count={ledger.count} calls_made={CALLS_MADE} =====")
    if ledger.count != CALLS_MADE:
        print("FAIL: 计数器与实际调用不一致")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
