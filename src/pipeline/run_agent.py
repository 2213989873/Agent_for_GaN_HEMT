"""M1 唯一入口（agent架构设计 v1.1 §7）

用法：
  python src/pipeline/run_agent.py --device jia            # 全新跑
  python src/pipeline/run_agent.py --device jia --resume   # 断点续跑
  python src/pipeline/run_agent.py --device yi --forms dc_transfer
  --via-mcp：M4 内容，当前报错退出。

M1 验收判据（总进度 待完成区）：
  --device jia 全程无人干预；NRMSE ≤0.01%（卡12 基准 0.0000%/6 次仿真）；
  QA 全过；日志含预算计数；kill 后 --resume 续跑成功。
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.main_graph import S_agent, build_main, load_ckpt, rehydrate  # noqa: E402


def fresh_state(device: str, forms: list, via_mcp: bool) -> S_agent:
    return {"device_id": device, "forms": forms, "active_form": "",
            "data_forms": {}, "target_vg": None, "target_id": None, "sim_fn": None,
            "params_space": [], "values": {}, "fit_hist": [],
            "best_values": None, "best_rmse": None, "rmse": None,
            "qa_pass": False, "violations": [], "n_retry": 0,
            "budget": {}, "final_card": None, "completed": [],
            "forms_done": [], "rmse_target": None, "warm_start": False,
            "via_mcp": via_mcp, "log": []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, choices=["jia", "yi"])
    ap.add_argument("--forms", default="dc_transfer")
    ap.add_argument("--via-mcp", action="store_true")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if args.via_mcp:
        sys.exit("--via-mcp 为 M4 内容，当前未实现（卡14 已验证协议链路，M4 接主图）")
    forms = [f.strip() for f in args.forms.split(",") if f.strip()]

    init = fresh_state(args.device, forms, args.via_mcp)
    if args.resume:
        snap = load_ckpt(args.device)
        if snap is None:
            sys.exit(f"--resume 失败：无 checkpoint（logs/ckpt_{args.device}.json）")
        init.update({k: v for k, v in snap.items() if k in init})
        init = rehydrate(init)          # 补水：重建 sim_fn/数组/session（不入 ckpt 的对象）
        init["log"] = init["log"] + [f"run_agent: --resume 从 checkpoint 恢复，"
                                     f"已完成节点 {init['completed']}，extract 若未完成将整段重跑"]
    else:
        ckpt = ROOT / "logs" / f"ckpt_{args.device}.json"
        ckpt.unlink(missing_ok=True)
        for old in (ROOT / "logs").glob(f"run_{args.device}_*.json"):
            shutil.move(str(old), str(old) + ".prev")

    final = build_main().invoke(init, config={"recursion_limit": 60})

    print(f"===== run_agent 全流程（器件：{args.device}，形态：{forms}）=====")
    for line in final["log"]:
        print(line)
    print(f"\n最终参数空间: {final['params_space']}")
    print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
    print(f"最终 NRMSE = {final['rmse']:.4%}，QA {'✅' if final['qa_pass'] else '❌'}")
    print(f"预算: {final['budget']}")


if __name__ == "__main__":
    main()
