* 冒烟测试：转移特性 Id-Vg
Vd d 0 6
Vg g 0 0
N1 d g 0 0 0 asmhemtdev
.model asmhemtdev asmhemt ()

.control
pre_osdi VA-Models/code/ASMHEMT/vacode/asmhemt.osdi
dc Vg -2 6 0.1
wrdata transfer.csv i(vd)
.endc

.end
