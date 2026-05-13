---
name: codecov-mcp
description: "Use when you need to check code coverage data from Codecov — including repo coverage, PR coverage impact, commit coverage, file-level coverage, and coverage comparisons. Calls codecov-mcp via mcporter CLI."
---

# Codecov MCP

通过 mcporter 调用 codecov-mcp 服务器，查询 Codecov 代码覆盖率数据。无需打开 Codecov 网页 UI，直接在终端中获取覆盖率报告。

## When To Use

- 查看当前仓库的整体覆盖率
- 分析某个 PR 的覆盖率影响（base/head/patch 覆盖率、受影响文件）
- 查看某个 commit 的覆盖率详情
- 查看某文件中哪些行未被测试覆盖
- 比较两个 commit 或两个分支之间的覆盖率差异

## Requirements

- Node.js >= 18（mcporter 和 codecov-mcp 均通过 npx 运行）
- `CODECOV_TOKEN` 环境变量已设置（Codecov API Access Token，非 Upload Token）
  - 获取方式：https://app.codecov.io/account -> API Access Token

## Hard Boundaries

- 永远不在输出中暴露 `CODECOV_TOKEN` 的值
- 不硬编码 owner/repo，优先使用 git remote 自动检测或让用户指定
- 只读操作，不修改 Codecov 上的任何数据
- 如果 token 未设置或无效，立即停止并给出明确提示，不猜测

## First-Time Setup

用户首次使用时，需要设置 CODECOV_TOKEN：

```bash
export CODECOV_TOKEN="your-api-access-token-here"
```

提示用户将此行加入 `~/.bashrc`、`~/.zshrc` 或项目级 `.env` 文件以持久化。

## Command Syntax

### 脚本调用（推荐）

使用 `scripts/` 目录下的封装脚本，自动处理 token、owner/repo 检测和输出格式化：

```bash
# 获取仓库覆盖率
./scripts/codecov-repo.sh [--owner OWNER] [--repo REPO] [--branch BRANCH] [--json]

# 获取 PR 覆盖率
./scripts/codecov-pr.sh <PR号> [--owner OWNER] [--repo REPO] [--json]

# 获取 commit 覆盖率
./scripts/codecov-commit.sh [SHA] [--owner OWNER] [--repo REPO] [--json]

# 比较两个 ref
./scripts/codecov-compare.sh <base> <head> [--owner OWNER] [--repo REPO] [--json]

# 获取文件逐行覆盖率
./scripts/codecov-file.sh <文件路径> [--owner OWNER] [--repo REPO] [--ref REF] [--json]
```

脚本自动从 `git remote` 检测 owner/repo，支持 `--json` 输出原始 JSON。

### 原始 mcporter 调用

如需更灵活的控制，可直接使用 mcporter：

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov <tool_name> owner:<owner> repo:<repo> [params...]
```

- `--stdio "npx -y @egulatee/mcp-codecov"` 指定本地 MCP 服务器命令
- `--env CODECOV_TOKEN=...` 传递认证 token
- `--name codecov` 设置服务器显示名称
- 参数以 `key:value` 形式传入（冒号分隔，无等号）
- 输出格式可加 `--output json` 获取结构化 JSON，便于后续处理

## Tool Reference

实际可用的 5 个工具：

### get_repo_coverage

获取仓库整体覆盖率统计，可指定分支。

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov get_repo_coverage owner:<owner> repo:<repo> [branch:<branch>]
```

返回字段：文件数、总行数、覆盖行数、未覆盖行数、覆盖率百分比等。

### get_commit_coverage

获取某个 commit 的覆盖率详情，包括文件级别变化。

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov get_commit_coverage owner:<owner> repo:<repo> commit_sha:<full_sha>
```

注意：`commit_sha` 必须是完整的 40 位 SHA，不支持 `main`、`HEAD`、`latest` 等别名。

### get_pull_request_coverage

获取 PR 的覆盖率影响，包括 base/head/patch 覆盖率。

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov get_pull_request_coverage owner:<owner> repo:<repo> pull_number:<number>
```

### get_file_coverage

获取单个文件的逐行覆盖率数据。

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov get_file_coverage owner:<owner> repo:<repo> file_path:<path> [ref:<branch_or_sha>]
```

注意：部分仓库可能返回 404，取决于 Codecov 后端数据存储方式。

### compare_coverage

比较两个 git 引用（分支、commit、tag）之间的覆盖率差异。

```bash
npx mcporter call --stdio "npx -y @egulatee/mcp-codecov" --env CODECOV_TOKEN="$CODECOV_TOKEN" --name codecov compare_coverage owner:<owner> repo:<repo> base:<ref> head:<ref>
```

返回详细的 base/head/patch 覆盖率对比，以及逐文件变化。

## Parameter Resolution

`owner`、`repo` 参数按以下优先级解析：

1. 工具调用时直接传入的参数
2. Git remote 自动检测（`git remote get-url origin`）
3. 若均无法解析，报错提示用户设置

如果当前目录是目标仓库的 git 本地克隆，大多数情况下无需传 owner/repo。

## Environment Variables

| 变量                   | 必需 | 默认值                   | 说明                       |
| ---------------------- | ---- | ------------------------ | -------------------------- |
| `CODECOV_TOKEN`        | 是   | —                        | Codecov API Access Token   |
| `CODECOV_API_BASE_URL` | 否   | `https://api.codecov.io` | 自托管 Codecov 的 API 地址 |

## Troubleshooting

| 错误                   | 解决方案                                                                          |
| ---------------------- | --------------------------------------------------------------------------------- |
| `401 Unauthorized`     | Token 无效或过期，到 https://app.codecov.io/account 重新生成                      |
| `404 Not Found`        | 检查 owner/repo 名称，确认该仓库已在 Codecov 上有覆盖率数据；或该工具不支持该仓库 |
| `commit_sha not found` | 使用完整的 40 位 commit SHA，不支持别名                                           |

## Usage Examples

### 用户说："看看这个仓库的覆盖率"

```bash
./scripts/codecov-repo.sh
```

### 用户说："PR #3253 的覆盖率怎么样"

```bash
./scripts/codecov-pr.sh 3253
```

### 用户说："比较 main 和 develop 的覆盖率"

```bash
./scripts/codecov-compare.sh main develop
```

### 用户说："看看这个 commit 的覆盖率"

```bash
./scripts/codecov-commit.sh e981d08260b92846ba2a6dc026c3863478f17696
```

## Output Formatting

- 默认以人类可读的文本形式展示
- 如果需要程序化处理，加 `--output json`
- 表格数据优先用 markdown 表格展示
- 百分比保留两位小数
