#!/bin/bash
# run_smoke2.sh — NanoSpice 修复后重跑 P2 真链路冒烟（M7 子任务1 判据之二）
# 一体窗口：拉起 MeQLab → 等 gRPC 2008 → 立即跑 p2_smoke.py（避 2min watchdog）
pkill -f 'nbexe[c]' 2>/dev/null; pkill -f 'jre17/bin/jav[a]' 2>/dev/null; pkill -f 'IEP[S]' 2>/dev/null
sleep 2
cd ~   # MeQLab 会在 cwd 落运行文件（all-*.dat 等），勿在仓库目录内拉起
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
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p2_smoke.py
