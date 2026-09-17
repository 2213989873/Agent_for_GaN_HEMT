* 开关瞬态 v2：50µs 关态应力 + 三管分离热/陷阱（阱管在线性区测）
.include jia.inc
.include yih.inc
.include yit.inc
Vd  d  0 8
Vd2 d2 0 8
Vd3 d3 0 1
Vg  g  0 PULSE(-3 1 50u 0.1u 0.1u 20u 200u)

N1 d  g 0 0 0    jiamod
N2 d2 g 0 0 dt_h yihmod
N3 d3 g 0 0 0    yitmod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
tran 0.05u 300u
wrdata tran_pulse2.csv i(vd) i(vd2) i(vd3)
.endc

.end
