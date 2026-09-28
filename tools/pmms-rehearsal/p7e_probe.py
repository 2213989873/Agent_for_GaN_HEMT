# -*- coding: utf-8 -*-
"""P7e 对照实验 v2：修 filter 歧义（type,op 精确选 Ordinary Page）后重判 nan 责任方。

P7d 教训：官方 iv_demo 有 6 个同名 filter 页，"name,iv_demo" 可能抓到非 Sweep 页
导致 0 视图。本探针 filter_string 首选 "type,op,name,iv_demo"。
判决不变：官方组合拿到数值 → nan 责任在我们 ASM-HEMT 卡；官方也 nan/空 → 环境/引擎。
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
CARD = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/nmos_wrapped.inc"
DEMO_IV = ("/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/data/mosfet/nmos/iv/25/"
           "w=9.0,t=25.0,l=9.0.pms")
LOG = Path(__file__).parent / "p7e_ledger.jsonl"
CALLS = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None, show: int = 700):
    global CALLS
    CALLS += 1
    r = await s.call(tool, args)
    print(f"--- [{CALLS}] {tool} {args or {}} -> ok={r.ok} code={r.error_code}")
    print("    " + r.text.replace("\n", "\n    ")[:show])
    return r


async def main() -> int:
    params = StdioServerParameters(command=PMMS,
                                   args=["--local", "--meqlab-path", WRAPPER_WIN],
                                   cwd="/home/zhengjp2/MCP/mcp")
    ledger = McpCallLedger(LOG)
    verdict = "EMPTY"
    async with PmmsSession(params, ledger) as s:
        r = await step(s, "exist_project", {"project_name": PROJECT})
        r = await (step(s, "generate_project", {"project_name": PROJECT})
                   if "否" in r.text else step(s, "open_project", {"project_name": PROJECT}))
        if not r.ok:
            return 1
        await step(s, "load_model", {"path": CARD, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid = next((int(i) for i, p in re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
                    if "nmos_wrapped" in p), None)
        if sid is None:
            print("FAIL: suite 未找到"); return 1
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid, "lib_name": "tt", "model_name": "nmos"})
        if not r.ok:
            print("FAIL: add_model_source"); return 1
        src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
        print(">>> 官方模型源:", src)

        r = await step(s, "load_data", {"data_type": 0, "path": DEMO_IV,
                                        "data_source_name": "iv_demo"})
        if not r.ok:
            print("FAIL: load_data"); return 1
        await step(s, "build_filter_by_data", {"data_source_name": "iv_demo"})

        for fs in ("type,op,name,iv_demo", "name,iv_demo"):
            for pg in ("id_vg_vb", "id_vg"):
                await step(s, "clear_views", {})
                r = await step(s, "view", {"view_fields": [{
                    "filter_string": fs,
                    "source_string": f"iv_demo, {src}",
                    "page_string": pg,
                    "selection_string": "xr(0,1)"}]})
                if not r.ok:
                    continue
                e = await step(s, "get_view_group_error", {}, show=1200)
                if e.ok and "共 0 个视图" not in e.text:
                    verdict = "NAN" if "nan" in e.text else "NUMBER"
                    print(f">>> 命中: filter='{fs}' page='{pg}'；判决={verdict}")
                    if verdict == "NUMBER":
                        await step(s, "dump_view_group",
                                   {"path": "/tmp/p7e_view_group.xlsx"})
                    break
                print(f">>> filter='{fs}' page='{pg}' 空，换下一个")
            if verdict != "EMPTY":
                break

    print(f"\n===== P7e DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"官方对照组判决={verdict} =====")
    return 0 if verdict == "NUMBER" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
