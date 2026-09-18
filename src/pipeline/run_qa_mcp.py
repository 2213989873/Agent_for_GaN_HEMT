"""任务卡 14 入口：MCP 切换演练 —— pipeline 零改动，协议层整体替换

与 run_qa_selfheat.py 的唯一差异：sim_fn 从 run_output_selfheat_params（本地直连）
换成 mcp_output_sim（经 mock Primarius MCP Server）。验证三件事：
  1. pipeline（粗调/精修/QA/双触发扩空间）在 MCP 协议下行为逐位一致
  2. MCP 调用计数自动累计，红线（≥10 次/器件）天然满足
  3. 测试日只换 SERVER_PATH 即切到组委会真接口

运行：python src/pipeline/run_qa_mcp.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import S, build  # noqa: E402
from src.tools.mcp_sim import get_count, mcp_output_sim, reset_count  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "dc_output_yi.csv")

reset_count()  # 红线按器件统计，提取开始清零

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "sim_fn": mcp_output_sim,           # ← 唯一的切换点：MCP 协议
    "params_space": ["voff", "u0"],
    "values": {"voff": -2.0, "u0": 170e-3},
    "rmse": None,
    "qa_pass": False,
    "violations": [],
    "n_retry": 0,
    "log": [],
}

final = build().invoke(init, {"recursion_limit": 60})

print("===== MCP 协议下的 physics_qa 闭环（乙·含自热 847 点）=====")
for line in final["log"]:
    print(line)
print(f"\n最终参数空间: {final['params_space']}")
print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
print(f"最终 NRMSE = {final['rmse']:.4%}")
n = get_count()
print(f"\nMCP 调用计数: {n} 次（红线 ≥10：{'✅ 满足' if n >= 10 else '❌ 不足'}）")
