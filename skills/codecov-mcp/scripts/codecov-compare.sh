#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

usage() {
  cat <<'EOF'
用法:
  codecov-compare.sh <base> <head> [--owner OWNER] [--repo REPO] [--json]

说明:
  比较两个 git 引用（分支、commit、tag）之间的覆盖率差异。
  owner/repo 默认从 git remote 自动检测。

示例:
  codecov-compare.sh main develop
  codecov-compare.sh main HEAD --json
  codecov-compare.sh abc1234 def5678 --owner qbox --repo las
EOF
}

main() {
  require_cmd npx
  require_cmd jq
  check_token

  local base=""
  local head=""
  local json_output=false
  local -a owner_repo_args=()
  local -a refs=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      --json) json_output=true; shift ;;
      --owner|--repo) owner_repo_args+=("$1"); shift; owner_repo_args+=("${1:?${owner_repo_args[-1]} 需要一个参数}"); shift ;;
      *) refs+=("$1"); shift ;;
    esac
  done

  [[ ${#refs[@]} -ge 2 ]] || die "请指定 base 和 head，例如: codecov-compare.sh main develop"
  base="${refs[0]}"
  head="${refs[1]}"

  parse_owner_repo "${owner_repo_args[@]}"

  local result
  result=$(call_codecov compare_coverage "base:$base" "head:$head")

  if [[ "$json_output" == true ]]; then
    echo "$result" | jq .
  else
    echo "$result" | jq -r '
      "比较: \(.base_commit[:8]) -> \(.head_commit[:8])",
      "",
      "=== 总体覆盖率 ===",
      "Base: \(.totals.base.coverage)% (\(.totals.base.files) 文件, \(.totals.base.lines) 行)",
      "Head: \(.totals.head.coverage)% (\(.totals.head.files) 文件, \(.totals.head.lines) 行)",
      "Patch: \(.totals.patch.coverage)% (\(.totals.patch.files) 文件, \(.totals.patch.lines) 行)",
      "",
      "=== 变化文件 (\(.files | length) 个) ===",
      (.files[:20][] |
        "\(.name.head // .name.base): " +
        "base=" + ((.totals.base.coverage // 0) | tostring) + "%" +
        " head=" + ((.totals.head.coverage // 0) | tostring) + "%" +
        " patch=" + ((.totals.patch.coverage // 0) | tostring) + "%"
      ),
      if (.files | length) > 20 then "... 还有 \(.files | length - 20) 个文件" else "" end
    '
  fi
}

main "$@"
