* 开关瞬态：关态应力后开闸，看 Id 恢复的陷阱滞后
.include jia.inc
.include yi.inc
Vd  d  0 8
Vd2 d2 0 8
Vg  g  0 PULSE(-3 1 0 0.1u 0.1u 20u 100u)

N1 d  g 0 0 0    jiamod
N2 d2 g 0 0 dt_y yimod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
tran 0.05u 200u
wrdata tran_pulse.csv i(vd) i(vd2)
.endc

.end
