"""ngspice 仿真工具：生成网表、跑仿真、读回数据

设计约定（任务卡 05 / 07 / 07.5 建立）：
- 工作目录固定在 data/sim/（pre_osdi 相对路径约定的前提）
- ngspice 在 ~/local/bin/（自编译，--enable-osdi）
- 试算器件一律带 rdsmod=1（任务卡 07 教训：这是接入电阻/陷阱挂载的总开关）
"""
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = ROOT / "data" / "sim"
NGSPICE = str(Path.home() / "local" / "bin" / "ngspice")
OSDI_REL = "VA-Models/code/ASMHEMT/vacode/asmhemt.osdi"  # 相对 SIM_DIR


def run_transfer(voff: float, tag: str) -> tuple[np.ndarray, np.ndarray]:
    """用指定 voff 跑线性区转移特性（Vd=1V，Vg 从 -4 扫到 2，与 transfer_jia.sp 同协议）。

    返回 (Vg 数组, Id 数组[取正])。每次试算的网表和 csv 都留在 data/sim/ 可追溯。
    """
    netlist = f"""* agent 试算 #{tag}: voff={voff}
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1 voff={voff})

.control
pre_osdi {OSDI_REL}
dc Vg -4 2 0.05
wrdata transfer_trial_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"transfer_trial_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ngspice 失败:\n{r.stdout}\n{r.stderr}")
    d = np.loadtxt(SIM_DIR / f"transfer_trial_{tag}.csv")
    return d[:, 0], -d[:, 1]


def run_transfer2(voff: float, u0: float, tag: str) -> tuple[np.ndarray, np.ndarray]:
    """两参数版：voff（V）+ u0（m²/(V·s)）。协议同 transfer_jia.sp（Vd=1V，Vg -4→2）。"""
    netlist = f"""* agent 试算 #{tag}: voff={voff} u0={u0}
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1 voff={voff} u0={u0})

.control
pre_osdi {OSDI_REL}
dc Vg -4 2 0.05
wrdata transfer_trial2_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"transfer_trial2_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ngspice 失败:\n{r.stdout}\n{r.stderr}")
    d = np.loadtxt(SIM_DIR / f"transfer_trial2_{tag}.csv")
    return d[:, 0], -d[:, 1]


def run_transfer3(voff: float, u0: float, rontr1: float, tag: str) -> tuple[np.ndarray, np.ndarray]:
    """三参数版：voff + u0 + rontr1（陷阱耦合进提取空间，trapmod=2 开）。
    协议同 transfer_jia.sp（Vd=1V，Vg -4→2）。任务卡10-bis 任务2。"""
    netlist = f"""* agent 试算 #{tag}: voff={voff} u0={u0} rontr1={rontr1}
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1 voff={voff} u0={u0} trapmod=2 rontr1={rontr1})

.control
pre_osdi {OSDI_REL}
dc Vg -4 2 0.05
wrdata transfer_trial3_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"transfer_trial3_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ngspice 失败:\n{r.stdout}\n{r.stderr}")
    d = np.loadtxt(SIM_DIR / f"transfer_trial3_{tag}.csv")
    return d[:, 0], -d[:, 1]
