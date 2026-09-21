* 丙器件 转移特性（与 transfer_jia.sp 同协议）
.include bing.inc
Vd d 0 1
Vg g 0 0
N1 d g 0 0 0 bingmod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
dc Vg -4 2 0.05
wrdata transfer_bing.csv i(vd)
.endc

.end
