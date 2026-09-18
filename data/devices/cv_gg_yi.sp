* 准静态 C-V：PWL 斜坡扫 Vg，C = -i(vg)/(dV/dt)，斜率 1e6 V/s
.include yi.inc
Vd d 0 0
Vg g 0 PWL(0 -6  12u 6)
N1 d g 0 0 0 yimod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
tran 0.01u 12u
wrdata cv_gg_yi.csv v(g) i(vg)
.endc

.end
