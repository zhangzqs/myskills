#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "$*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "缺少依赖: $cmd"
}

usage() {
  cat <<'EOF'
用法:
  fetch-starred.sh [username] [--limit N]

说明:
  - 不传 username 时，抓取当前已登录账号的 stars
  - 传 username 时，抓取该账号的公开 stars
EOF
}

main() {
  require_cmd gh
  require_cmd jq

  local username=""
  local limit=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --limit)
        shift
        [[ $# -gt 0 ]] || die "--limit 需要一个整数参数"
        limit="$1"
        ;;
      *)
        if [[ -z "$username" ]]; then
          username="$1"
        else
          die "未知参数: $1"
        fi
        ;;
    esac
    shift
  done

  [[ "$limit" =~ ^[0-9]+$ ]] || die "--limit 必须是非负整数"

  gh auth status -h github.com >/dev/null 2>&1 || die "GitHub 认证失败，请先执行: gh auth login -h github.com"

  local endpoint=""
  local actual_user=""

  if [[ -n "$username" ]]; then
    endpoint="users/$username/starred?per_page=100"
    actual_user="$username"
  else
    endpoint="user/starred?per_page=100"
    actual_user="$(gh api user --jq '.login')"
  fi

  gh api --paginate -H "Accept: application/vnd.github+json" "$endpoint" \
    | jq -s --arg username "$actual_user" --argjson limit "$limit" '
        (
          add
          | map({
              repo: .full_name,
              name: .name,
              owner: .owner.login,
              description: (.description // ""),
              language: (.language // ""),
              topics: (.topics // []),
              html_url: .html_url,
              visibility: (.visibility // "public"),
              archived: .archived,
              fork: .fork
            })
          | if $limit > 0 then .[:$limit] else . end
        ) as $repos
        | {
            targetAccount: $username,
            count: ($repos | length),
            repos: $repos
          }
      '
}

main "$@"
