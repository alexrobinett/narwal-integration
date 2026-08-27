#!/usr/bin/env bash
# Deploy custom_components/narwal to Home Assistant and restart core.
# Usage: HA_HOST=homeassistant.local scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
HA_HOST="${HA_HOST:-homeassistant.local}"
.venv/bin/pytest -q
rsync -avz --delete --exclude '__pycache__' custom_components/narwal/ "$HA_HOST:/config/custom_components/narwal/"
ssh "$HA_HOST" 'ha core restart'
echo "Deployed $(grep '"version"' custom_components/narwal/manifest.json) to $HA_HOST"
