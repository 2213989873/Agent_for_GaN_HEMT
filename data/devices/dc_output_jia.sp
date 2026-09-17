* 甲器件 DC 输出特性 Id-Vd（Vg 阶梯嵌套扫描）
.include jia.inc
Vd d 0 0
Vg g 0 0
N1 d g 0 0 dt jiamod

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
dc Vd 0 12 0.1 Vg -1.5 1.5 0.5
wrdata dc_output_jia.csv i(vd)
.endc

.end
