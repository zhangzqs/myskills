#!/usr/bin/env bash
# codecov-mcp 公共辅助函数，由各脚本 source 引用

die() {
  echo "错误: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少依赖: $1"
}

check_token() {
  [[ -n "${CODECOV_TOKEN:-}" ]] || die "CODECOV_TOKEN 未设置。请执行: export CODECOV_TOKEN='your-token'"
}

# 从 git remote 自动检测 owner/repo，支持命令行覆盖
# 用法: parse_owner_repo "$@"  -> 设置 OWNER 和 REPO 变量，剩余参数放入 REMAINING_ARGS
parse_owner_repo() {
  OWNER=""
  REPO=""
  REMAINING_ARGS=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --owner)
        shift
        OWNER="${1:?--owner 需要一个参数}"
        ;;
      --repo)
        shift
        REPO="${1:?--repo 需要一个参数}"
        ;;
      *)
        REMAINING_ARGS+=("$1")
        ;;
    esac
    shift
  done

  if [[ -z "$OWNER" || -z "$REPO" ]]; then
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || true)
    if [[ -n "$remote_url" ]]; then
      [[ -z "$OWNER" ]] && OWNER=$(echo "$remote_url" | sed -E 's|.*github\.com[:/]([^/]+)/([^/.]+).*|\1|')
      [[ -z "$REPO" ]] && REPO=$(echo "$remote_url" | sed -E 's|.*github\.com[:/]([^/]+)/([^/.]+).*|\2|')
    fi
  fi

  [[ -n "$OWNER" ]] || die "无法检测 owner，请使用 --owner 指定"
  [[ -n "$REPO" ]] || die "无法检测 repo，请使用 --repo 指定"
}

# 调用 codecov MCP 工具，自动处理错误
# 用法: call_codecov <tool_name> [key:value ...]
# 输出: JSON 结果到 stdout
# 错误: 如果调用失败，输出错误信息到 stderr 并退出
call_codecov() {
  local tool="$1"
  shift
  local result
  result=$(npx mcporter call \
    --stdio "npx -y @egulatee/mcp-codecov" \
    --env CODECOV_TOKEN="$CODECOV_TOKEN" \
    --name codecov \
    "$tool" \
    "owner:$OWNER" "repo:$REPO" \
    "$@" 2>&1)

  # 检查是否返回错误
  if [[ "$result" == Error:* ]]; then
    die "${result#Error: }"
  fi

  echo "$result"
}
