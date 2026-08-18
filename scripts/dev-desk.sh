#!/usr/bin/env bash
# Start the full local Aether Desk backend stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Missing .venv — create it first, then re-run."
  exit 1
fi

export PYTHONPATH="packages/shared/src:services/api_gateway/src:services/news_intelligence/src:services/risk/src:services/execution/src:services/llm_reasoning/src:services/portfolio/src:services/prediction/src:services/market_data/src:services/company_announcements/src:services/macro/src:services/geopolitical/src:services/sentiment/src:services/learning/src:services/backtesting/src:services/knowledge_graph/src"
PY="$ROOT/.venv/bin/python"
LOG_DIR="/tmp/aether-logs"
mkdir -p "$LOG_DIR"

"$PY" - "$ROOT" "$PY" "$LOG_DIR" <<'PY'
import os, sys, subprocess, time, urllib.request, socket

root, py, log_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.chdir(root)

services = [
    ("api", "api_gateway.main:app", 8000),
    ("portfolio", "portfolio.api.main:app", 8008),
    ("market", "market_data.api.main:app", 8002),
    ("news", "news_intelligence.api.main:app", 8001),
    ("announcements", "company_announcements.api.main:app", 8003),
]

def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0

for name, module, port in services:
    if port_open(port):
        print(f"· {name} already on :{port}")
        continue
    log = open(f"{log_dir}/{name}.log", "a", buffering=1)
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(port)],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=root,
        env=os.environ.copy(),
    )
    print(f"· started {name} on :{port} (pid {proc.pid})")

time.sleep(3.0)
for name, _, port in services:
    ok = False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            ok = r.status == 200
    except Exception:
        ok = False
    print(f"  {name}: {'ok' if ok else 'NOT READY'} :{port}")
PY

echo
echo "Desk:  http://localhost:3000"
echo "Login: admin@local.dev / ChangeMeAdmin123!"
echo "Dashboard (if needed): cd apps/dashboard && npm run dev"
echo "Logs:  $LOG_DIR"
