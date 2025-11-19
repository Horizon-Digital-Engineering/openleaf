#!/usr/bin/env bash
set -euo pipefail

SERVER_PID_FILE=".openleaf_server.pid"
UI_PID_FILE=".openleaf_ui.pid"

usage() {
  echo "Usage: $0 [server|ui|all]" >&2
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
    echo "Stopped ${name} (PID ${pid})."
  else
    echo "No process found for PID ${pid}. Cleaning up ${pid_file}."
  fi
  rm -f "${pid_file}"
}

TARGET=${1:-server}
case "${TARGET}" in
  server)
    stop_component "${SERVER_PID_FILE}" "OpenLeaf server"
    ;;
  ui)
    stop_component "${UI_PID_FILE}" "OpenLeaf UI"
    ;;
  all)
    stop_component "${SERVER_PID_FILE}" "OpenLeaf server"
    stop_component "${UI_PID_FILE}" "OpenLeaf UI"
    ;;
  *)
    usage
    exit 1
    ;;
esac
