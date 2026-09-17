* 乙-阱对照 v2：yi 去掉自热（shmod=0），陷阱开强度 rontr1=-1（+ rdsmod=1 复活陷阱）
.model yitmod asmhemt (
+ rdsmod=1
+ voff=-2.2
+ u0=150e-3
+ shmod=0
+ trapmod=2
+ rontr1=-1.0
+ )
