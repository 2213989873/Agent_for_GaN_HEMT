# -*- coding: utf-8 -*-
"""P5 探针：全参数写入路径判决（M7 子任务2 第一件事，待确认项 #6）。

假说：
  H3 文档先行：pmms://param_fields_guide 资源里有参数寻址语法（read_resource，非工具调用）
  H1 set_param 带 node_name 可对未声明参数"查找或添加"（API §6.2 文案）
  H2 参数必须先声明在 .model 卡上（list_params 只列已声明参数）

链路同 p2_smoke_v3：python → pmms.exe --local → wrapper → 预热 MeQLab(2008)
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
CARD_WRAP = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_with_lib.inc"
CARD_DECL = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_declared.inc"
LOG = Path(__file__).parent / "p5_ledger.jsonl"
CALLS = 0


async def step(s: PmmsSession, tool: str, args: dict | None = None, show: int = 800):
    global CALLS
    CALLS += 1
    r = await s.call(tool, args)
    print(f"--- [{CALLS}] {tool} {args or {}} -> ok={r.ok} code={r.error_code}")
    print("    " + r.text.replace("\n", "\n    ")[:show])
    return r


def find_suite(text: str, needle: str) -> int | None:
    pairs = re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", text)
    for i, p in pairs:
        if needle in p:
            return int(i)
    return None


def parse_src(text: str) -> str:
    m = re.search(r"名称：([^\n，]+)", text)
    return m.group(1).strip() if m else ""


async def main() -> int:
    global CALLS
    params = StdioServerParameters(command=PMMS,
                                   args=["--local", "--meqlab-path", WRAPPER_WIN],
                                   cwd="/home/zhengjp2/MCP/mcp")
    ledger = McpCallLedger(LOG)
    h1 = None
    async with PmmsSession(params, ledger) as s:
        # H3：先读官方参数语法资源（read_resource 不是工具调用，不占账本）
        try:
            res = await s._session.read_resource("pmms://param_fields_guide")
            for c in res.contents:
                print("=== pmms://param_fields_guide 原文（前 2500 字符）===")
                print(getattr(c, "text", str(c))[:2500])
        except Exception as e:
            print(f"=== param_fields_guide 读取失败: {e!r}")

        r = await step(s, "exist_project", {"project_name": PROJECT})
        if "否" in r.text:
            r = await step(s, "generate_project", {"project_name": PROJECT})
        else:
            r = await step(s, "open_project", {"project_name": PROJECT})
        if not r.ok:
            print("FAIL: 工程不可开"); return 1

        # ---- 包装卡（卡上仅声明 rdsmod）----
        await step(s, "load_model", {"path": CARD_WRAP, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid1 = find_suite(r.text, "jia_with_lib")
        if sid1 is None:
            print("FAIL: 找不到 jia_with_lib suite"); return 1
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid1, "lib_name": "tt", "model_name": "jiamod"})
        if not r.ok:
            print("FAIL: add_model_source(jiamod)"); return 1
        src1 = parse_src(r.text)
        print(">>> src1 =", src1)

        print("\n##### H1：未声明参数 voff 的读写 #####")
        await step(s, "get_param", {"model_source_name": src1, "param_name": "voff"})
        r = await step(s, "set_param", {"model_source_name": src1, "param_name": "voff",
                                        "param_value": "-2.0", "param_min": -3.0,
                                        "param_max": 0.0, "param_step": 0.01,
                                        "node_name": "jiamod"})
        h1 = r.ok
        if not r.ok:
            # 复现 v2 的 code 2（不带 node_name）
            await step(s, "set_param", {"model_source_name": src1, "param_name": "voff",
                                        "param_value": "-2.0", "param_min": -3.0,
                                        "param_max": 0.0, "param_step": 0.01})
        await step(s, "get_param", {"model_source_name": src1, "param_name": "voff"})
        await step(s, "list_params", {"model_source_name": src1}, show=2000)

        # ---- H2：声明卡（voff/u0/rth0/tbar/rontr1 已写在卡上，占位值）----
        print("\n##### H2：声明卡 jia_declared.inc #####")
        await step(s, "load_model", {"path": CARD_DECL, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid2 = find_suite(r.text, "jia_declared")
        if sid2 is None:
            print("FAIL: 找不到 jia_declared suite（load_model 可能失败）")
        else:
            r = await step(s, "add_model_source",
                           {"model_suite_id": sid2, "lib_name": "tt", "model_name": "jiafull"})
            if not r.ok:
                print("FAIL: add_model_source(jiafull)")
            else:
                src2 = parse_src(r.text)
                print(">>> src2 =", src2)
                await step(s, "list_params", {"model_source_name": src2}, show=2000)
                r = await step(s, "set_param", {"model_source_name": src2,
                                                "param_name": "voff",
                                                "param_value": "-2.2", "param_min": -3.0,
                                                "param_max": 0.0, "param_step": 0.01})
                if r.ok:
                    await step(s, "get_param", {"model_source_name": src2,
                                                "param_name": "voff"})

    print(f"\n===== P5 DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"H1(node_name 直写未声明参数)={'PASS' if h1 else 'FAIL'} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
