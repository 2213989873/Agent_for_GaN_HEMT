* 丙器件 准静态 C-V（与 cv_gg_jia.sp 同协议）
.include bing.inc
Vd d 0 0
Vg g 0 PWL(0 -6  12u 6)
N1 d g 0 0 0 bingmod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
tran 0.01u 12u
wrdata cv_gg_bing.csv v(g) i(vg)
.endc

.end
