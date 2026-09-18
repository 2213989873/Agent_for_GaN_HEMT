"""任务卡 11 入口：physics_qa 闭环实战

场景：乙器件（真值 voff=-2.2, u0=150e-3, rontr1=-1）。
提取空间只从 ["voff","u0"] 起步——任务卡 10 已知这条路会产出
u0=84e-3 的补偿解。预期剧情：
  精修出界 → QA 驳回 → 换初值重调 → 再驳回 → 自动扩空间(+rontr1)
  → 精修命中真值 → QA 通过。
这就是评分公式 Card = QA通过率 × (1−NRMSE) 的完整落地。

运行：python src/pipeline/run_qa.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import S, build  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "transfer_yi.csv")

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "params_space": ["voff", "u0"],     # 只带两参数起步
    "values": {"voff": -2.0, "u0": 170e-3},
    "rmse": None,
    "qa_pass": False,
    "violations": [],
    "n_retry": 0,
    "log": [],
}

final = build().invoke(init)

print("===== physics_qa 闭环过程 =====")
for line in final["log"]:
    print(line)
print(f"\n最终参数空间: {final['params_space']}")
print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
print(f"最终 NRMSE = {final['rmse']:.4%}")
print("（真值 voff=-2.2, u0=150e-3, rontr1=-1.0）")
