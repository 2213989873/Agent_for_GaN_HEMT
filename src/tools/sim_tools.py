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


def run_transfer_params(params: dict, tag: str) -> tuple[np.ndarray, np.ndarray]:
    """通用版：params 为任意参数子集 {"voff":..., "u0":..., "rontr1":...}。
    自动带 rdsmod=1；含 rontr1 时自动开 trapmod=2（任务卡11，QA 闭环用）。"""
    card = " ".join(f"{k}={v}" for k, v in params.items())
    trap = " trapmod=2" if "rontr1" in params else ""
    netlist = f"""* agent 试算 #{tag}: {card}
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1{trap} {card})

.control
pre_osdi {OSDI_REL}
dc Vg -4 2 0.05
wrdata transfer_trialP_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"transfer_trialP_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("ngspice 失败: " + r.stdout + r.stderr)
    d = np.loadtxt(SIM_DIR / f"transfer_trialP_{tag}.csv")
    return d[:, 0], -d[:, 1]


def run_output_params(params: dict, tag: str) -> np.ndarray:
    """输出特性版：嵌套 dc（Vd 0→12 步0.1 × Vg -1.5→1.5 步0.5，847 点），
    与 dc_output_yi.sp 同协议。dt 接地（等温）；含 rontr1 自动开 trapmod=2。
    返回 Id 一维数组（847 点，取正）。任务卡12 Part B。"""
    card = " ".join(f"{k}={v}" for k, v in params.items())
    trap = " trapmod=2" if "rontr1" in params else ""
    netlist = f"""* agent 试算(输出特性) #{tag}: {card}
Vd d 0 0
Vg g 0 0
N1 d g 0 0 0 trialmod
.model trialmod asmhemt (rdsmod=1{trap} {card})

.control
pre_osdi {OSDI_REL}
dc Vd 0 12 0.1 Vg -1.5 1.5 0.5
wrdata output_trialP_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"output_trialP_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("ngspice 失败: " + r.stdout + r.stderr)
    d = np.loadtxt(SIM_DIR / f"output_trialP_{tag}.csv")
    return -d[:, 1]


def run_output_selfheat_params(params: dict, tag: str) -> np.ndarray:
    """含自热的输出特性版：协议同 dc_output_yi.sp（847 点嵌套扫描）。
    含 rth0 → dt 浮地 + shmod=1（自热生效）；不含 → dt 接地（等温）。
    含 rontr1 自动开 trapmod=2。任务卡13。"""
    card = " ".join(f"{k}={v}" for k, v in params.items())
    trap = " trapmod=2" if "rontr1" in params else ""
    if "rth0" in params:
        heat, dt_node = " shmod=1", "dt"
    else:
        heat, dt_node = "", "0"
    netlist = f"""* agent 试算(输出特性+自热) #{tag}: {card}
Vd d 0 0
Vg g 0 0
N1 d g 0 0 {dt_node} trialmod
.model trialmod asmhemt (rdsmod=1{trap}{heat} {card})

.control
pre_osdi {OSDI_REL}
dc Vd 0 12 0.1 Vg -1.5 1.5 0.5
wrdata output_sh_trialP_{tag}.csv i(vd)
.endc
.end
"""
    sp = SIM_DIR / f"output_sh_trialP_{tag}.sp"
    sp.write_text(netlist, encoding="utf-8")
    r = subprocess.run([NGSPICE, "-b", sp.name], cwd=SIM_DIR,
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("ngspice 失败: " + r.stdout + r.stderr)
    d = np.loadtxt(SIM_DIR / f"output_sh_trialP_{tag}.csv")
    return -d[:, 1]
