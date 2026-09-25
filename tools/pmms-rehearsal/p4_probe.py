# -*- coding: utf-8 -*-
"""P4 探针：先取官方 project_initialization Prompt 原文（非工具调用），
再按 lib_name=tt（顶层 corner 段）试 add_model_source；失败再试默认值变体。

用法：python p4_probe.py
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
DEMO = "/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/model/demo.lib"


async def main() -> int:
    params = StdioServerParameters(command=PMMS,
                                   args=["--local", "--meqlab-path", WRAPPER_WIN],
                                   cwd="/home/zhengjp2/MCP/mcp")
    ledger = McpCallLedger(Path(__file__).parent / "p4_ledger.jsonl")
    async with PmmsSession(params, ledger) as s:
        # 官方 Prompt 原文（get_prompt 不是工具调用，不占红线计数）
        try:
            gp = await s._session.get_prompt(
                "project_initialization",
                {"model_path": DEMO, "data_path": "iv.dat", "data_type": "0"})
            for msg in gp.messages:
                c = msg.content
                txt = getattr(c, "text", str(c))
                print("=== project_initialization prompt 原文 ===")
                print(txt[:3000])
        except Exception as e:
            print(f"[get_prompt failed] {e}")

        r = await s.call("open_project", {"project_name": PROJECT})
        print(f"\n[open_project] ok={r.ok}")
        r = await s.call("load_model", {"path": DEMO, "format": "hspice"})
        print(f"[load_model] ok={r.ok}")
        r = await s.call("list_available_models")
        pairs = re.findall(r"ID:\s*(\d+),\s*路径：([^\n]+)", r.text)
        suite_id = None
        for sid, p in pairs:
            if p.strip() == DEMO:
                suite_id = int(sid)
        print(f"[suite_id] {suite_id} from {pairs}")

        for kw in ({"lib_name": "tt", "model_name": "nch"}, {}):
            tag = kw or "默认(lib/model 缺省)"
            r = await s.call("add_model_source",
                             {"model_suite_id": suite_id, "simulator": "Nano", **kw})
            print(f"[add_model_source {tag}] ok={r.ok}")
            print("    " + r.text.replace("\n", "\n    ")[:400])
            if r.ok:
                m = re.search(r"名称：([^\n，]+)", r.text)
                src = m.group(1) if m else None
                r = await s.call("set_param", {
                    "model_source_name": src, "param_name": "vth0",
                    "param_value": "0.5", "param_min": 0.0,
                    "param_max": 2.0, "param_step": 0.01})
                print(f"[set_param] ok={r.ok} {r.text.splitlines()[0]}")
                r = await s.call("get_param",
                                 {"model_source_name": src, "param_name": "vth0"})
                print(f"[get_param] ok={r.ok}")
                print("    " + r.text.replace("\n", "\n    ")[:200])
                break

    print(f"===== P4 DONE ledger.count={ledger.count} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
