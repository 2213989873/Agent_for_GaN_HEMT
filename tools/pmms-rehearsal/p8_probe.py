# -*- coding: utf-8 -*-
"""P8 探针：error=nan 现场取证 + 官方示例工程对照。

背景：P7-bis jia+asmhemt 组合 1 视图但 error=nan；P7g 日志发现 NanoSpice
确实跑过（nmos BSIM4 license OK），但 MS_MEQLAB_SPICE 签出失败。
P7-bis 窗口的日志已被轮转，nan 时刻的 license/仿真记录缺失。

本探针：
  A 段——原样复现 P7-bis 命中组合（jia_transfer.pms + jia_with_lib.inc，
        页名 id_vg_vb），在 view/error 调用前后对 MeQLab 四个日志文件做
        偏移快照，打印增量内容：nan 时刻到底签出了什么 license、
        NanoSpice 对 jiamod 说了什么。
  B 段——打开官方示例工程 bin_model_demo_point_model（已知良好、
        BSIM 模型、Ordinary Page 曲线视图 74 个），直接
        get_view_group_error：官方工程若能算出数值 → 引擎/license
        对 BSIM 无罪；若也 nan → 环境问题升级组委会。
"""
import asyncio
import os
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
DEMO_PROJECT = "bin_model_demo_point_model"
CARD = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_with_lib.inc"
JIA_PMS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_transfer.pms"
LOG = Path(__file__).parent / "p8_ledger.jsonl"
LOGDIR = Path.home() / ".MS-MeQLab/dev/var/log"
LOGFILES = ["info.log", "warning.log", "severe.log", "messages.log"]
CALLS = 0


def log_sizes() -> dict:
    return {f: (LOGDIR / f).stat().st_size if (LOGDIR / f).exists() else 0
            for f in LOGFILES}


def log_new(sizes: dict, tag: str) -> None:
    print(f"\n########## 日志增量 @{tag} ##########")
    for f, off in sizes.items():
        p = LOGDIR / f
        if not p.exists():
            print(f"--- {f}: 不存在"); continue
        cur = p.stat().st_size
        if cur <= off:
            print(f"--- {f}: 无新增 ({off}B)"); continue
        with open(p, "rb") as fh:
            fh.seek(off)
            chunk = fh.read(cur - off)
        text = chunk.decode("utf-8", errors="replace")
        # 去掉 ANSI 颜色码，便于阅读存档
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        print(f"--- {f} (+{cur - off}B) ---")
        print(text[-3000:])


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
    verdict_a = "EMPTY"
    verdict_b = "EMPTY"
    async with PmmsSession(params, ledger) as s:
        # ===== A 段：复现 nan + 日志取证 =====
        print("========== A 段：jia + asmhemt nan 现场取证 ==========")
        r = await step(s, "exist_project", {"project_name": PROJECT})
        r = await (step(s, "generate_project", {"project_name": PROJECT})
                   if "否" in r.text else step(s, "open_project", {"project_name": PROJECT}))
        if not r.ok:
            return 1
        await step(s, "load_model", {"path": CARD, "format": "hspice"})
        r = await step(s, "list_available_models", {})
        sid = next((int(i) for i, p in re.findall(r"ID:\s*(\d+),\s*路径：\s*(\S+)", r.text)
                    if "jia_with_lib" in p), None)
        if sid is None:
            print("FAIL: jia suite"); return 1
        r = await step(s, "add_model_source",
                       {"model_suite_id": sid, "lib_name": "tt", "model_name": "jiamod"})
        if not r.ok:
            print("FAIL: add_model_source"); return 1
        src = re.search(r"名称：([^\n，]+)", r.text).group(1).strip()
        print(">>> 模型源:", src)
        r = await step(s, "load_data", {"data_type": 0, "path": JIA_PMS,
                                        "data_source_name": "jia_iv"})
        if not r.ok:
            print("FAIL: load_data"); return 1
        await step(s, "build_filter_by_data", {"data_source_name": "jia_iv"})

        await step(s, "clear_views", {})
        snap = log_sizes()                      # <-- 取证快照点
        r = await step(s, "view", {"view_fields": [{
            "filter_string": "name,jia_iv",
            "source_string": f"jia_iv, {src}",
            "page_string": "id_vg_vb",
            "selection_string": "xr(0,1)"}]}, show=1200)
        if r.ok:
            e = await step(s, "get_view_group_error", {}, show=1500)
            log_new(snap, "A段 view+error 之后")   # <-- 打印增量日志
            if e.ok and "共 0 个视图" not in e.text:
                verdict_a = "NAN" if "nan" in e.text else "NUMBER"
                if verdict_a == "NUMBER":
                    await step(s, "dump_view_group", {"path": "/tmp/p8_view_group.xlsx"})

        # ===== B 段：官方示例工程对照 =====
        print("\n========== B 段：官方 point_model 工程对照 ==========")
        snap = log_sizes()
        r = await step(s, "exist_project", {"project_name": DEMO_PROJECT})
        if "否" in r.text:
            print(">>> 官方工程不在 /tmp/MeqlabProjects，B 段跳过（run_p8.sh 应先复制）")
            verdict_b = "MISSING"
        else:
            r = await step(s, "open_project", {"project_name": DEMO_PROJECT}, show=400)
            if r.ok:
                await step(s, "list_filters", {}, show=1200)
                e = await step(s, "get_view_group_error", {}, show=2000)
                log_new(snap, "B段 打开官方工程+error 之后")
                if e.ok:
                    if "共 0 个视图" in e.text:
                        verdict_b = "0VIEWS"
                    else:
                        verdict_b = "NAN" if "nan" in e.text else "NUMBER"
                        if verdict_b == "NUMBER":
                            await step(s, "dump_view_group",
                                       {"path": "/tmp/p8_demo_view_group.xlsx"})

    print(f"\n===== P8 DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"A段(nan复现)={verdict_a} B段(官方对照)={verdict_b} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
