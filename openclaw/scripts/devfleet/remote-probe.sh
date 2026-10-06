#!/usr/bin/env bash
# Runs ON a dev-fleet host (piped over ssh). Read-only. Emits key=value lines.
export LC_ALL=C
echo "hostname=$(hostname)"
echo "uptime_s=$(cut -d. -f1 /proc/uptime)"
echo "load1=$(cut -d' ' -f1 /proc/loadavg)"
echo "ncpu=$(nproc)"
awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}/SwapTotal/{st=$2}/SwapFree/{sf=$2}END{printf "mem_avail_pct=%d\nswap_used_pct=%d\n",a*100/t,(st>0?(st-sf)*100/st:0)}' /proc/meminfo
df -P -x tmpfs -x devtmpfs -x overlay -x squashfs -x efivarfs 2>/dev/null | awk 'NR>1{gsub("%","",$5); print "disk="$6":"$5}'
df -P -i -x tmpfs -x devtmpfs -x overlay -x squashfs -x efivarfs 2>/dev/null | awk 'NR>1 && $5!="-"{gsub("%","",$5); print "inode="$6":"$5}'
systemctl --failed --no-legend --plain 2>/dev/null | awk '{print $1}' | while read -r u; do
  echo "failed_unit=$u:$(systemctl is-enabled "$u" 2>/dev/null || echo unknown)"
done
for u in beacon validator execution; do
  s=$(systemctl is-active "$u.service" 2>/dev/null) && echo "svc=$u:$s" || { [ "$s" != "inactive" ] && [ -n "$s" ] && systemctl cat "$u.service" >/dev/null 2>&1 && echo "svc=$u:$s"; }
done
if command -v docker >/dev/null 2>&1; then
  docker ps -aq 2>/dev/null | xargs -r docker inspect --format 'ctr={{.Name}}|{{.State.Status}}|{{.State.ExitCode}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.RestartCount}}|{{.Config.Image}}' 2>/dev/null | sed 's#ctr=/#ctr=#'
fi
if [ -r /proc/mdstat ]; then
  awk '/^md/{if(n)print n":"l":"st":"f; n=$1; l=$4; st="-"; f=($0~/\(F\)/)?"failed_member":"ok"; if($3!="active")l="INACTIVE"; next}
       n && /blocks/{if(match($0,/\[[U_]+\]/))st=substr($0,RSTART,RLENGTH)}
       END{if(n)print n":"l":"st":"f}' /proc/mdstat | sed 's/^/md=/'
fi
sudo -n journalctl -k -p err --since "-24h" --no-pager -q 2>/dev/null \
  | grep -iE 'I/O error|EXT4-fs error|XFS .*error|Buffer I/O|blk_update_request|nvme.*(timeout|reset|failed)|ata[0-9.]+: (failed|exception)|md/raid.*(fail|disabled)|Medium Error|critical medium|Out of memory|oom-kill' \
  | tail -n 5 | sed 's/^/kerr=/' | cut -c1-240
if command -v smartctl >/dev/null 2>&1; then
  for d in $(lsblk -dno NAME,TYPE 2>/dev/null | awk '$2=="disk"{print $1}'); do
    out=$(sudo -n smartctl -H -A "/dev/$d" 2>/dev/null)
    h=$(echo "$out" | grep -iE 'overall-health|SMART Health Status' | awk -F: '{gsub(/^ +/,"",$2); print $2}')
    used=$(echo "$out" | awk -F: '/Percentage Used/{gsub(/[ %]/,"",$2); print $2}')
    [ -n "$h" ] && echo "smart=$d:$h:${used:-?}"
  done
fi
for port in 9596 5052; do
  sync=$(curl -s -m 5 "http://127.0.0.1:$port/eth/v1/node/syncing" 2>/dev/null)
  if [ -n "$sync" ]; then
    echo "bn_port=$port"
    echo "bn_syncing=$sync"
    echo "bn_peers=$(curl -s -m 5 "http://127.0.0.1:$port/eth/v1/node/peer_count" 2>/dev/null)"
    echo "bn_version=$(curl -s -m 5 "http://127.0.0.1:$port/eth/v1/node/version" 2>/dev/null)"
    break
  fi
done
[ -f /var/run/reboot-required ] && echo "reboot_required=1"
echo "probe_done=1"
