#!/bin/sh
# HopTrace Testbed Fault Injector
# Usage: ./fault.sh <NODE_ID> <down|slow|loss|heal>
# Example: ./fault.sh WB3 down

NODE=$(echo "$1" | tr '[:lower:]' '[:upper:]')
ACTION=$(echo "$2" | tr '[:upper:]' '[:lower:]')

if [ -z "$NODE" ] || [ -z "$ACTION" ]; then
    echo "Usage: $0 <NODE_ID> <down|slow|loss|heal>"
    echo "Nodes: R1, WB1, WB2, AP1, AP2, WB3, WB4, R2, AP3, AP4, WB5, WB6, AP5, AP6"
    exit 1
fi

to_container() {
    echo "hoptrace-$(echo "$1" | tr '[:upper:]' '[:lower:]')"
}

get_descendants() {
    case "$1" in
        R1) echo "WB1 WB2 AP1 AP2 WB3 WB4 R2 AP3 AP4 WB5 WB6 AP5 AP6" ;;
        WB1) echo "WB2 AP1 AP2" ;;
        WB2) echo "AP1 AP2" ;;
        AP1|AP2) echo "" ;;
        WB3) echo "WB4 R2 AP3 AP4" ;;
        WB4) echo "R2 AP3 AP4" ;;
        R2) echo "AP3 AP4" ;;
        AP3|AP4) echo "" ;;
        WB5) echo "WB6 AP5 AP6" ;;
        WB6) echo "AP5 AP6" ;;
        AP5|AP6) echo "" ;;
        *) echo "" ;;
    esac
}

CONTAINER=$(to_container "$NODE")
DESCENDANTS=$(get_descendants "$NODE")

echo "[HopTrace Testbed] Target Node: $NODE (Container: $CONTAINER) | Action: $ACTION"

case "$ACTION" in
    down)
        echo "--> Simulating link/device outage: pausing $CONTAINER and descendants: $DESCENDANTS"
        docker pause "$CONTAINER" 2>/dev/null || docker stop "$CONTAINER"
        for d in $DESCENDANTS; do
            dc=$(to_container "$d")
            docker pause "$dc" 2>/dev/null || docker stop "$dc"
        done
        echo "--> Outage applied. Descendants are now unreachable (behind failure boundary)."
        ;;
    slow)
        echo "--> Injecting latency degradation on $CONTAINER: 120ms +/- 15ms"
        docker exec "$CONTAINER" tc qdisc replace dev eth0 root netem delay 120ms 15ms 2>/dev/null || \
        docker exec "$CONTAINER" tc qdisc add dev eth0 root netem delay 120ms 15ms
        echo "--> High latency applied to $NODE."
        ;;
    loss)
        echo "--> Injecting packet loss on $CONTAINER: 30% drop"
        docker exec "$CONTAINER" tc qdisc replace dev eth0 root netem loss 30% 2>/dev/null || \
        docker exec "$CONTAINER" tc qdisc add dev eth0 root netem loss 30%
        echo "--> Packet loss applied to $NODE."
        ;;
    heal)
        echo "--> Healing $CONTAINER and descendants: unpausing and clearing netem"
        docker unpause "$CONTAINER" 2>/dev/null || docker start "$CONTAINER" 2>/dev/null || true
        docker exec "$CONTAINER" tc qdisc del dev eth0 root 2>/dev/null || true
        for d in $DESCENDANTS; do
            dc=$(to_container "$d")
            docker unpause "$dc" 2>/dev/null || docker start "$dc" 2>/dev/null || true
            docker exec "$dc" tc qdisc del dev eth0 root 2>/dev/null || true
        done
        echo "--> Topology segment healed. Normal operation restored."
        ;;
    *)
        echo "Unknown action: $ACTION. Valid actions: down, slow, loss, heal."
        exit 1
        ;;
esac
