* 乙器件参数卡 v4：v3 + rdsmod=1（陷阱电阻挂载总开关）
* 强自热(shmod=1, rth0×4) + 脉冲陷阱(trapmod=2, rontr1=-1) + 轻微"换 die"偏移
.model yimod asmhemt (
+ rdsmod=1
+ voff=-2.2
+ u0=150e-3
+ shmod=1
+ rth0=20
+ cth0=1e-6
+ trapmod=2
+ rontr1=-1.0
+ )
