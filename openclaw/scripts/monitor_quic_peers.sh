#!/bin/bash
# Monitor QUIC inbound peers and report when threshold is hit
THRESHOLD=10
CHECK_INTERVAL=300  # 5 minutes

while true; do
    RESULT=$(docker exec mainnet-consensus-1 wget -qO- http://localhost:5052/eth/v1/node/peers 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)['data']
    quic_in = [p for p in data if '/quic' in p.get('last_seen_p2p_address', '') and p.get('direction') == 'inbound']
    quic_out = [p for p in data if '/quic' in p.get('last_seen_p2p_address', '') and p.get('direction') == 'outbound']
    total = len(data)
    print(f'{len(quic_in)}|{len(quic_out)}|{total}')
except Exception as e:
    print(f'ERR|{e}')
" 2>/dev/null)

    QUIC_IN=$(echo "$RESULT" | cut -d'|' -f1)
    QUIC_OUT=$(echo "$RESULT" | cut -d'|' -f2)
    TOTAL=$(echo "$RESULT" | cut -d'|' -f3)
    
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")
    echo "[$TIMESTAMP] QUIC inbound: $QUIC_IN, outbound: $QUIC_OUT, total peers: $TOTAL"
    
    if [ "$QUIC_IN" != "ERR" ] && [ "$QUIC_IN" -ge "$THRESHOLD" ] 2>/dev/null; then
        echo "THRESHOLD_REACHED: $QUIC_IN inbound QUIC peers"
        exit 0
    fi
    
    sleep $CHECK_INTERVAL
done
