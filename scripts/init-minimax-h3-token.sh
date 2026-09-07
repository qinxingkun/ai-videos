#!/usr/bin/env bash
# Create or reuse .secrets/minimax_h3_api_token without starting SGLang.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/minimax-h3-auth.sh"

echo "Token file: ${MINIMAX_H3_API_TOKEN_FILE}"
echo "Restart ComfyUI / H3 Studio to send Authorization: Bearer."
echo "Restart MiniMax-H3 (FL2VA / Ref2VA) to enforce SGLang --api-key."
