# -*- coding: utf-8 -*-
"""P7c 对照实验：error=nan 责任方判决。

对照组：官方 demo.lib（lib=tt → model=nch，BSIM level54）+ 官方 demo IV 数据。
  - 官方组合拿到数值误差 → 仿真引擎/license 无恙，nan 责任在我们的 ASM-HEMT 卡；
  - 官方组合同样 nan → 环境/引擎/license 问题，升级组委会。
自检验环同 p7b：页名候选逐个试，以"视图非空"为命中；命中后再看 error 是否 nan。
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
DEMO_LIB = "/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/model/demo.lib"
DEMO_IV = ("/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/data/mosfet/nmos/iv/25/"
           "w=9.0,t=25.0,l=9.0.pms")
LOG = Path(__file__).parent / "p7c_ledger.jsonl"
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

        # 官方模型：demo.lib 顶层 lib=tt（内嵌 tt_mos 含 .model nch nmos）
        await step(s, "load_model", {"path": DEMO_LIB, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        pairs = re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
        sid = next((int(i) for i, p in pairs if "demo.lib" in p), None)
        if sid is None:
            print("FAIL: demo.lib suite 未找到"); return 1
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid, "lib_name": "tt", "model_name": "nch"})
        if not r.ok:
            print("FAIL: add_model_source(nch@tt)"); return 1
        src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
        print(">>> 官方模型源:", src)

        # 官方数据
        r = await step(s, "load_data", {"data_type": 0, "path": DEMO_IV,
                                        "data_source_name": "iv_demo"})
        if not r.ok:
            print("FAIL: load_data demo"); return 1
        await step(s, "build_filter_by_data", {"data_source_name": "iv_demo"})
        await step(s, "list_filters", {})

        # 页名自检验环（demo 数据 group=Id_Vg p=Vbs → id_vg_vb 一族）
        for pg in ("id_vg_vb", "id_vg", "Id_Vg"):
            await step(s, "clear_views", {})
            r = await step(s, "view", {"view_fields": [{
                "filter_string": "name,iv_demo",
                "source_string": f"iv_demo, {src}",
                "page_string": pg,
                "selection_string": "xr(0,1)"}]})
            if not r.ok:
                continue
            e = await step(s, "get_view_group_error", {}, show=1200)
            if e.ok and "共 0 个视图" not in e.text:
                verdict = "NAN" if "nan" in e.text else "NUMBER"
                print(f">>> 页名 '{pg}' 命中非空视图；判决={verdict}")
                if verdict == "NUMBER":
                    await step(s, "dump_view_group", {"path": "/tmp/p7c_view_group.xlsx"})
                break
            print(f">>> 页名 '{pg}' 空，换下一个")

    print(f"\n===== P7c DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"官方对照组判决={verdict} =====")
    return 0 if verdict == "NUMBER" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
