* 甲器件线性区转移特性 Id-Vg（Vd=1V）—— Agent 提取 voff 的"晶圆实测"目标
.include yi.inc
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 yimod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
dc Vg -4 2 0.05
wrdata transfer_yi.csv i(vd)
.endc

.end
