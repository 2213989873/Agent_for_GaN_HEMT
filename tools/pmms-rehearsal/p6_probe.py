# -*- coding: utf-8 -*-
"""P6 探针：数据 I/O 支线（M7 子任务2，C3 双轨对拍前置）。

判决：① 官方 demo .pms 能否走通 load_data→build_filter 全链（基线）；
     ② 我们按同格式生成的 jia 转移曲线 .pms 能否被接受（格式复刻判决）。
窗口内动作见输出编号；extract_spec 顺手一测（sweep→spec）。
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp import StdioServerParameters  # noqa: E402
from src.pmms import McpCallLedger, PmmsSession  # noqa: E402

PMMS = "/home/zhengjp2/MCP/mcp/pmms.exe"
WRAPPER_WIN = r"D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\meqlab-wrapper.exe"
PROJECT = "pmms_rehearsal"
DEMO_IV = ("/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/data/mosfet/nmos/iv/25/"
           "w=9.0,t=25.0,l=9.0.pms")
JIA_PMS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_transfer.pms"
LOG = Path(__file__).parent / "p6_ledger.jsonl"
CALLS = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None, show: int = 900):
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
    async with PmmsSession(params, ledger) as s:
        r = await step(s, "exist_project", {"project_name": PROJECT})
        if "否" in r.text:
            r = await step(s, "generate_project", {"project_name": PROJECT})
        else:
            r = await step(s, "open_project", {"project_name": PROJECT})
        if not r.ok:
            print("FAIL: 工程不可开"); return 1

        print("\n##### A. 官方 demo 数据基线 #####")
        r = await step(s, "load_data", {"data_type": 0, "path": DEMO_IV,
                                        "data_source_name": "iv_demo"})
        if not r.ok:
            print("FAIL: 官方 demo 数据都加载失败，格式假设需重来"); return 1
        await step(s, "list_data_sources", {})
        await step(s, "get_data_detail", {"data_source_name": "iv_demo"}, show=1500)
        await step(s, "build_filter_by_data", {"data_source_name": "iv_demo"})
        await step(s, "list_filters", {})
        await step(s, "extract_spec", {"data_source_name": "iv_demo"})

        print("\n##### B. 自制 jia 转移曲线 .pms（格式复刻判决）#####")
        r = await step(s, "load_data", {"data_type": 0, "path": JIA_PMS,
                                        "data_source_name": "jia_iv"})
        our_data_ok = r.ok
        if r.ok:
            await step(s, "get_data_detail", {"data_source_name": "jia_iv"}, show=1500)
            await step(s, "build_filter_by_data", {"data_source_name": "jia_iv"})
            await step(s, "list_filters", {})

    print(f"\n===== P6 DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"自制.pms={'PASS' if our_data_ok else 'FAIL'} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
