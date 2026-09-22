"""M5 唯一入口（agent架构设计 v1.1 §7）

用法：
  python src/pipeline/run_agent.py --device jia              # 单器件全新跑
  python src/pipeline/run_agent.py --devices jia,yi          # M5 连跑+提交物
  python src/pipeline/run_agent.py --device jia --resume     # 断点续跑
  --forms dc_transfer,dc_output  显式指定形态；缺省按器件数据目录自动探测
  --via-mcp  M4 链路——仿真经 MCP Server（长连接），与本地直连同签名切换
  --submit   单器件跑也强制生成提交物（多器件默认生成）

M5 验收判据（总进度 待完成区）：
  --devices jia,yi 一条命令；两份模型卡+日志包产出；Schema 校验通过。
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.main_graph import S_agent, build_main, load_ckpt, rehydrate  # noqa: E402
from src.tools.interface import DEVICE_DIR, FORM_FILES  # noqa: E402

FORM_ORDER = ["dc_transfer", "dc_output", "cv_gg"]
DEVICE_CHOICES = ("jia", "yi", "bing")


def detect_forms(device: str) -> list:
    """按器件数据目录自动探测可用形态（FORM_FILES 注册表内文件存在即纳入）。"""
    return [f for f in FORM_ORDER
            if (DEVICE_DIR / FORM_FILES[f].format(dev=device)).exists()]


def fresh_state(device: str, forms: list, via_mcp: bool) -> S_agent:
    return {"device_id": device, "forms": forms, "active_form": "",
            "data_forms": {}, "target_vg": None, "target_id": None, "sim_fn": None,
            "params_space": [], "values": {}, "fit_hist": [],
            "best_values": None, "best_rmse": None, "rmse": None,
            "qa_pass": False, "violations": [], "n_retry": 0,
            "budget": {}, "final_card": None, "completed": [],
            "forms_done": [], "rmse_target": None, "warm_start": False,
            "family_order": None, "freeze": None, "rmse_per_form": None,
            "via_mcp": via_mcp, "log": []}


def run_device(device: str, forms: list | None, via_mcp: bool, resume: bool) -> dict:
    forms = forms or detect_forms(device)
    if not forms:
        sys.exit(f"{device}: 无可用数据形态（{DEVICE_DIR / device}）")
    init = fresh_state(device, forms, via_mcp)
    if resume:
        snap = load_ckpt(device)
        if snap is None:
            init["log"] = [f"run_agent: --resume 指定但无 checkpoint，{device} 全新跑"]
        else:
            init.update({k: v for k, v in snap.items() if k in init})
            init = rehydrate(init)          # 补水：重建 sim_fn/数组/session（不入 ckpt 的对象）
            init["log"] = init["log"] + [f"run_agent: --resume 从 checkpoint 恢复，"
                                         f"已完成节点 {init['completed']}，extract 若未完成将整段重跑"]
    else:
        ckpt = ROOT / "logs" / f"ckpt_{device}.json"
        ckpt.unlink(missing_ok=True)
        for old in (ROOT / "logs").glob(f"run_{device}_*.json"):
            shutil.move(str(old), str(old) + ".prev")

    # 递归上限随形态数伸缩：主链 ~8 节点 + 每形态 extract 子图 ~10-40 超步
    limit = 40 + 40 * len(forms)
    final = build_main().invoke(init, config={"recursion_limit": limit})

    print(f"===== run_agent 全流程（器件：{device}，形态：{forms}，"
          f"链路：{'MCP' if via_mcp else '本地直连'}）=====")
    for line in final["log"]:
        print(line)
    print(f"\n最终参数空间: {final['params_space']}")
    print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
    per = final.get("rmse_per_form") or {}
    if len(per) > 1:
        print("逐形态 NRMSE: " + "，".join(f"{f}={v:.4%}" for f, v in per.items()))
    print(f"最差形态 NRMSE = {final['rmse']:.4%}，QA {'✅' if final['qa_pass'] else '❌'}")
    print(f"预算: {final['budget']}\n")
    return final


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", "--device", dest="devices", required=True,
                    help="逗号分隔器件列表，如 jia,yi（--device 为兼容别名）")
    ap.add_argument("--forms", default=None,
                    help="逗号分隔形态列表；缺省按器件数据目录自动探测")
    ap.add_argument("--via-mcp", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--submit", action="store_true", help="单器件也生成提交物")
    args = ap.parse_args()

    devices = [d.strip() for d in args.devices.split(",") if d.strip()]
    bad = [d for d in devices if d not in DEVICE_CHOICES]
    if bad:
        sys.exit(f"未知器件 {bad}（可选 {DEVICE_CHOICES}）")
    forms = [f.strip() for f in args.forms.split(",") if f.strip()] if args.forms else None

    results = {}
    for dev in devices:
        results[dev] = run_device(dev, forms, args.via_mcp, args.resume)

    if len(devices) > 1 or args.submit:
        from src.pipeline.make_submission import build_submission
        out, problems = build_submission(results)
        print(f"===== 提交物已生成：{out} =====")
        for p in sorted(out.glob("*")):
            if p.is_file():
                print(f"  {p.name}")
        if problems:
            print("Schema 校验 ❌：")
            for b in problems:
                print(f"  - {b}")
            sys.exit(1)
        print("Schema 校验 ✅ 全部通过")


if __name__ == "__main__":
    main()
