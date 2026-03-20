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

require_auth() {
  gh auth status -h github.com >/dev/null 2>&1 || die "GitHub 认证失败，请先执行: gh auth login -h github.com"
}

graphql() {
  gh api graphql "$@"
}

usage() {
  cat <<'EOF'
用法:
  apply-lists.sh --plan <plan.json> [--execute] [--public-lists]

说明:
  - 默认 dry-run，只输出将要创建和更新的内容
  - 加上 --execute 才会真正写入 GitHub Lists
  - 新建 Lists 默认 private，加上 --public-lists 改为 public
EOF
}

query_lists_with_items() {
  graphql -f query='
    query {
      viewer {
        lists(first: 100) {
          nodes {
            id
            name
            slug
            isPrivate
            items(first: 100) {
              nodes {
                ... on Repository {
                  nameWithOwner
                }
              }
            }
          }
        }
      }
    }
  '
}

resolve_list_id_from_response() {
  local list_name="$1"
  local response="$2"
  local matches=()

  mapfile -t matches < <(jq -r --arg list_name "$list_name" '
    .data.viewer.lists.nodes[]? | select(.name == $list_name) | .id
  ' <<<"$response")

  if [[ "${#matches[@]}" -eq 0 ]]; then
    return 1
  fi

  if [[ "${#matches[@]}" -gt 1 ]]; then
    die "List 名称存在歧义: $list_name"
  fi

  printf '%s\n' "${matches[0]}"
}

get_repo_list_ids_from_response() {
  local repo="$1"
  local response="$2"

  jq -r --arg repo "$repo" '
    .data.viewer.lists.nodes[]?
    | select(any(.items.nodes[]?; .nameWithOwner == $repo))
    | .id
  ' <<<"$response"
}

resolve_repo_id() {
  local repo="$1"
  local owner="${repo%%/*}"
  local name="${repo#*/}"
  local response

  response="$(graphql \
    -f query='
      query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          id
        }
      }
    ' \
    -F owner="$owner" \
    -F name="$name"
  )"

  jq -r '.data.repository.id // empty' <<<"$response"
}

create_list() {
  local name="$1"
  local is_private="$2"

  graphql \
    -f query='
      mutation($name: String!, $isPrivate: Boolean!) {
        createUserList(input: {
          name: $name
          isPrivate: $isPrivate
        }) {
          list {
            id
            name
          }
        }
      }
    ' \
    -F name="$name" \
    -F isPrivate="$is_private" >/dev/null
}

update_repo_lists() {
  local repo_id="$1"
  shift

  local args=(
    -f query='
      mutation($itemId: ID!, $listIds: [ID!]!) {
        updateUserListsForItem(input: {
          itemId: $itemId
          listIds: $listIds
        }) {
          item {
            ... on Repository {
              nameWithOwner
            }
          }
          lists {
            name
          }
        }
      }
    '
    -F "itemId=$repo_id"
  )

  local list_id
  for list_id in "$@"; do
    args+=(-F "listIds[]=$list_id")
  done

  graphql "${args[@]}"
}

validate_plan() {
  local plan="$1"

  jq -e '
    .repos
    and (.repos | type == "array")
    and (.repos | length > 0)
    and all(.repos[]; (.repo | type == "string") and (.repo | test("^[^/]+/[^/]+$")))
    and all(.repos[]; (.lists | type == "array") and (.lists | length > 0))
  ' "$plan" >/dev/null || die "计划文件格式错误，需包含 repos[].repo 和 repos[].lists[]"
}

main() {
  require_cmd gh
  require_cmd jq

  local plan=""
  local execute=0
  local is_private="true"
  local visibility_overridden=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --plan)
        shift
        [[ $# -gt 0 ]] || die "--plan 需要一个文件路径"
        plan="$1"
        ;;
      --execute)
        execute=1
        ;;
      --public-lists)
        is_private="false"
        visibility_overridden=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "未知参数: $1"
        ;;
    esac
    shift
  done

  [[ -n "$plan" ]] || die "必须提供 --plan"
  [[ -f "$plan" ]] || die "计划文件不存在: $plan"

  validate_plan "$plan"
  require_auth

  if [[ "$visibility_overridden" -eq 0 ]] && [[ "$(jq -r '.listVisibility // "private"' "$plan")" == "public" ]]; then
    is_private="false"
  fi

  local lists_response
  lists_response="$(query_lists_with_items)"

  local list_name
  while IFS= read -r list_name; do
    [[ -n "$list_name" ]] || continue
    if resolve_list_id_from_response "$list_name" "$lists_response" >/dev/null 2>&1; then
      continue
    fi

    if [[ "$execute" -eq 1 ]]; then
      create_list "$list_name" "$is_private"
      echo "CREATED_LIST	$list_name"
      lists_response="$(query_lists_with_items)"
    else
      echo "DRY_RUN_CREATE_LIST	$list_name"
    fi
  done < <(jq -r '.repos[].lists[]' "$plan" | sort -u)

  local repo
  while IFS= read -r repo; do
    [[ -n "$repo" ]] || continue

    local target_names=()
    mapfile -t target_names < <(jq -r --arg repo "$repo" '
      .repos[] | select(.repo == $repo) | .lists[]
    ' "$plan" | awk '!seen[$0]++')

    local repo_id
    repo_id="$(resolve_repo_id "$repo")"
    if [[ -z "$repo_id" ]]; then
      echo "SKIP_REPO	$repo	未找到仓库" >&2
      continue
    fi

    if [[ "$execute" -eq 0 ]]; then
      echo "DRY_RUN_UPDATE	$repo	$(printf '%s\n' "${target_names[@]}" | paste -sd ',' -)"
      continue
    fi

    local current_list_ids=()
    mapfile -t current_list_ids < <(get_repo_list_ids_from_response "$repo" "$lists_response")

    local merged_ids=()
    local list_id
    local target_name
    declare -A seen=()

    for list_id in "${current_list_ids[@]}"; do
      [[ -n "$list_id" ]] || continue
      if [[ -z "${seen[$list_id]:-}" ]]; then
        seen["$list_id"]=1
        merged_ids+=("$list_id")
      fi
    done

    for target_name in "${target_names[@]}"; do
      list_id="$(resolve_list_id_from_response "$target_name" "$lists_response")"
      if [[ -z "${seen[$list_id]:-}" ]]; then
        seen["$list_id"]=1
        merged_ids+=("$list_id")
      fi
    done

    if [[ "$execute" -eq 1 ]]; then
      local response
      response="$(update_repo_lists "$repo_id" "${merged_ids[@]}")"
      local final_lists
      final_lists="$(jq -r '.data.updateUserListsForItem.lists | map(.name) | join(",")' <<<"$response")"
      echo "APPLIED	$repo	$final_lists"
    fi
  done < <(jq -r '.repos[].repo' "$plan" | awk '!seen[$0]++')
}

main "$@"
