#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1) Python venv
if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
python -m pip install --upgrade pip

# 2) Per-repo requirements
install_req () {
  local dir="$1"
  if [[ -f "$dir/requirements.txt" ]]; then
    echo "Installing deps for $dir"
    pip install -r "$dir/requirements.txt"
  else
    echo "No requirements.txt in $dir (skipped)"
  fi
}

install_req "$ROOT/repos/at-gateway"
install_req "$ROOT/repos/at-agent-mcp"
install_req "$ROOT/repos/at-exec-sim"

echo "Done. venv active at $ROOT/.venv"
echo "Run services in separate terminals:"
echo "  uvicorn at_gateway.app:app --port 8081 --reload"
echo "  python -m at_agent_mcp.server 8082"
echo "  python -m at_exec_sim.app 8083"
