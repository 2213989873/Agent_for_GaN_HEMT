* 探针5：rdsmod 开关效应 + 陷阱复活判决（DC 输出扫描，Vg=1V 固定，dt 全接地=等温）
Vd  d   0 0
Vg  g   0 1
Vm1 d   dm1 0
Vm2 d   dm2 0
Vm3 d   dm3 0
Vm4 d   dm4 0
N1 dm1 g 0 0 0 m1
N2 dm2 g 0 0 0 m2
N3 dm3 g 0 0 0 m3
N4 dm4 g 0 0 0 m4
.model m1 asmhemt ()
.model m2 asmhemt (rdsmod=1)
.model m3 asmhemt (rdsmod=1 trapmod=2 rontr1=-1.0)
.model m4 asmhemt (voff=-2.2 u0=150e-3 shmod=1 rth0=20 cth0=1e-6 trapmod=2 rontr1=-1.0)
.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
dc Vd 0 8 0.05
wrdata probe_rdsmod.csv i(vm1) i(vm2) i(vm3) i(vm4)
.endc
.end
