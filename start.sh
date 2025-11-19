#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"
SERVER_PID_FILE=".openleaf_server.pid"
UI_PID_FILE=".openleaf_ui.pid"
SERVER_LOG="openleaf_server.log"
UI_LOG="openleaf_ui.log"

usage() {
  echo "Usage: $0 [server|ui|all]" >&2
}

ensure_venv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
}

install_server_deps() {
  python -m pip install -e '.' >/dev/null
}

install_ui_deps() {
  python -m pip install -e '.[ui]' >/dev/null
}

start_server() {
  if [[ -f "${SERVER_PID_FILE}" ]] && kill -0 "$(cat "${SERVER_PID_FILE}")" 2>/dev/null; then
    echo "Server already running with PID $(cat "${SERVER_PID_FILE}")"
    return
  fi
  ensure_venv
  install_server_deps
  nohup python main.py >"${SERVER_LOG}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${SERVER_PID_FILE}"
  echo "OpenLeaf server started (PID ${pid}). Logs: ${SERVER_LOG}"
}

start_ui() {
  if [[ -f "${UI_PID_FILE}" ]] && kill -0 "$(cat "${UI_PID_FILE}")" 2>/dev/null; then
    echo "UI already running with PID $(cat "${UI_PID_FILE}")"
    return
  fi
  ensure_venv
  install_ui_deps
  nohup python -m openleaf.ui.kivy.main >"${UI_LOG}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${UI_PID_FILE}"
  echo "OpenLeaf Kivy UI started (PID ${pid}). Logs: ${UI_LOG}"
}

TARGET=${1:-server}
case "${TARGET}" in
  server)
    start_server
    ;;
  ui)
    start_ui
    ;;
  all)
    start_server
    start_ui
    ;;
  *)
    usage
    exit 1
    ;;
esac
