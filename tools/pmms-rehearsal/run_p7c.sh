#!/bin/bash
# run_p6.sh — P6 数据 I/O 支线探针：生成 jia_transfer.pms + 预热 + 窗口内跑探针
set -euo pipefail
cd "$HOME/projects/gan-hemt-agent"

# 1) 离线生成 .pms（复刻官方 demo 格式；w/l 为任意占位元数据 t=27；Id 取负还原符号约定）
~/miniconda3/envs/gan-agent/bin/python - << 'PYEOF'
import numpy as np
d = np.loadtxt("data/devices/jia/transfer_jia.csv")   # Vg, Id(ngspice i(vd) 约定为负)
hdr = ("// Primarius Technologies Co., Ltd.\n// Sweep Data\n"
       "{group=Id_Vg,y=(Id),x=Vgs,p=Vbs(0.0),condition=(ref_vs=0.00000,vds=1.0000000),"
       "device=(type=Mosfet,polarity=NMOS,w=10.0,t=27.0,l=1.0)}\n")
with open("data/sim/jia_transfer.pms", "w") as f:
    f.write(hdr)
    for vg, idv in d:
        f.write(f"{vg:g}\t{-idv:.6e}\n")
print("jia_transfer.pms written,", len(d), "rows")
PYEOF
head -5 data/sim/jia_transfer.pms

# 2) 预热 + 窗口内探针
pkill -f 'nbexe[c]' 2>/dev/null || true; pkill -f 'jre17/bin/jav[a]' 2>/dev/null || true; pkill -f 'IEP[S]' 2>/dev/null || true
sleep 2
cd ~
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
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p7c_probe.py 2>&1 | tee tools/pmms-rehearsal/p7c_output.txt
