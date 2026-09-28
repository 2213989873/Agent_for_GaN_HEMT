# -*- coding: utf-8 -*-
"""P7 探针：view + get_view_group_error —— 首次 NanoSpice 真仿真与官方误差读数。

链路：open_project → 幂等备料（模型源/数据源/filter）→ clear_views
     → view(view_fields 五元组) → get_view_group_error → dump_view_group
附：先读 pmms://view_fields_guide 资源原文（非工具调用）。
容错：page_string/filter_string 候选回退；模型源/数据源已存在则复用。
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
CARD = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_with_lib.inc"
JIA_PMS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_transfer.pms"
LOG = Path(__file__).parent / "p7_ledger.jsonl"
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
        # 0. 视图填写指南（资源，不占账本）
        try:
            res = await s._session.read_resource("pmms://view_fields_guide")
            for c in res.contents:
                print("=== pmms://view_fields_guide（前 2800 字符）===")
                print(getattr(c, "text", str(c))[:2800])
        except Exception as e:
            print(f"=== view_fields_guide 读取失败: {e!r}")

        # 1. 工程
        r = await step(s, "exist_project", {"project_name": PROJECT})
        r = await (step(s, "generate_project", {"project_name": PROJECT})
                   if "否" in r.text else step(s, "open_project", {"project_name": PROJECT}))
        if not r.ok:
            print("FAIL: 工程"); return 1

        # 2. 模型源（幂等）
        r = await step(s, "list_model_sources", {})
        m = re.search(r"jiamod_tt_N\w*?", r.text)
        if m:
            src = m.group(0)
            print(">>> 复用已持久化模型源:", src)
        else:
            await step(s, "load_model", {"path": CARD, "format": "hspice"})
            r = await step(s, "list_available_models", {})
            sid = next(int(i) for i, p in re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
                       if "jia_with_lib" in p)
            r = await step(s, "add_model_source",
                           {"model_suite_id": sid, "lib_name": "tt", "model_name": "jiamod"})
            if not r.ok:
                print("FAIL: add_model_source"); return 1
            src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
            print(">>> 新建模型源:", src)

        # 3. 数据源 + filter（幂等）
        r = await step(s, "list_data_sources", {})
        if "jia_iv" not in r.text:
            r = await step(s, "load_data", {"data_type": 0, "path": JIA_PMS,
                                            "data_source_name": "jia_iv"})
            if not r.ok:
                print("FAIL: load_data jia_iv"); return 1
            await step(s, "build_filter_by_data", {"data_source_name": "jia_iv"})
        else:
            print(">>> 复用已持久化数据源 jia_iv")
        await step(s, "list_filters", {})

        # 4. view（候选回退）
        await step(s, "clear_views", {})
        view_ok = False
        for fs in ("name,jia_iv", "type,op,name,jia_iv"):
            for pg in ("Id_Vg", "id_vg", "id_vgs", "Id_Vgs"):
                r = await step(s, "view", {"view_fields": [{
                    "filter_string": fs,
                    "source_string": f"jia_iv, {src}",
                    "page_string": pg,
                    "selection_string": "xr(0,1)",
                    "prop_string": "logy"}]})
                if r.ok:
                    view_ok = True
                    print(f">>> view 成功组合: filter='{fs}' page='{pg}'")
                    break
            if view_ok:
                break
        if not view_ok:
            print("FAIL: view 全部候选组合失败"); return 1

        # 5. 首次真仿真误差
        r = await step(s, "get_view_group_error", {}, show=1500)
        # 6. 导出视图组（可选存档）
        await step(s, "dump_view_group", {"path": "/tmp/p7_view_group.xlsx"})

    print(f"\n===== P7 DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"get_view_group_error={'PASS' if r.ok else 'FAIL'} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
