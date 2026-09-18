* 任务10-bis 任务3：外推风险量化
* 补偿解(voff=-2.5181,u0=83.97e-3) vs 真值乙全处方，在未拟合网格对比
Vd  d   0 1
Vg  g   0 0
Vm1 d   dm1 0
Vm2 d   dm2 0
N1 dm1 g 0 0 0 compmod
N2 dm2 g 0 0 0 truemod
.model compmod asmhemt (rdsmod=1 voff=-2.5181 u0=83.97e-3)
.model truemod asmhemt (rdsmod=1 voff=-2.2 u0=150e-3 shmod=1 rth0=20 cth0=1e-6 trapmod=2 rontr1=-1.0)

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
* (a) Vd=4V 转移（未参与拟合的偏置段）
alter Vd = 4
dc Vg -4 2 0.05
wrdata extrap_vd4.csv i(vm1) i(vm2)
* (b) Vd=8V 转移（更远偏置段）
alter Vd = 8
dc Vg -4 2 0.05
wrdata extrap_vd8.csv i(vm1) i(vm2)
* (c) Vd=1V 但 T=85C（非室温外推）
alter Vd = 1
set temp = 85
dc Vg -4 2 0.05
wrdata extrap_t85.csv i(vm1) i(vm2)
.endc

.end
