# -*- coding: utf-8 -*-
"""P3 探针 v2：add_model_source 判决实验（每次会话先 load_model）。

用法：python p3_probe.py <model_path> <lib_name> <model_name> [param_name]
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
PROJECT = "pmms_rehearsal"


async def main() -> int:
    path, lib, model = sys.argv[1], sys.argv[2], sys.argv[3]
    param = sys.argv[4] if len(sys.argv) > 4 else "vth0"
    params = StdioServerParameters(command=PMMS,
                                   args=["--local", "--meqlab-path", WRAPPER_WIN],
                                   cwd="/home/zhengjp2/MCP/mcp")
    ledger = McpCallLedger(Path(__file__).parent / "p3_ledger.jsonl")
    async with PmmsSession(params, ledger) as s:
        r = await s.call("open_project", {"project_name": PROJECT})
        print(f"[open_project] ok={r.ok}")

        r = await s.call("load_model", {"path": path, "format": "hspice"})
        print(f"[load_model] ok={r.ok} {r.text.splitlines()[0] if r.text else ''}")
        if not r.ok:
            return 1

        r = await s.call("list_available_models")
        pairs = re.findall(r"ID:\s*(\d+),\s*路径：([^\n]+)", r.text)
        print(f"[list_available_models] {pairs}")
        suite_id = None
        for sid, p in pairs:
            if p.strip() == path:
                suite_id = int(sid)
        if suite_id is None and pairs:
            suite_id = int(pairs[-1][0])
        if suite_id is None:
            print("FAIL: suite id not found")
            return 1

        r = await s.call("add_model_source", {
            "model_suite_id": suite_id, "lib_name": lib,
            "model_name": model, "simulator": "Nano"})
        print(f"[add_model_source suite={suite_id} lib={lib} model={model}] ok={r.ok}")
        print("    " + r.text.replace("\n", "\n    ")[:500])
        if not r.ok:
            return 1
        m = re.search(r"名称：([^\n，]+)", r.text)
        src = m.group(1) if m else None
        print(f"    >>> src={src}")

        r = await s.call("set_param", {
            "model_source_name": src, "param_name": param,
            "param_value": "0.5", "param_min": 0.0,
            "param_max": 2.0, "param_step": 0.01})
        print(f"[set_param {param}=0.5] ok={r.ok} {r.text.splitlines()[0]}")

        r = await s.call("get_param", {"model_source_name": src, "param_name": param})
        print(f"[get_param {param}] ok={r.ok}")
        print("    " + r.text.replace("\n", "\n    ")[:200])

    print(f"===== PROBE DONE ledger.count={ledger.count} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
