# -*- coding: utf-8 -*-
"""P7-bis 探针：配对为空修复——页名候选 × 误差非空自检验环。

P7 教训：view 返回"视图选择成功"≠视图非空（page_string 不匹配时静默为空，
get_view_group_error 报"共 0 个视图/nan"）。本探针以 get_view_group_error
非空为唯一验收，逐个候选页名循环验证。

候选页名依 view_fields_guide §2.4（y_x_p 下划线式 + @条件）：我们的 .pms
group=Id_Vg、p=Vbs、condition vds=1.0 → 理论页名 id_vg_vb@vds=1 一族。
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
LOG = Path(__file__).parent / "p7b_ledger.jsonl"
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
    got_error = False
    async with PmmsSession(params, ledger) as s:
        # 0. 视图指南全文存档（资源，不占账本）
        try:
            res = await s._session.read_resource("pmms://view_fields_guide")
            for c in res.contents:
                print("=== pmms://view_fields_guide 全文 ===")
                print(getattr(c, "text", str(c))[:9000])
        except Exception as e:
            print(f"=== view_fields_guide 读取失败: {e!r}")

        # 1. 工程 + 模型源 + 数据源/filter（每次会话重建，已证不持久）
        r = await step(s, "exist_project", {"project_name": PROJECT})
        r = await (step(s, "generate_project", {"project_name": PROJECT})
                   if "否" in r.text else step(s, "open_project", {"project_name": PROJECT}))
        if not r.ok:
            return 1
        await step(s, "load_model", {"path": CARD, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid = next(int(i) for i, p in re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
                   if "jia_with_lib" in p)
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid, "lib_name": "tt", "model_name": "jiamod"})
        if not r.ok:
            print("FAIL: add_model_source"); return 1
        src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
        r = await step(s, "load_data", {"data_type": 0, "path": JIA_PMS,
                                        "data_source_name": "jia_iv"})
        if not r.ok:
            print("FAIL: load_data"); return 1
        await step(s, "build_filter_by_data", {"data_source_name": "jia_iv"})

        # 2. 页名候选 × 误差非空自检验环
        for pg in ("id_vg_vb@vds=1.0", "id_vg_vb@vd=1", "id_vg_vb",
                   "id_vg", "Id_Vg"):
            await step(s, "clear_views", {})
            r = await step(s, "view", {"view_fields": [{
                "filter_string": "name,jia_iv",
                "source_string": f"jia_iv, {src}",
                "page_string": pg,
                "selection_string": "xr(0,1)"}]})
            if not r.ok:
                continue
            e = await step(s, "get_view_group_error", {}, show=1200)
            if e.ok and "共 0 个视图" not in e.text and "nan" not in e.text:
                got_error = True
                print(f">>> 命中页名: '{pg}'，误差读数见上")
                await step(s, "dump_view_group",
                           {"path": "/tmp/p7b_view_group.xlsx"})
                break
            print(f">>> 页名 '{pg}' 配对为空，换下一个")

    print(f"\n===== P7-bis DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"真误差={'GOT' if got_error else 'STILL-EMPTY'} =====")
    return 0 if got_error else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
