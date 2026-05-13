#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

usage() {
  cat <<'EOF'
用法:
  codecov-commit.sh [SHA] [--owner OWNER] [--repo REPO] [--json]

说明:
  获取某个 commit 的覆盖率详情。
  不传 SHA 时使用当前 HEAD。
  owner/repo 默认从 git remote 自动检测。

示例:
  codecov-commit.sh
  codecov-commit.sh e981d08260b92846ba2a6dc026c3863478f17696
  codecov-commit.sh --json
EOF
}

main() {
  require_cmd npx
  require_cmd jq
  require_cmd git
  check_token

  local sha=""
  local json_output=false
  local -a owner_repo_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      --json) json_output=true; shift ;;
      --owner|--repo) owner_repo_args+=("$1"); shift; owner_repo_args+=("${1:?${owner_repo_args[-1]} 需要一个参数}"); shift ;;
      *)
        if [[ -z "$sha" ]]; then
          sha="$1"
        else
          die "未知参数: $1"
        fi
        shift
        ;;
    esac
  done

  parse_owner_repo "${owner_repo_args[@]}"

  # 默认使用当前 HEAD
  if [[ -z "$sha" ]]; then
    sha=$(git rev-parse HEAD 2>/dev/null || die "无法获取当前 HEAD")
  fi

  # 验证 SHA 格式（至少 7 位 hex）
  [[ "$sha" =~ ^[0-9a-f]{7,40}$ ]] || die "无效的 commit SHA: $sha"

  # 先写入临时文件再用 jq 处理（避免管道截断大 JSON）
  local tmpfile
  tmpfile=$(mktemp)
  trap "rm -f '$tmpfile'" EXIT

  npx mcporter call \
    --stdio "npx -y @egulatee/mcp-codecov" \
    --env CODECOV_TOKEN="$CODECOV_TOKEN" \
    --name codecov \
    get_commit_coverage "owner:$OWNER" "repo:$REPO" "commit_sha:$sha" \
    > "$tmpfile" 2>&1

  if [[ "$json_output" == true ]]; then
    jq '{commitid, message, branch, author, timestamp, ci_passed, totals, state}' "$tmpfile"
  else
    jq -r '
      "Commit: \(.commitid)",
      "消息: \(.message | split("\n")[0])",
      "分支: \(.branch)",
      "作者: \(.author.name)",
      "时间: \(.timestamp)",
      "CI: \(if .ci_passed then "通过" else "未通过" end)",
      "",
      "覆盖率: \(.totals.coverage)%",
      "文件数: \(.totals.files)",
      "总行数: \(.totals.lines)",
      "覆盖行: \(.totals.hits)",
      "未覆盖: \(.totals.misses)",
      "部分覆盖: \(.totals.partials)"
    ' "$tmpfile"
  fi
}

main "$@"
