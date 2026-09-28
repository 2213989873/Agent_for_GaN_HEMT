#!/bin/bash
# run_smoke3.sh — 复跑 v3 冒烟（验证 .lib 包装解法的可复现性）
pkill -f 'nbexe[c]' 2>/dev/null; pkill -f 'jre17/bin/jav[a]' 2>/dev/null; pkill -f 'IEP[S]' 2>/dev/null
sleep 2
cd ~   # MeQLab 会在 cwd 落运行文件，勿在仓库目录内拉起
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
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p2_smoke_v3.py
