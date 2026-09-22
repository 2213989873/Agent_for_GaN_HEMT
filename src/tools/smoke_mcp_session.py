"""M4 链路自检：McpSession 长连接冒烟（正式提取前的快速探针，约 15s）

验证：长连接建立 → 三形态各跑一次 → 计数一致 → close 干净退出。
运行：python src/tools/smoke_mcp_session.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools.interface import get_session  # noqa: E402

s = get_session(via_mcp=True)
h = s.select_model("asmhemt")
s.reset_count()
s.set_params(h, {"voff": -2.0, "u0": 0.17, "rth0": 20.0, "tbar": 2.5e-8})

y = s.run_simulation(h, {"form": "dc_output"})
print(f"dc_output: shape={y.shape}, 峰值={float(np.abs(y).max()):.4g} A")
y = s.run_simulation(h, {"form": "dc_transfer"})
print(f"dc_transfer: shape={y.shape}, 峰值={float(np.abs(y).max()):.4g} A")
grid = np.linspace(-3, 1, 17)
y = s.run_simulation(h, {"form": "cv_gg", "grid": grid})
print(f"cv_gg: shape={y.shape}, C 范围 [{float(y.min()):.4g}, {float(y.max()):.4g}] F")

n = s.get_call_count()
assert n == 3, f"计数 {n} != 3"
print(f"server 端计数: {n}（=3 次仿真 ✅）")
s.close()
print("MCP 长连接冒烟通过")
