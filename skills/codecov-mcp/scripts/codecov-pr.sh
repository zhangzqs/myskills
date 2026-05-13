#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

usage() {
  cat <<'EOF'
用法:
  codecov-pr.sh <PR号> [--owner OWNER] [--repo REPO] [--json]

说明:
  获取 PR 的覆盖率影响，包括 base/head/patch 覆盖率。
  owner/repo 默认从 git remote 自动检测。

示例:
  codecov-pr.sh 3253
  codecov-pr.sh 3253 --owner qbox --repo las
  codecov-pr.sh 3253 --json
EOF
}

main() {
  require_cmd npx
  require_cmd jq
  check_token

  local pr_number=""
  local json_output=false
  local -a passthrough=()

  for arg in "$@"; do
    case "$arg" in
      -h|--help) usage; exit 0 ;;
      --json) json_output=true ;;
      *) passthrough+=("$arg") ;;
    esac
  done

  # 提取 PR 号（第一个非选项参数）
  local -a owner_repo_args=()
  for arg in "${passthrough[@]}"; do
    if [[ -z "$pr_number" && "$arg" =~ ^[0-9]+$ ]]; then
      pr_number="$arg"
    else
      owner_repo_args+=("$arg")
    fi
  done

  [[ -n "$pr_number" ]] || die "请指定 PR 号，例如: codecov-pr.sh 3253"

  parse_owner_repo "${owner_repo_args[@]}"

  local result
  result=$(call_codecov get_pull_request_coverage "pull_number:$pr_number")

  if [[ "$json_output" == true ]]; then
    echo "$result" | jq .
  else
    echo "$result" | jq -r '
      "PR #\(.pullid): \(.title)",
      "",
      "Base 覆盖率: \(.base_totals.coverage)%",
      "Head 覆盖率: \(.head_totals.coverage)%",
      "Patch 覆盖率: \(.patch_totals.coverage)%",
      "",
      "Base 文件数: \(.base_totals.files)",
      "Head 文件数: \(.head_totals.files)",
      "Patch 文件数: \(.patch_totals.files)",
      "Patch 总行数: \(.patch_totals.lines)",
      "Patch 覆盖行: \(.patch_totals.hits)",
      "Patch 未覆盖: \(.patch_totals.misses)"
    '
  fi
}

main "$@"
