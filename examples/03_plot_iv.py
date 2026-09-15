"""任务 03：看懂 I-V 曲线 —— 输出特性族 + 转移特性（pandas + matplotlib）

输入：examples/sample_iv.csv（虚拟 GaN HEMT 输出特性，列 vgs, vds, id，含自热效应）
输出：
  examples/output_iv.png    输出特性族 Id-Vds（5 条 Vgs 曲线 + 三个区域标注）
  examples/transfer_iv.png  转移特性 Id-Vgs（Vds=5V）+ 最大斜率点切线外推 Vth

运行：python examples/03_plot_iv.py（无图形界面服务器，Agg 后端直接存 PNG）
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 服务器无显示器，必须在 import pyplot 之前切换到 Agg 后端

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文显示：指定系统里的 CJK 字体（缺中文字体会显示成方框）；负号用 ASCII 连字符
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).resolve().parent
df = pd.read_csv(HERE / "sample_iv.csv")

# ================= 图一：输出特性族 Id-Vds =================
fig, ax = plt.subplots(figsize=(8, 5))
for vgs, g in df.groupby("vgs"):
    ax.plot(g["vds"], g["id"], "o-", ms=3, lw=1.5, label=f"Vgs = {vgs:g} V")

ax.set_xlabel("Vds (V)")
ax.set_ylabel("Id (A/mm)")
ax.set_title("虚拟 GaN HEMT 输出特性族（含自热效应）")
ax.legend(title="栅压", loc="upper left")
ax.grid(alpha=0.3)
ax.set_ylim(0, 0.65)  # 顶部留白，放区域标注文字

# 三个物理区域的文字标注：文字放空白处，箭头指向对应区域
ax.annotate("线性区", xy=(1.0, 0.09), xytext=(2.5, 0.45),
            fontsize=13, arrowprops=dict(arrowstyle="->"))
ax.annotate("饱和区", xy=(10.0, 0.38), xytext=(8.0, 0.55),
            fontsize=13, arrowprops=dict(arrowstyle="->"))
ax.annotate("自热下弯", xy=(18.0, 0.47), xytext=(14.5, 0.58),
            fontsize=13, arrowprops=dict(arrowstyle="->"))

fig.tight_layout()
out_png = HERE / "output_iv.png"
fig.savefig(out_png, dpi=150)
print(f"已保存: {out_png}")

# ================= 图二：转移特性 Id-Vgs（Vds = 5V）+ 切线法外推 Vth =================
tr = df[df["vds"] == 5.0].sort_values("vgs")
vgs_arr = tr["vgs"].to_numpy()
id_arr = tr["id"].to_numpy()

# 数值微分求跨导 gm = dId/dVgs，最大斜率点即 gm 最大的点
gm = np.gradient(id_arr, vgs_arr, edge_order=2)
i_max = int(np.argmax(gm))
v0, i0, gm_max = vgs_arr[i_max], id_arr[i_max], gm[i_max]

# 最大斜率点的切线：Id = gm_max * (Vgs - v0) + i0；与横轴（Id=0）的交点即外推 Vth
vth = v0 - i0 / gm_max

fig2, ax2 = plt.subplots(figsize=(7, 5))
ax2.plot(vgs_arr, id_arr, "o-", lw=1.5, label="测量数据 Id–Vgs")
x_tan = np.linspace(vth, vgs_arr[-1] + 0.3, 50)  # 切线从横轴交点画起
ax2.plot(x_tan, gm_max * (x_tan - v0) + i0, "--",
         label=f"最大斜率点切线（Vgs = {v0:g} V 处）")
ax2.plot(vth, 0, "s", color="red", zorder=5)  # 标出横轴交点
ax2.annotate(f"Vth ≈ {vth:.2f} V", xy=(vth, 0), xytext=(4.5, 0.05),
             fontsize=12, arrowprops=dict(arrowstyle="->"))

ax2.set_xlabel("Vgs (V)")
ax2.set_ylabel("Id (A/mm)")
ax2.set_title("转移特性（Vds = 5 V）与切线法外推 Vth")
ax2.legend(loc="upper left")
ax2.grid(alpha=0.3)
ax2.set_xlim(0.8, None)  # 向左多留些空间，让横轴交点可见

fig2.tight_layout()
tr_png = HERE / "transfer_iv.png"
fig2.savefig(tr_png, dpi=150)
print(f"已保存: {tr_png}")

print(f"\n最大斜率点: Vgs = {v0:g} V, Id = {i0:.4f} A/mm, gm_max = {gm_max:.4f} A/mm/V")
print(f"切线外推估算 Vth ≈ {vth:.2f} V")
