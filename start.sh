#!/usr/bin/env bash
set -euo pipefail

# Find the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Support both .venv and venv directories
if [[ -d "venv" ]]; then
  VENV_DIR="venv"
elif [[ -d ".venv" ]]; then
  VENV_DIR=".venv"
else
  VENV_DIR="venv"
fi

SERVER_PID_FILE=".openleaf_server.pid"
UI_PID_FILE=".openleaf_ui.pid"
LOG_DIR="logs"
SERVER_LOG="${LOG_DIR}/server.log"
UI_LOG="${LOG_DIR}/ui.log"
DEFAULT_CONFIG="configs/leaf_2013_24kwh.yaml"

usage() {
  echo "Usage: $0 [server|ui|all] [config_path]"
  echo ""
  echo "Commands:"
  echo "  server  - Start the API server (default)"
  echo "  ui      - Start the Kivy UI"
  echo "  all     - Start both server and UI"
  echo ""
  echo "Config defaults to: ${DEFAULT_CONFIG}"
}

ensure_venv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    echo "Creating virtual environment in ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
  mkdir -p "${LOG_DIR}"
  export KIVY_LOG_DIR="${LOG_DIR}"
  export KIVY_LOG_NAME="kivy_ui.log"
}

install_deps() {
  local extra="${1:-}"
  echo "Checking dependencies..."
  if [[ -n "${extra}" ]]; then
    pip install -q -e ".[${extra}]"
  else
    pip install -q -e .
  fi
}

start_server() {
  if [[ -f "${SERVER_PID_FILE}" ]] && kill -0 "$(cat "${SERVER_PID_FILE}")" 2>/dev/null; then
    echo "Server already running with PID $(cat "${SERVER_PID_FILE}")"
    return
  fi

  ensure_venv
  install_deps

  echo "Starting OpenLeaf server with config: ${CONFIG_PATH}"
  nohup python -m openleaf.server --config "${CONFIG_PATH}" >"${SERVER_LOG}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${SERVER_PID_FILE}"
  echo "OpenLeaf server started (PID ${pid})"
  echo "  Logs: ${SERVER_LOG}"
  echo "  API:  http://localhost:8000/state"
}

start_ui() {
  if [[ -f "${UI_PID_FILE}" ]] && kill -0 "$(cat "${UI_PID_FILE}")" 2>/dev/null; then
    echo "UI already running with PID $(cat "${UI_PID_FILE}")"
    return
  fi

  ensure_venv
  install_deps "ui"

  echo "Starting OpenLeaf Kivy UI..."
  nohup python -m openleaf.ui.kivy.main >"${UI_LOG}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${UI_PID_FILE}"
  echo "OpenLeaf UI started (PID ${pid})"
  echo "  Logs: ${UI_LOG}"
}

# Parse arguments
TARGET=${1:-server}
CONFIG_PATH=${2:-${OPENLEAF_CONFIG:-${DEFAULT_CONFIG}}}

case "${TARGET}" in
  server)
    start_server
    ;;
  ui)
    start_ui
    ;;
  all)
    start_server
    sleep 2  # Give server time to start
    start_ui
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: ${TARGET}"
    usage
    exit 1
    ;;
esac
