# -*- coding: utf-8 -*-
"""P7g 探针：单变量对照——同数据换模型（jia_iv 数据 + 官方 BSIM nmos 模型）。

已知基线：jia_iv + 我们 asmhemt 卡 → 1 视图但 error=nan（P7-bis）。
本探针只换模型为官方 nmos_tt_N，页名直接用已命中的 id_vg_vb。
  - NUMBER → 引擎/license 无恙，nan 责任在我们 ASM-HEMT 卡；
  - NAN    → 官方 BSIM 也算不出 → 引擎/license/环境问题，升级组委会。
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
CARD_NMOS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/nmos_wrapped.inc"
JIA_PMS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_transfer.pms"
LOG = Path(__file__).parent / "p7g_ledger.jsonl"
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
    verdict = "EMPTY"
    async with PmmsSession(params, ledger) as s:
        r = await step(s, "exist_project", {"project_name": PROJECT})
        r = await (step(s, "generate_project", {"project_name": PROJECT})
                   if "否" in r.text else step(s, "open_project", {"project_name": PROJECT}))
        if not r.ok:
            return 1
        await step(s, "load_model", {"path": CARD_NMOS, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid = next((int(i) for i, p in re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
                    if "nmos_wrapped" in p), None)
        if sid is None:
            print("FAIL: nmos suite"); return 1
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid, "lib_name": "tt", "model_name": "nmos"})
        if not r.ok:
            print("FAIL: add_model_source"); return 1
        src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
        print(">>> 官方模型源:", src)

        r = await step(s, "load_data", {"data_type": 0, "path": JIA_PMS,
                                        "data_source_name": "jia_iv"})
        if not r.ok:
            print("FAIL: load_data"); return 1
        await step(s, "build_filter_by_data", {"data_source_name": "jia_iv"})

        await step(s, "clear_views", {})
        r = await step(s, "view", {"view_fields": [{
            "filter_string": "name,jia_iv",
            "source_string": f"jia_iv, {src}",
            "page_string": "id_vg_vb",
            "selection_string": "xr(0,1)"}]}, show=1200)
        if r.ok:
            e = await step(s, "get_view_group_error", {}, show=1500)
            if e.ok and "共 0 个视图" not in e.text:
                verdict = "NAN" if "nan" in e.text else "NUMBER"
                if verdict == "NUMBER":
                    await step(s, "dump_view_group", {"path": "/tmp/p7g_view_group.xlsx"})

    print(f"\n===== P7g DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"换模型对照判决={verdict} =====")
    return 0 if verdict == "NUMBER" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
