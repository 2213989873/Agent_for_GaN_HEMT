* 乙-热对照 v2：yi 去掉陷阱，只留自热（+ rdsmod=1 基线）
.model yihmod asmhemt (
+ rdsmod=1
+ voff=-2.2
+ u0=150e-3
+ shmod=1
+ rth0=20
+ cth0=1e-6
+ )
