"""M3 标定实验：C-V 残差量级与敏感参数摸底（不进闭环，纯事实采集）

三问：
1. 真值卡（jia 默认）对 cv_gg_jia 数据的残差是不是 ~0（同模型同协议，理论上零）？
2. voff 偏移 ±0.2V 的残差量级（曲线平移敏感度）？
3. cgso/cgdo 偏移对残差的量级（电容族可辨识度）？
据此定 cv_gg 形态的 NRMSE 达标线。
"""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("/home/zhengjp2/projects/gan-hemt-agent")
sys.path.insert(0, str(ROOT))
from src.eval.metrics import nrmse  # noqa: E402
from src.tools.sim_tools import NGSPICE, OSDI_REL, SIM_DIR  # noqa: E402

SLOPE = 1e6        # V/s，PWL(0 -6 12u 6)


def load_cv(path):
    d = np.loadtxt(path)
    vg, i = d[:, 1], d[:, 3]
    c = -i / SLOPE
    return vg[5:-5], c[5:-5]          # 卡08 纪律：丢首尾各5点


def run_cv(params: dict, tag: str):
    card = " ".join(f"{k}={v}" for k, v in params.items())
    netlist = f"""* M3 标定 #{tag}: {card}
Vd d 0 0
Vg g 0 PWL(0 -6  12u 6)
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1 {card})

.control
pre_osdi {OSDI_REL}
tran 0.01u 12u
wrdata cv_trial_{tag}.csv v(g) i(vg)
.endc
.end
"""
    sp = SIM_DIR / f"cv_trial_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return load_cv(SIM_DIR / f"cv_trial_{tag}.csv")


def nrmse_on_grid(sim_vg, sim_c, tgt_vg, tgt_c):
    c_interp = np.interp(tgt_vg, sim_vg, sim_c)   # 自适应步长网格对齐
    return nrmse(c_interp, tgt_c)


tgt_vg, tgt_c = load_cv(ROOT / "data/devices/jia/cv_gg_jia.csv")
print(f"目标：jia cv_gg，{len(tgt_vg)} 点，峰值 {tgt_c.max()*1e15:.1f}fF")

cases = [
    ("真值卡（默认）", {}),
    ("voff=-1.8（+0.2V）", {"voff": -1.8}),
    ("voff=-2.2（-0.2V）", {"voff": -2.2}),
    ("cgdo=20fF（+10）", {"cgdo": 20e-15}),
    ("cgso=20fF（+10）", {"cgso": 20e-15}),
    ("cgso=cgdo=1fF", {"cgso": 1e-15, "cgdo": 1e-15}),
]
for label, p in cases:
    t0 = time.time()
    svg, sc = run_cv(p, f"cal{cases.index((label, p))}")
    n = nrmse_on_grid(svg, sc, tgt_vg, tgt_c)
    print(f"{label:24s} NRMSE = {n:8.4%}   （饱和段 {sc[-10:].mean()*1e15:.1f}fF，{time.time()-t0:.1f}s）")
