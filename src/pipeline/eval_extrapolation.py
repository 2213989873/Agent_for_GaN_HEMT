"""T4 外推验证（作战手册 T4 / 卡10-bis 任务3 方法对 M5 最终卡的复跑）

用未参与拟合的网格复测：提取卡 vs 答案卡（ground truth，data/sim/<dev>.inc）。
网格（练兵拟合协议之外）：
  Vd=4V 转移、Vd=8V 转移（拟合只用 Vd=1V 转移 + 标准输出网格；dt 浮地自热生效）
  T=85°C 转移（温度族未练兵——量化"未建模温度效应"的反弹幅度，手册风险表第4行）
判读：NRMSE 反弹 >2× 拟合集内值 → 记录外推风险（卡10-bis 规范：补偿解须记录
外推风险，仅作最后手段）。

用法：python src/pipeline/eval_extrapolation.py --device yi
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools.sim_tools import NGSPICE, OSDI_REL, SIM_DIR  # noqa: E402

# (名称, Vd, 温度)——拟合集外网格
GRIDS = [("Vd=4V 转移", 4.0, None), ("Vd=8V 转移", 8.0, None), ("T=85°C 转移(Vd=1V)", 1.0, 85)]


def load_answer_card(device: str) -> dict:
    """解析答案卡 .inc 的 .model 行（含 `+` 续行）为参数 dict。"""
    txt = (ROOT / "data" / "sim" / f"{device}.inc").read_text(encoding="utf-8")
    m = re.search(r"\.model\s+\S+\s+asmhemt\s*\(([^)]*)\)", txt, re.S)
    body = m.group(1).replace("+", " ").replace("\n", " ")
    return {k: float(v) for k, v in
            (tok.split("=", 1) for tok in body.split() if "=" in tok)}


def load_extracted_card(device: str) -> dict:
    """submission/<dev>_modelcard.json → 完整模型行参数（补开关，同 sim_tools 约定）。"""
    card = json.loads((ROOT / "submission" / f"{device}_modelcard.json")
                      .read_text(encoding="utf-8"))
    params = {"rdsmod": 1, **{k: float(v) for k, v in card["params"].items()}}
    if "rontr1" in params:
        params["trapmod"] = 2
    if "rth0" in params:
        params["shmod"] = 1
    return params


def run_transfer_at(params: dict, vd: float, temp: float | None, tag: str) -> np.ndarray:
    """Vd=vd 的转移扫描（Vg -4→2 步0.05），dt 浮地；temp 非空时设 .options TEMP。"""
    card = " ".join(f"{k}={v}" for k, v in params.items())
    opt = f".options TEMP={temp}\n" if temp is not None else ""
    netlist = f"""* T4 外推复测 #{tag}: Vd={vd} TEMP={temp} {card}
Vd d 0 {vd}
Vg g 0 0
N1 d g 0 0 dt xmod
.model xmod asmhemt ({card})
{opt}
.control
pre_osdi {OSDI_REL}
dc Vg -4 2 0.05
wrdata extrap_trial_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"extrap_trial_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("ngspice 失败: " + r.stdout + r.stderr)
    return -np.loadtxt(SIM_DIR / f"extrap_trial_{tag}.csv")[:, 1]


def nrmse(a: np.ndarray, ref: np.ndarray) -> float:
    return float(np.sqrt(np.mean(((a - ref) / np.abs(ref).max()) ** 2)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, choices=["jia", "yi", "bing"])
    args = ap.parse_args()
    truth = load_answer_card(args.device)
    extr = load_extracted_card(args.device)
    print(f"T4 外推复测（{args.device}）：提取卡 vs 答案卡 {truth}")
    for name, vd, temp in GRIDS:
        y_t = run_transfer_at(truth, vd, temp, f"t_{args.device}")
        y_e = run_transfer_at(extr, vd, temp, f"e_{args.device}")
        r = nrmse(y_e, y_t)
        print(f"  {name}: NRMSE = {r:.3%}（峰值 {np.abs(y_t).max():.4g}A）")


if __name__ == "__main__":
    main()
