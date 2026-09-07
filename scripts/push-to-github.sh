#!/usr/bin/env bash
# 推送到 GitHub：https://github.com/qinxingkun/ai-videos
# 用法：
#   export GH_TOKEN=ghp_xxxx   # PAT，需 repo 权限
#   ./scripts/push-to-github.sh
#   ./scripts/push-to-github.sh main
#
# 网络不稳时可：
#   RETRIES=5 ./scripts/push-to-github.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GITHUB_HTTPS="https://github.com/qinxingkun/ai-videos.git"
GITHUB_SSH="git@github.com:qinxingkun/ai-videos.git"
BRANCH="${1:-$(git branch --show-current)}"
GIT_SSH="${GIT_SSH:-0}"
RETRIES="${RETRIES:-5}"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo ">> $*"; }

[[ -n "$BRANCH" ]] || die "请指定分支名"

git remote get-url origin >/dev/null 2>&1 || git remote add origin "$GITHUB_HTTPS"
if [[ "$GIT_SSH" == "1" ]]; then
  git remote set-url origin "$GITHUB_SSH"
  info "origin (SSH) = $GITHUB_SSH"
else
  git remote set-url origin "$GITHUB_HTTPS"
  info "origin = $GITHUB_HTTPS"
fi

if ! git remote get-url gitlab >/dev/null 2>&1; then
  git remote add gitlab https://innovation-gitlab.hikvision.com.cn/HiStor/preresearch/ai-video.git || true
fi

info "本地: $(git rev-parse --short HEAD) on $BRANCH"
git status -sb | head -5
echo

if [[ -n "$(git status --porcelain)" ]]; then
  echo "WARN: 有未提交改动，本次只推送已有 commit。" >&2
fi

# 缓解 HTTP 408 / unexpected disconnect：加大缓冲、放宽低速超时、HTTP/1.1
GIT_HTTP_CFG=(
  -c http.version=HTTP/1.1
  -c http.postBuffer=524288000
  -c http.lowSpeedLimit=0
  -c http.lowSpeedTime=999999
  -c http.followRedirects=true
)

do_push() {
  if [[ "$GIT_SSH" == "1" ]]; then
    git "${GIT_HTTP_CFG[@]}" push -u origin "$BRANCH"
    return
  fi

  TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  if [[ -z "$TOKEN" ]]; then
    info "推送 $BRANCH -> origin（Password 处填 PAT）"
    GIT_TERMINAL_PROMPT=1 git "${GIT_HTTP_CFG[@]}" push -u origin "$BRANCH"
    return
  fi

  info "使用 token 认证推送（不把 token 写进进程参数）"
  # 通过临时 askpass，避免 https://token@... 出现在 ps 里
  ASKPASS="$(mktemp)"
  cleanup() { rm -f "$ASKPASS"; }
  trap cleanup EXIT
  cat >"$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) echo "x-access-token" ;;
  *) echo "$GH_TOKEN_FOR_ASKPASS" ;;
esac
EOF
  chmod 700 "$ASKPASS"
  export GH_TOKEN_FOR_ASKPASS="$TOKEN"
  export GIT_ASKPASS="$ASKPASS"
  export SSH_ASKPASS="$ASKPASS"
  export GIT_TERMINAL_PROMPT=0
  git "${GIT_HTTP_CFG[@]}" push -u origin "$BRANCH"
}

info "检查远端是否已有本分支"
if out="$(GIT_ASKPASS=true GIT_TERMINAL_PROMPT=0 git "${GIT_HTTP_CFG[@]}" ls-remote origin "refs/heads/${BRANCH}" 2>/dev/null)"; then
  remote_sha="$(awk '{print $1}' <<<"$out")"
  local_sha="$(git rev-parse "$BRANCH")"
  if [[ -n "$remote_sha" && "$remote_sha" == "$local_sha" ]]; then
    info "远端已是最新 ($local_sha)，无需推送"
    exit 0
  fi
  if [[ -n "$remote_sha" ]]; then
    info "远端 ${BRANCH}=${remote_sha:0:7}，本地=${local_sha:0:7}"
  else
    info "远端尚无 ${BRANCH}（首次推送）"
  fi
fi

attempt=1
while true; do
  info "推送尝试 ${attempt}/${RETRIES}"
  if do_push; then
    info "推送成功 → https://github.com/qinxingkun/ai-videos"
    echo "内网机器同步 GitLab："
    echo "  git clone https://github.com/qinxingkun/ai-videos.git && cd ai-videos"
    echo "  git remote add gitlab https://innovation-gitlab.hikvision.com.cn/HiStor/preresearch/ai-video.git"
    echo "  git push -u gitlab main"
    exit 0
  fi
  ec=$?
  if (( attempt >= RETRIES )); then
    die "推送失败（exit=$ec）。可再试：RETRIES=8 ./scripts/push-to-github.sh  或换网络/代理后再推"
  fi
  sleep_s=$(( attempt * 5 ))
  echo "WARN: 失败 (exit=$ec)，${sleep_s}s 后重试…" >&2
  sleep "$sleep_s"
  attempt=$((attempt + 1))
done
