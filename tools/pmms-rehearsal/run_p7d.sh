#!/bin/bash
# run_p7d.sh — P7d 对照实验：官方 BSIM 卡(包装版)+官方数据，判 error=nan 责任方
set -euo pipefail
cd "$HOME/projects/gan-hemt-agent"

# 1) 包装官方 iv_cv/nmos.l（原件不动）：.lib tt 直包 .model nmos
CARD=data/sim/nmos_wrapped.inc
{
  echo '* P7d 对照组：官方 nmos.l 的 .lib 包装（原件 etc/demo/model/mosfet/iv_cv/nmos.l 未动）'
  echo '.lib tt'
  cat "/home/zhengjp2/MS-MeQLab/MS-MeQLab/etc/demo/model/mosfet/iv_cv/nmos.l"
  echo '.endl tt'
} > "$CARD"
echo "wrapped card head:"; head -4 "$CARD"; echo "... ($(wc -l < "$CARD") lines)"

# 2) 探针 cp 就位（p7d_probe.py 应已由教练放在 tools/pmms-rehearsal/）

# 3) 预热 + 窗口
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
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p7d_probe.py 2>&1 | tee tools/pmms-rehearsal/p7d_output.txt
