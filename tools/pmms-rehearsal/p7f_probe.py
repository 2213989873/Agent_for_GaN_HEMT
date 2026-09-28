# -*- coding: utf-8 -*-
"""P7f 探针：pmms://api 结构化状态取证 + 按真名重试官方对照组。

依据：API 文档"通用数据结构"节——ModelSuite.libs 的 key 是 PVT corner（tt/ff），
value 是该 corner 下的 model/subckt 名列表；§5.1 注称结构化字段经 pmms://api 读。
步骤：load demo.lib + demo 数据 → read pmms://api（全文落盘）→ 按 libs 真名
add_model_source → view 页名候选（id_vgs 优先，12 参考视图第 5 条）→ 误差自检。
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
LOG = Path(__file__).parent / "p7f_ledger.jsonl"
API_DUMP = Path(__file__).parent / "p7f_pmms_api_dump.txt"
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
        await step(s, "load_model", {"path": DEMO_LIB, "format": "hspice"})
        await step(s, "load_data", {"data_type": 0, "path": DEMO_IV,
                                    "data_source_name": "iv_demo"})

        # 结构化状态取证（资源，不占账本）
        try:
            res = await s._session.read_resource("pmms://api")
            txt = "\n".join(getattr(c, "text", str(c)) for c in res.contents)
            API_DUMP.write_text(txt)
            print(f"=== pmms://api 已落盘 {API_DUMP.name}，{len(txt)} 字符；"
                  f"libs 相关片段：")
            for mline in re.findall(r'.*(?:libs|tt_mos|"tt"|nch).*', txt)[:15]:
                print("   ", mline[:160])
        except Exception as e:
            print(f"=== pmms://api 读取失败: {e!r}")

        # 按真名尝试 add_model_source：候选 (lib, model) 组合
        src = ""
        for lib, mdl in (("tt", "nch"), ("tt", "tt_mos"), ("tt_mos", "nch")):
            r = await step(s, "add_model_source",
                           {"model_suite_id": 0, "lib_name": lib, "model_name": mdl})
            if r.ok:
                src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
                print(f">>> 成功组合: lib='{lib}' model='{mdl}' -> {src}")
                break
            print(f">>> lib='{lib}' model='{mdl}' 空")
        if not src:
            print("FAIL: demo.lib 所有候选组合均空"); return 1

        await step(s, "build_filter_by_data", {"data_source_name": "iv_demo"})

        for pg in ("id_vgs", "id_vgs_vbs", "Id_Vgs_Vbs", "id_vg_vb", "id_vg"):
            await step(s, "clear_views", {})
            r = await step(s, "view", {"view_fields": [{
                "filter_string": "type,op,name,iv_demo",
                "source_string": f"iv_demo, {src}",
                "page_string": pg,
                "selection_string": "xr(0,1)"}]})
            if not r.ok:
                continue
            e = await step(s, "get_view_group_error", {}, show=1200)
            if e.ok and "共 0 个视图" not in e.text:
                verdict = "NAN" if "nan" in e.text else "NUMBER"
                print(f">>> 命中页名 '{pg}'；判决={verdict}")
                if verdict == "NUMBER":
                    await step(s, "dump_view_group", {"path": "/tmp/p7f_view_group.xlsx"})
                break
            print(f">>> 页名 '{pg}' 空")

    print(f"\n===== P7f DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"官方对照组判决={verdict} =====")
    return 0 if verdict == "NUMBER" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
