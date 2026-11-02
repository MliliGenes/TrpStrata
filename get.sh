#!/usr/bin/env bash
# Install this trpStrata checkout, then open it.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
bash ./install.sh
(setsid "$HOME/.local/share/trpstrata/trpstrata" >/dev/null 2>&1 &)
echo "Opening trpStrata. Next time, find it in your apps or run: trpstrata"
