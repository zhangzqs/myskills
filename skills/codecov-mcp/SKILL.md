---
name: codecov-mcp
description: "Use when you need to check code coverage data from Codecov — including repo coverage, PR coverage impact, coverage trends, flaky tests, uncovered lines, and coverage comparisons. Calls codecov-mcp via mcporter CLI."
---

# Codecov MCP

通过 mcporter 调用 codecov-mcp 服务器，查询 Codecov 代码覆盖率数据。无需打开 Codecov 网页 UI，直接在终端中获取覆盖率报告。

## When To Use

- 查看当前仓库的整体覆盖率
- 分析某个 PR 的覆盖率影响（patch %、受影响文件、行级 diff）
- 查找覆盖率最低的文件和目录
- 查看某文件中哪些行未被测试覆盖
- 追踪覆盖率趋势（上升/下降/持平）
- 发现 flaky tests（在默认分支上反复失败的测试）
- 校验 `codecov.yaml` 配置是否正确
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

使用 mcporter 的 ad-hoc stdio 模式直接调用，无需预先配置。格式为：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.<tool_name> <param>:<value> [<param>:<value> ...]
```

- `--stdio "npx -y codecov-mcp"` 指定本地 MCP 服务器命令
- mcporter 会自动继承当前 shell 的环境变量（包括 `CODECOV_TOKEN`）
- 参数以 `key:value` 形式传入（冒号分隔，无等号）
- 如果值包含空格，用单引号包裹
- 输出格式可加 `--output json` 获取结构化 JSON，便于后续处理

## Common Workflows

### Workflow 1: 快速了解仓库覆盖率全貌

这是最常用的入口。用 `get_coverage_summary` 一次调用获取：整体覆盖率、趋势方向、flag 分支覆盖率、开放 PR 数量。

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_summary owner:<owner> repo:<repo>
```

如果在目标仓库的 git 本地目录中运行，可省略 owner 和 repo（自动检测）：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_summary
```

### Workflow 2: PR 覆盖率审查

在 code review 时检查 PR 的覆盖率影响。`get_pr_coverage` 是复合工具，一次调用返回 PR 的 base/head/patch 覆盖率以及所有受影响文件。

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_pr_coverage owner:<owner> repo:<repo> pullNumber:<PR号>
```

示例：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_pr_coverage owner:myorg repo:myapp pullNumber:42
```

如果需要更详细的逐文件比较：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.compare_coverage owner:<owner> repo:<repo> pullNumber:<PR号>
```

### Workflow 3: 查找覆盖率最低的文件

用 `get_coverage_tree` 以目录树形式查看覆盖率，快速定位薄弱区域：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_tree owner:<owner> repo:<repo>
```

然后针对某个具体文件查看逐行覆盖：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_file_coverage owner:<owner> repo:<repo> path:src/auth.ts
```

### Workflow 4: 追踪覆盖率趋势

查看覆盖率随时间的变化：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_trend owner:<owner> repo:<repo>
```

可指定时间范围和间隔：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_trend owner:<owner> repo:<repo> interval:month start:2025-01-01 end:2025-06-01
```

### Workflow 5: 发现 Flaky Tests

找出在默认分支上反复失败的测试（flaky test 候选）：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.find_flaky_tests owner:<owner> repo:<repo>
```

### Workflow 6: 校验 codecov.yaml

提交前检查配置文件是否正确（此工具不需要认证）：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.validate_yaml owner:<owner> repo:<repo>
```

或指定配置文件内容：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.validate_yaml config:'<yaml内容>'
```

### Workflow 7: 比较两个 commit 的覆盖率

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.compare_coverage owner:<owner> repo:<repo> base:<commit_sha> head:<commit_sha>
```

### Workflow 8: 查看 PR 列表及覆盖率影响

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.list_pulls owner:<owner> repo:<repo> state:open
```

### Workflow 9: 按 Flag 查看覆盖率

适用于区分 unit/integration/e2e 等不同测试类型的覆盖率：

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.list_flags owner:<owner> repo:<repo>
```

```bash
npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_flag_coverage_trend owner:<owner> repo:<repo> flag:unit
```

## Tool Reference

### Composite Tools (优先使用)

| Tool                   | 用途                                          | 关键参数                      |
| ---------------------- | --------------------------------------------- | ----------------------------- |
| `get_coverage_summary` | 仓库覆盖率全貌（覆盖率+趋势+flags+PR数）      | `owner`, `repo`               |
| `get_pr_coverage`      | PR 覆盖率详情（base/head/patch + 受影响文件） | `owner`, `repo`, `pullNumber` |
| `find_flaky_tests`     | 发现 flaky test 候选                          | `owner`, `repo`               |
| `validate_yaml`        | 校验 codecov.yaml（无需认证）                 | `owner`, `repo` 或 `config`   |

### Coverage Tools

| Tool                  | 用途                   | 关键参数                                    |
| --------------------- | ---------------------- | ------------------------------------------- |
| `get_coverage_totals` | 某 commit 的覆盖率汇总 | `owner`, `repo`, `sha`                      |
| `get_coverage_trend`  | 覆盖率时间序列         | `owner`, `repo`, `interval`, `start`, `end` |
| `get_coverage_report` | 逐文件覆盖率详情       | `owner`, `repo`, `sha`                      |
| `get_coverage_tree`   | 目录树形式的覆盖率     | `owner`, `repo`                             |
| `get_file_coverage`   | 单文件逐行覆盖率       | `owner`, `repo`, `path`                     |

### Comparison Tools

| Tool                     | 用途                           | 关键参数                                       |
| ------------------------ | ------------------------------ | ---------------------------------------------- |
| `compare_coverage`       | 两个 commit 或 PR 的覆盖率对比 | `owner`, `repo`, `pullNumber` 或 `base`+`head` |
| `compare_impacted_files` | 仅列出覆盖率变化的文件         | `owner`, `repo`, `pullNumber`                  |
| `compare_file`           | 单文件行级 diff                | `owner`, `repo`, `path`, `pullNumber`          |
| `compare_flags`          | 按 flag 对比                   | `owner`, `repo`, `pullNumber`                  |
| `compare_components`     | 按 component 对比              | `owner`, `repo`, `pullNumber`                  |

### PR & Repository Tools

| Tool              | 用途                              | 关键参数                      |
| ----------------- | --------------------------------- | ----------------------------- |
| `list_pulls`      | PR 列表及覆盖率影响               | `owner`, `repo`, `state`      |
| `get_pull`        | 单个 PR 的 base/head/patch 覆盖率 | `owner`, `repo`, `pullNumber` |
| `get_repo`        | 仓库详情及当前覆盖率              | `owner`, `repo`               |
| `get_repo_config` | 活跃的 Codecov YAML 配置          | `owner`, `repo`               |
| `list_branches`   | 有覆盖率数据的分支列表            | `owner`, `repo`               |

### Commit & Flag Tools

| Tool              | 用途                             | 关键参数               |
| ----------------- | -------------------------------- | ---------------------- |
| `list_commits`    | 有覆盖率的 commit 列表           | `owner`, `repo`        |
| `get_commit`      | 单个 commit 的详细覆盖率         | `owner`, `repo`, `sha` |
| `list_flags`      | 覆盖率 flag 列表及百分比         | `owner`, `repo`        |
| `list_components` | codecov.yaml 中定义的 components | `owner`, `repo`        |

### Test Analytics

| Tool                  | 用途                   | 关键参数        |
| --------------------- | ---------------------- | --------------- |
| `list_test_analytics` | 测试通过/失败/耗时统计 | `owner`, `repo` |

## Parameter Resolution

`owner`、`repo`、`service` 三个参数按以下优先级解析：

1. 工具调用时直接传入的参数
2. 环境变量 `CODECOV_OWNER`、`CODECOV_REPO`、`CODECOV_SERVICE`
3. Git remote 自动检测（`git remote get-url origin`）
4. 若均无法解析，报错提示用户设置

如果当前目录是目标仓库的 git 本地克隆，大多数情况下无需传 owner/repo。

## Environment Variables

| 变量                   | 必需 | 默认值                   | 说明                               |
| ---------------------- | ---- | ------------------------ | ---------------------------------- |
| `CODECOV_TOKEN`        | 是   | —                        | Codecov API Access Token           |
| `CODECOV_SERVICE`      | 否   | 自动检测                 | `github`、`gitlab`、`bitbucket` 等 |
| `CODECOV_OWNER`        | 否   | 自动检测                 | 组织名或用户名                     |
| `CODECOV_REPO`         | 否   | 自动检测                 | 仓库名                             |
| `CODECOV_API_BASE_URL` | 否   | `https://api.codecov.io` | 自托管 Codecov 的 API 地址         |
| `CODECOV_CACHE_TTL_MS` | 否   | `300000`                 | 缓存 TTL（毫秒），设为 0 禁用缓存  |

## Troubleshooting

| 错误                              | 解决方案                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------- |
| `CODECOV_TOKEN is not set`        | 确认已 export token，且使用的是 API Access Token（非 Upload Token）               |
| `Authentication failed (401)`     | Token 过期或无效，到 https://app.codecov.io/account 重新生成                      |
| `Resource not found (404)`        | 检查 owner/repo 名称，确认该仓库已在 Codecov 上有覆盖率数据                       |
| `Could not determine git service` | 在目标仓库目录中运行，或手动设置 `CODECOV_SERVICE`/`CODECOV_OWNER`/`CODECOV_REPO` |
| 数据过时                          | 设置 `CODECOV_CACHE_TTL_MS=0` 禁用缓存                                            |

## Usage Examples

### 用户说："看看这个仓库的覆盖率"

1. 确认 `CODECOV_TOKEN` 已设置
2. 运行 `npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_summary`
3. 以表格形式呈现结果

### 用户说："PR #56 的覆盖率怎么样"

1. 运行 `npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_pr_coverage pullNumber:56`
2. 展示 base/head/patch 覆盖率
3. 列出覆盖率下降的文件

### 用户说："哪些文件覆盖率最低"

1. 运行 `npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_coverage_tree`
2. 按覆盖率升序排列，展示覆盖率最低的 10 个文件/目录
3. 如果用户想看某个文件的详情，运行 `npx mcporter call --stdio "npx -y codecov-mcp" codecov.get_file_coverage path:<文件路径>`

### 用户说："帮我检查 codecov.yaml 对不对"

1. 运行 `npx mcporter call --stdio "npx -y codecov-mcp" codecov.validate_yaml`
2. 展示校验结果
3. 如有错误，给出修复建议

## Output Formatting

- 默认以人类可读的文本形式展示
- 如果需要程序化处理，加 `--output json`
- 表格数据优先用 markdown 表格展示
- 百分比保留两位小数
- 覆盖率变化用颜色标记：上升用绿色文字，下降用红色文字
