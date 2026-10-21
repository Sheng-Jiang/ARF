#!/usr/bin/env bash
#
# sync_china_lighthouse.sh — Execute domestic China leg ingestion on Lighthouse.
#
# Runs either:
#   1. Remotely from developer workstation (default): syncs codebase via rsync,
#      triggers the ingestion on Lighthouse over SSH, and streams logs.
#   2. Locally on Lighthouse (--local): sets up python environment if needed,
#      runs `arf.run --leg China`, and syncs DuckDB snapshots to GCS via HMAC.
#
# Usage:
#   scripts/sync_china_lighthouse.sh                     # Remote sync for today CST
#   scripts/sync_china_lighthouse.sh --as-of 2026-10-21  # Remote sync for specific date
#   scripts/sync_china_lighthouse.sh --local             # Direct local run on Lighthouse
#
set -euo pipefail

SSH_HOST="${ARF_LIGHTHOUSE_HOST:-lighthouse}"
REMOTE_DIR="/home/ubuntu/ARF"
DEFAULT_AS_OF=$(date +%Y-%m-%d)
AS_OF="${DEFAULT_AS_OF}"
RUN_MODE="auto"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --as-of YYYY-MM-DD   Snapshot date to compute (default: today ${DEFAULT_AS_OF})
  --local              Execute locally on this host (used by systemd or SSH runner)
  --remote             Force remote execution via SSH to ${SSH_HOST}
  --help               Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --as-of)
            AS_OF="$2"
            shift 2
            ;;
        --local)
            RUN_MODE="local"
            shift
            ;;
        --remote)
            RUN_MODE="remote"
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            ;;
    esac
done

# Auto-detect mode if not explicitly set
if [[ "${RUN_MODE}" == "auto" ]]; then
    if [[ "$(hostname)" =~ (ubuntu|VM-0-8-ubuntu) ]] && [[ -d "/home/ubuntu" ]]; then
        RUN_MODE="local"
    else
        RUN_MODE="remote"
    fi
fi

# ------------------------------------------------------------------------------
# LOCAL RUNNER (Executed on the domestic Lighthouse node)
# ------------------------------------------------------------------------------
run_local() {
    echo "============================================================"
    echo "🇨🇳 ARF China Leg Domestic Runner (Lighthouse: $(hostname))"
    echo "📅 Snapshot date: ${AS_OF}"
    echo "⏰ Started at:    $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "============================================================"

    # Load GCS HMAC credentials if present in config files
    if [[ -z "${GCS_HMAC_KEY:-}" ]]; then
        if [[ -f "/etc/arf/gcs_hmac.env" ]]; then
            # shellcheck disable=SC1091
            source "/etc/arf/gcs_hmac.env"
        elif [[ -f "${HOME}/.arf/gcs_hmac.env" ]]; then
            # shellcheck disable=SC1091
            source "${HOME}/.arf/gcs_hmac.env"
        fi
    fi

    # Set storage environment
    export OUTPUT_TARGET="gcs"
    export GCS_BUCKET="${GCS_BUCKET:-arf-data-ai-rf}"
    export GCS_DB_OBJECT="${GCS_DB_OBJECT:-arf.db}"
    export TRIGGER_SOURCE="lighthouse"

    # Select Python 3.11 virtual environment
    VENV_DIR="${REMOTE_DIR}/.venv"
    if [[ ! -d "${VENV_DIR}" ]]; then
        echo "Creating Python 3.11 virtual environment in ${VENV_DIR}..."
        python3.11 -m venv "${VENV_DIR}"
        "${VENV_DIR}/bin/pip" install --upgrade pip
        "${VENV_DIR}/bin/pip" install -e "${REMOTE_DIR}[cloud]"
    fi

    PYTHON="${VENV_DIR}/bin/python"

    cd "${REMOTE_DIR}"
    echo "Executing China leg pipeline..."
    "${PYTHON}" -m arf.run --leg China --as-of "${AS_OF}"

    echo "✅ China leg ingestion completed successfully."
}

# ------------------------------------------------------------------------------
# REMOTE RUNNER (Executed from developer workstation / CI)
# ------------------------------------------------------------------------------
run_remote() {
    echo "============================================================"
    echo "🚀 Triggering ARF China Leg Sync on ${SSH_HOST}..."
    echo "📅 Snapshot date: ${AS_OF}"
    echo "============================================================"

    # Verify SSH reachability
    if ! ssh -q -o ConnectTimeout=5 "${SSH_HOST}" true; then
        echo "❌ Error: Cannot connect to ${SSH_HOST}. Check ~/.ssh/config or network." >&2
        exit 1
    fi

    echo "📦 Syncing repository to ${SSH_HOST}:${REMOTE_DIR}..."
    ssh "${SSH_HOST}" "mkdir -p ${REMOTE_DIR} ${REMOTE_DIR}/data ${REMOTE_DIR}/reports ~/.arf"

    rsync -avz --delete \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.pytest_cache' \
        --exclude '.ruff_cache' \
        --exclude 'data/*.db*' \
        ./ "${SSH_HOST}:${REMOTE_DIR}/"

    # Propagate local HMAC credentials to ~/.arf/gcs_hmac.env if present.
    # Streamed over stdin (never in ssh's argv, which local users can read via ps).
    if [[ -n "${GCS_HMAC_KEY:-}" && -n "${GCS_HMAC_SECRET:-}" ]]; then
        printf 'export GCS_HMAC_KEY=%q\nexport GCS_HMAC_SECRET=%q\n' \
            "${GCS_HMAC_KEY}" "${GCS_HMAC_SECRET}" \
            | ssh "${SSH_HOST}" "umask 077; cat > ~/.arf/gcs_hmac.env"
    fi

    echo "⚡ Executing remote runner on Lighthouse..."
    ssh -t "${SSH_HOST}" "bash ${REMOTE_DIR}/scripts/sync_china_lighthouse.sh --local --as-of ${AS_OF}"

    echo "🎉 Lighthouse sync complete for ${AS_OF}."
}

if [[ "${RUN_MODE}" == "local" ]]; then
    run_local
else
    run_remote
fi
