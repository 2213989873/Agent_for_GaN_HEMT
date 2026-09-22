"""熔断 A 处置工具：分段残差归因（卡10-bis 任务1 方法的代码化）

单族精修撞墙（>100 次仿真仍 >5%）时，别傻跑——把残差按偏置区分段归因：
  dc_output 847 点排布（实测判定）：Vg 外层 7 档（-1.5→1.5 步0.5）× Vd 内层
  121 点（0→12 步0.1）。分段：线性区 Vd<2 / 饱和区 2≤Vd<8 / 高压自热区 Vd≥8。

判读规则（知识表3 签名体系）：
  残差集中在高压段          → 自热族 rth0 缺失/失配；
  段总量随 Vg 档单调变化     → 陷阱耦合 rontr1（ron 随 Vg 漂移）；
  各段均匀偏高              → 阈值/迁移率/接入电阻基线（voff/u0）。

用法：
  python src/pipeline/residual_triage.py --device yi                # 当前最优卡
  python src/pipeline/residual_triage.py --device yi --set voff=-2.0 u0=0.17
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools import sim_tools as st  # noqa: E402

VG_VALS = np.arange(-1.5, 1.51, 0.5)
VD_SEGS = [("线性区 Vd<2", 0, 20), ("饱和区 2≤Vd<8", 20, 80), ("高压自热区 Vd≥8", 80, 121)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, choices=["jia", "yi", "bing"])
    ap.add_argument("--set", nargs="*", default=None,
                    help="参数覆盖，如 voff=-2.0 u0=0.17；缺省读 submission 最优卡")
    args = ap.parse_args()

    if args.set:
        params = {k: float(v) for k, v in
                  (tok.split("=", 1) for tok in args.set)}
    else:
        card = json.loads((ROOT / "submission" / f"{args.device}_modelcard.json")
                          .read_text(encoding="utf-8"))
        params = {k: float(v) for k, v in card["params"].items()}
    print(f"分段残差归因（{args.device}，参数 { {k: round(v, 4) for k, v in params.items()} }）")

    fn = st.run_output_selfheat_params if "rth0" in params else st.run_output_params
    sim = fn(params, "triage").reshape(7, 121)
    tgt = (-np.loadtxt(ROOT / "data" / "devices" / args.device
                       / f"dc_output_{args.device}.csv")[:, 1]).reshape(7, 121)
    scale = np.abs(tgt).max()

    seg_sse = np.zeros(3)
    vg_nrmse = []
    header = "Vg\\区段      " + "".join(f"{n:>14}" for n, _, _ in VD_SEGS) + "     整档 NRMSE"
    print(header)
    for i, vg in enumerate(VG_VALS):
        row = []
        for s, (name, a, b) in enumerate(VD_SEGS):
            r2 = float(np.mean(((sim[i, a:b] - tgt[i, a:b]) / scale) ** 2))
            seg_sse[s] += r2
            row.append(r2 ** 0.5)
        vg_nrmse.append(float(np.sqrt(np.mean(((sim[i] - tgt[i]) / scale) ** 2))))
        print(f"Vg={vg:+.1f}  " + "".join(f"{r:>14.3%}" for r in row)
              + f"     {vg_nrmse[-1]:.3%}")
    share = seg_sse / seg_sse.sum()
    print("区段残差占比: " + "，".join(f"{n} {s:.0%}" for s, (n, _, _) in zip(share, VD_SEGS)))

    # 归因判决（规则见模块 docstring）
    trend = np.corrcoef(VG_VALS, vg_nrmse)[0, 1]
    verdicts = []
    if share[2] > 0.6:
        verdicts.append(f"高压段占残差 {share[2]:.0%}（>60%）→ 自热族 rth0 缺失/失配")
    if abs(trend) > 0.8:
        verdicts.append(f"整档 NRMSE 随 Vg {'递增' if trend > 0 else '递减'}（|corr|={abs(trend):.2f}>0.8）"
                        f" → 陷阱耦合 rontr1 族")
    if not verdicts:
        verdicts.append("各段均匀 → 阈值/迁移率/接入电阻基线（voff/u0）复核")
    print("归因判决: " + "；".join(verdicts))


if __name__ == "__main__":
    main()
