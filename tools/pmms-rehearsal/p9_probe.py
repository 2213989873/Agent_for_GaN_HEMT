# -*- coding: utf-8 -*-
"""P9 探针：官方示例工程 view→error 出数值（目标1，引擎无罪终证）
        + jia+asmhemt 复现以捕获 NanoSpice 临时网表（目标2）。

目标1（B 段）：open_project(bin_model_demo_point_model) → list_filters /
  list_data_sources / get_data_detail 探索 → 用工程 workspace.xml 钉死的
  参数（filter "IV_data(Sweep)"、source "IV_data, Binning1"）+ 页名候选
  逐个试 view → get_view_group_error。判决：共 N 个视图且 N>0 且聚合误差
  是数值 = NUMBER（成功）；N=0 = 0VIEWS；error=nan = NAN。
  页名候选依据：data.h2.db 里 strings 到 "Id_Vg" / "id_vd"，另附 P7 一族。

目标2（A 段）：照抄 p8_probe.py A 段调用序列复现 jia_transfer.pms +
  jia_with_lib.inc（asmhemt, rdsmod=1）组合，触发 NanoSpice 写
  ~/.jms-meqlab/TempP_0.sp；run_p9.sh 在探针运行期间后台高频复制该目录
  下的 *.sp 到 /tmp/p9_deck_capture/。

每个 view/error 窗口前后对 ~/.MS-MeQLab/dev/var/log 四个日志做偏移快照，
打印增量。
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
DEMO_PROJECT = "bin_model_demo_point_model"
CARD = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_with_lib.inc"
JIA_PMS = "/home/zhengjp2/projects/gan-hemt-agent/data/sim/jia_transfer.pms"
LOG = Path(__file__).parent / "p9_ledger.jsonl"
LOGDIR = Path.home() / ".MS-MeQLab/dev/var/log"
LOGFILES = ["info.log", "warning.log", "severe.log", "messages.log"]
CALLS = 0

# 目标1 页名候选（data.h2.db strings 命中的在前）
DEMO_PAGES = ["id_vd", "Id_Vg", "id_vd_vg", "id_vg_vb", "id_vg", "ig_vg"]
# 目标1 filter_string 候选
DEMO_FILTERS = ["name,IV_data(Sweep)", "name,IV_data"]


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


def judge(text: str) -> str:
    """get_view_group_error 文本 → 判决。"""
    m = re.search(r"共 (\d+) 个视图", text)
    n = int(m.group(1)) if m else -1
    if n <= 0:
        return "0VIEWS"
    return "NAN" if "nan" in text else "NUMBER"


async def main() -> int:
    params = StdioServerParameters(command=PMMS,
                                   args=["--local", "--meqlab-path", WRAPPER_WIN],
                                   cwd="/home/zhengjp2/MCP/mcp")
    ledger = McpCallLedger(LOG)
    verdict_demo = "EMPTY"
    verdict_jia = "EMPTY"
    hit_combo = None
    async with PmmsSession(params, ledger) as s:
        # ===== 目标1：官方示例工程 view→error =====
        print("========== 目标1：官方 bin_model_demo_point_model view→error ==========")
        snap = log_sizes()
        r = await step(s, "exist_project", {"project_name": DEMO_PROJECT})
        if "否" in r.text:
            print(">>> 官方工程不在 /tmp/MeqlabProjects，目标1 跳过")
            verdict_demo = "MISSING"
        else:
            r = await step(s, "open_project", {"project_name": DEMO_PROJECT}, show=400)
            if r.ok:
                await step(s, "list_filters", {}, show=1200)
                await step(s, "list_data_sources", {}, show=1200)
                await step(s, "get_data_detail", {"data_source_name": "IV_data"}, show=800)
                # 不 view 直接 get_view_group_error，验证 code 2 基线
                await step(s, "get_view_group_error", {}, show=400)
                done = False
                for fs in DEMO_FILTERS:
                    if done:
                        break
                    for pg in DEMO_PAGES:
                        await step(s, "clear_views", {})
                        r = await step(s, "view", {"view_fields": [{
                            "filter_string": fs,
                            "source_string": "IV_data, Binning1",
                            "page_string": pg,
                            "selection_string": "xr(0,1)"}]}, show=400)
                        if not r.ok:
                            print(f">>> filter='{fs}' page='{pg}' view 调用失败，换下一个")
                            continue
                        e = await step(s, "get_view_group_error", {}, show=2000)
                        v = judge(e.text) if e.ok else f"ERR{e.error_code}"
                        print(f">>> filter='{fs}' page='{pg}' 判决={v}")
                        if v in ("NUMBER", "NAN"):
                            verdict_demo = v
                            hit_combo = (fs, pg)
                            done = True
                            break
                log_new(snap, "目标1 官方工程 view+error 之后")
                if verdict_demo == "NUMBER":
                    await step(s, "dump_view_group",
                               {"path": "/tmp/p9_demo_view_group.xlsx"})
                if verdict_demo == "EMPTY":
                    verdict_demo = "0VIEWS"

        # ===== 目标2：jia+asmhemt 复现（触发 TempP_0.sp，供后台捕获）=====
        print("\n========== 目标2：jia + asmhemt 复现（网表捕获窗口）==========")
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
            if e.ok and "共 0 个视图" not in e.text:
                verdict_jia = "NAN" if "nan" in e.text else "NUMBER"
            elif e.ok:
                verdict_jia = "0VIEWS"
            # 同步强制仿真：P8-verify1 证据表明 NanoSpice 是异步跑的
            # （"Done simulation" 出现在 view 之后约 1s），run1 里探针在
            # get_view_group_error 返回后 3ms 就关会话，MeQLab 被杀，
            # 异步仿真没来得及写 TempP_0.sp。save_sim_result 同步触发仿真，
            # 之后再等 10s 让异步仿真/日志 flush 完成，给捕获器留窗口。
            await step(s, "save_sim_result",
                       {"data_source_name": "jia_iv",
                        "model_source_name": src,
                        "path": "/tmp/p9_jia_sim.dat"}, show=800)
            print(">>> 等待 10s 让异步仿真/日志 flush ...")
            await asyncio.sleep(10)
            log_new(snap, "目标2 jia view+error+save_sim_result+10s 之后")

    print(f"\n===== P9 DONE: ledger.count={ledger.count} calls={CALLS} | "
          f"目标1(官方工程)={verdict_demo} hit={hit_combo} | "
          f"目标2(jia复现)={verdict_jia} =====")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
