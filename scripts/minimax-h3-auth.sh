# Shared MiniMax-H3 / SGLang API token loading.
# Source this file; it sets MINIMAX_H3_API_TOKEN and SGLANG_AUTH_ARGS.
# Do not print the token.

_H3_AUTH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_H3_AUTH_ROOT="$(cd "${_H3_AUTH_DIR}/.." && pwd)"
MINIMAX_H3_API_TOKEN_FILE="${MINIMAX_H3_API_TOKEN_FILE:-${_H3_AUTH_ROOT}/.secrets/minimax_h3_api_token}"
MINIMAX_H3_REQUIRE_AUTH="${MINIMAX_H3_REQUIRE_AUTH:-1}"

_h3_read_token() {
  if [[ -n "${MINIMAX_H3_API_TOKEN:-}" ]]; then
    MINIMAX_H3_API_TOKEN="$(printf '%s' "${MINIMAX_H3_API_TOKEN}" | tr -d '[:space:]')"
    return
  fi
  if [[ -f "${MINIMAX_H3_API_TOKEN_FILE}" ]]; then
    MINIMAX_H3_API_TOKEN="$(tr -d '[:space:]' < "${MINIMAX_H3_API_TOKEN_FILE}")"
  fi
}

_h3_ensure_token() {
  _h3_read_token
  if [[ -n "${MINIMAX_H3_API_TOKEN:-}" ]]; then
    return
  fi
  if [[ "${MINIMAX_H3_REQUIRE_AUTH}" == "0" ]]; then
    return
  fi
  mkdir -p "$(dirname "${MINIMAX_H3_API_TOKEN_FILE}")"
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "${MINIMAX_H3_API_TOKEN_FILE}"
  chmod 600 "${MINIMAX_H3_API_TOKEN_FILE}"
  MINIMAX_H3_API_TOKEN="$(tr -d '[:space:]' < "${MINIMAX_H3_API_TOKEN_FILE}")"
  echo "Generated MiniMax-H3 API token file: ${MINIMAX_H3_API_TOKEN_FILE}"
}

_h3_ensure_token
SGLANG_AUTH_ARGS=()
if [[ -n "${MINIMAX_H3_API_TOKEN:-}" ]]; then
  SGLANG_AUTH_ARGS+=(--api-key "${MINIMAX_H3_API_TOKEN}")
  echo "Auth: SGLang --api-key enabled"
else
  echo "Auth: disabled (MINIMAX_H3_REQUIRE_AUTH=0 and no token)"
fi
