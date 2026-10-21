#!/usr/bin/env bash
#
# Helper script to manage SSH Dynamic SOCKS5 Proxy to the Tencent Cloud Lighthouse server.
#
# Usage:
#   scripts/tunnel_china.sh start     # Start background SOCKS5 proxy on 127.0.0.1:10808
#   scripts/tunnel_china.sh stop      # Stop the proxy
#   scripts/tunnel_china.sh status    # Check status and verify egress IP
#   eval "$(scripts/tunnel_china.sh env)" # Export ARF_CHINA_PROXY in current shell
#
set -euo pipefail

PORT="${SOCKS_PORT:-10808}"
HOST="${LIGHTHOUSE_HOST:-lighthouse}"

is_running() {
    pgrep -f "ssh.*-D ${PORT} ${HOST}" > /dev/null 2>&1
}

start_tunnel() {
    if is_running; then
        echo "==> SOCKS5 tunnel is already running on port ${PORT}."
        exit 0
    fi
    echo "==> Starting SSH SOCKS5 tunnel to ${HOST} on 127.0.0.1:${PORT}..."
    if ! ssh -o BatchMode=yes -o ExitOnForwardFailure=yes \
             -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
             -f -N -D "${PORT}" "${HOST}"; then
        echo "==> Failed to start tunnel. Check SSH connection to '${HOST}'." >&2
        exit 1
    fi
    sleep 1
    if is_running; then
        echo "==> Tunnel established successfully."
        echo "    Export proxy: export ARF_CHINA_PROXY=socks5://127.0.0.1:${PORT}"
    else
        echo "==> SSH exited after starting; no tunnel on port ${PORT}." >&2
        exit 1
    fi
}

stop_tunnel() {
    if is_running; then
        echo "==> Stopping SSH SOCKS5 tunnel on port ${PORT}..."
        pkill -f "ssh.*-D ${PORT} ${HOST}" || true
        echo "==> Stopped."
    else
        echo "==> Tunnel is not running."
    fi
}

check_status() {
    if is_running; then
        echo "==> Tunnel is RUNNING on 127.0.0.1:${PORT}."
        echo "==> Testing egress IP via proxy..."
        ip_info=$(curl -s --max-time 5 --socks5 "127.0.0.1:${PORT}" https://httpbin.org/ip 2>/dev/null || echo '{"origin": "failed"}')
        echo "    Egress IP: ${ip_info}"
    else
        echo "==> Tunnel is NOT running."
    fi
}

print_env() {
    echo "export ARF_CHINA_PROXY=socks5://127.0.0.1:${PORT}"
}

cmd="${1:-status}"
case "${cmd}" in
    start)  start_tunnel ;;
    stop)   stop_tunnel ;;
    status) check_status ;;
    env)    print_env ;;
    *)
        echo "Usage: $0 {start|stop|status|env}" >&2
        exit 1
        ;;
esac
