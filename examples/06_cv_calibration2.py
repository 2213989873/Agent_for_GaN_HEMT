"""M3 标定实验·第二轮：C-V 真正可辨识的参数是谁？

第一轮结论：cgso/cgdo 是 F/m 归一化，w=200µm 下不可辨识（0.001% 噪声级）。
本轮测：tbar（势垒层厚度，决定本征饱和电容）、eta0（DIBL）、cdscd（亚阈斜率漏致）。
"""
import sys

import numpy as np

sys.path.insert(0, "/home/zhengjp2/projects/gan-hemt-agent")
from examples import __init__  # noqa: F401  (仅确保包路径)
from importlib import import_module

cal = import_module("examples.05_cv_calibration")

tgt_vg, tgt_c = cal.load_cv(cal.ROOT / "data/devices/jia/cv_gg_jia.csv")

cases = [
    ("tbar=2.0e-8（-20%）", {"tbar": 2.0e-8}),
    ("tbar=3.0e-8（+20%）", {"tbar": 3.0e-8}),
    ("eta0=0.1（×1e8）", {"eta0": 0.1}),
    ("cdscd=0.1（×100）", {"cdscd": 0.1}),
    ("voff=-2.0001（微扰）", {"voff": -2.0001}),
]
for i, (label, p) in enumerate(cases):
    svg, sc = cal.run_cv(p, f"cal2_{i}")
    n = cal.nrmse_on_grid(svg, sc, tgt_vg, tgt_c)
    print(f"{label:24s} NRMSE = {n:8.4%}   （饱和段 {sc[-10:].mean()*1e15:.1f}fF）")
