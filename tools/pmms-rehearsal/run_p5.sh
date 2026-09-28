#!/bin/bash
# run_p5.sh — P5 全参数写入路径探针：建声明卡 + 预热 + 窗口内跑探针
set -euo pipefail

# 声明卡（占位值，非真值；只为验证"卡上声明"是否写入前提）
cat > "$HOME/projects/gan-hemt-agent/data/sim/jia_declared.inc" << 'EOF'
* P5 探针卡：声明常用参数（占位值，验证 list_params/set_param 行为）
.lib tt
.model jiafull asmhemt (
+ rdsmod=1
+ voff=-1.0
+ u0=0.03
+ rth0=20.0
+ tbar=1e-8
+ rontr1=0.0
+ )
.endl tt
EOF
echo "declared card written:"; cat "$HOME/projects/gan-hemt-agent/data/sim/jia_declared.inc"

pkill -f 'nbexe[c]' 2>/dev/null || true; pkill -f 'jre17/bin/jav[a]' 2>/dev/null || true; pkill -f 'IEP[S]' 2>/dev/null || true
sleep 2
cd ~   # 勿在仓库目录拉起 MeQLab（运行残留）
nohup /home/zhengjp2/MS-MeQLab/bin/MS-MeQLab --grpc-port-timeout 2008 --feature 'primarius|rf_main|pnano' > /tmp/meqlab_warm.log 2>&1 &
echo "LAUNCH_PID=$!"
ok=0
for i in $(seq 1 24); do
  if ss -tln 2>/dev/null | grep -q ':2008'; then ok=1; echo "PORT_UP after ~$((i*10))s"; break; fi
  sleep 10
done
if [ "$ok" != "1" ]; then
  echo "PORT_TIMEOUT"; tail -3 /tmp/meqlab_warm.log; exit 1
fi
cd ~/projects/gan-hemt-agent
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p5_probe.py 2>&1 | tee tools/pmms-rehearsal/p5_output.txt
