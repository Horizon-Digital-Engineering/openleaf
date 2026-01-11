#!/usr/bin/env bash
set -euo pipefail

# Find the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

SERVER_PID_FILE=".openleaf_server.pid"
UI_PID_FILE=".openleaf_ui.pid"

usage() {
  echo "Usage: $0 [server|ui|all]"
  echo ""
  echo "Commands:"
  echo "  server  - Stop the API server"
  echo "  ui      - Stop the Kivy UI"
  echo "  all     - Stop both (default)"
}

stop_component() {
  local pid_file=$1
  local name=$2
  if [[ ! -f "${pid_file}" ]]; then
    echo "No running ${name} process found."
    return
  fi
  local pid
  pid=$(cat "${pid_file}")
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}"
    echo "Stopped ${name} (PID ${pid})"
  else
    echo "No process found for PID ${pid}. Cleaning up."
  fi
  rm -f "${pid_file}"
}

TARGET=${1:-all}

case "${TARGET}" in
  server)
    stop_component "${SERVER_PID_FILE}" "OpenLeaf server"
    ;;
  ui)
    stop_component "${UI_PID_FILE}" "OpenLeaf UI"
    ;;
  all)
    stop_component "${UI_PID_FILE}" "OpenLeaf UI"
    stop_component "${SERVER_PID_FILE}" "OpenLeaf server"
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
