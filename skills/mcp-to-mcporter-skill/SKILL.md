---
name: mcp-to-mcporter-skill
description: "Convert any MCP server into a Claude Code skill using mcporter. Use when: user wants to wrap an MCP as a skill, create skill from MCP, generate SKILL.md for MCP server, convert MCP to skill, or says 'wrap this MCP', 'make a skill from MCP', 'turn MCP into skill'. Also triggers on: skill generator, MCP skill creator, mcporter skill."
---

# MCP to mcporter Skill Generator

将任意 MCP 服务器转换为基于 mcporter 的 Claude Code skill。输入 MCP 包名或 command，自动生成完整的 SKILL.md。

## When To Use

- 用户想把某个 MCP 服务器包装成 skill
- 用户说"把这个 MCP 转成 skill"
- 用户想减少 MCP 工具占用的 context token
- 用户有多个 MCP 想要统一管理

## Requirements

- Node.js >= 18
- mcporter 已安装（`npx mcporter --version` 可用）

## Workflow

### Step 1: 获取 MCP 信息

用户提供 MCP 服务器信息，支持以下格式：

**npm 包名：**

```
codecov-mcp
@anthropic/mcp-server-github
```

**自定义 command：**

```
bun run ./server.ts
python mcp_server.py --port 8080
```

**已配置的服务器名：**

```
github (从 mcporter 配置中读取)
```

### Step 2: 获取工具列表

使用 mcporter 列出服务器的所有工具：

```bash
# 对于 npm 包
npx mcporter list --stdio "npx -y <package>" --schema

# 对于自定义 command
npx mcporter list --stdio "<command>" --schema

# 对于已配置的服务器
npx mcporter list <server-name> --schema
```

如果命令需要环境变量，使用 `--env` 传递：

```bash
npx mcporter list --stdio "npx -y codecov-mcp" --env CODECOV_TOKEN=test --schema
```

### Step 2.1: 处理包兼容性问题

如果 `npx -y <package>` 失败（如包没有 `bin` 字段），尝试以下方案：

**方案 A：搜索替代包**

```bash
npm search <keyword> --json | jq '.[] | select(.name | test("mcp")) | .name'
```

很多 MCP 服务器有多个发布者，尝试其他包名。

**方案 B：下载并直接运行**

```bash
# 下载包
mkdir -p /tmp/mcp-server && cd /tmp/mcp-server
npm pack <package> && tar -xzf *.tgz

# 安装依赖
cd package && npm install --production

# 检查入口文件
cat package.json | jq '.main // .module // "index.js"'

# 使用 node 直接运行
npx mcporter list --stdio "node /tmp/mcp-server/package/build/index.js" --schema
```

**方案 C：检查包是否有 CLI 入口**

```bash
# 查看 package.json 的 bin 字段
npm info <package> bin
```

在生成的 SKILL.md 中，记录发现的兼容性问题和解决方案。

### Step 2.5: 验证工具可用性

**重要：不要信任文档中的工具名，必须实际验证。**

很多 MCP 服务器的文档（README）与实际实现不一致。在 Step 2 获取工具列表后，必须：

1. 用实际工具名（从 `mcporter list --schema` 输出中提取）替换文档中的工具名
2. 对每个工具进行一次实际调用测试，确认可用
3. 记录工具的实际参数格式（可能与文档描述不同）

```bash
# 测试工具是否可用
npx mcporter call --stdio "npx -y <package>" --env TOKEN=test <tool_name> <required_params>
```

如果调用失败，检查：
- 工具名是否正确（大小写、下划线）
- 必需参数是否齐全
- 环境变量是否正确传递

### Step 3: 分析工具

从获取的 schema 中提取：

1. **工具列表** — 所有可用工具的名称和描述
2. **参数定义** — 每个工具的输入参数、类型、是否必需
3. **分类** — 按功能分组（查询类、操作类、复合工具等）
4. **环境变量** — 从以下来源推断必需的环境变量：
   - mcporter list 输出中的 env 相关错误
   - 包的 README 或文档（使用 `npm info <package>` 查看）
   - 工具参数中的 token/key 相关字段
   - 常见模式：`<SERVICE>_TOKEN`、`<SERVICE>_API_KEY`、`<SERVICE>_ACCESS_TOKEN`

**环境变量推断规则：**

- 如果工具需要认证，检查文档中的环境变量名
- 常见 MCP 服务器的环境变量：
  - GitHub: `GITHUB_TOKEN`
  - Linear: `LINEAR_ACCESS_TOKEN` 或 `LINEAR_API_KEY`
  - Codecov: `CODECOV_TOKEN`
  - Slack: `SLACK_BOT_TOKEN`
- 如果无法确定，在 SKILL.md 中标记为 `<SERVICE>_TOKEN` 并提示用户查阅文档

### Step 4: 生成 SKILL.md

根据分析结果生成 SKILL.md，结构如下：

```markdown
---
name: <skill-name>
description: "<触发描述，包含关键词和场景>"
---

# <Skill 标题>

<一句话说明这个 skill 的用途>

## When To Use

<基于工具功能推导的使用场景列表>

## Requirements

<运行依赖，包括 Node.js、环境变量等>

## Hard Boundaries

<安全边界，如不暴露 token、只读操作等>

## First-Time Setup

<环境变量设置说明>

## Command Syntax

<mcporter call --stdio 的调用格式>

## Common Workflows

<基于工具分类推导的常用工作流，每个包含具体命令示例>

## Tool Reference

<工具分类表格，包含工具名、用途、关键参数>

## Environment Variables

<环境变量表格>

## Troubleshooting

<常见错误和解决方案>
```

### Step 5: 生成规则

**Frontmatter：**

- `name`：从包名推导，移除 `mcp-server-` 或 `-mcp` 后缀
- `description`：包含触发关键词（wrap、convert、skill 等）和核心功能描述

**触发描述模板：**

```
"<功能描述> Use when: <场景1>, <场景2>, <场景3>. Triggers on: <关键词1>, <关键词2>."
```

**命令格式：**

```bash
npx mcporter call --stdio "<command>" <tool_name> <param>:<value>
```

**工作流生成规则：**

1. 优先使用复合工具（一次调用完成多步骤）
2. 每个工作流包含：场景说明、命令示例、参数说明
3. 常见工作流：快速概览、详情查看、搜索/过滤、创建/修改

**工具表格格式：**
| Tool | 用途 | 关键参数 |
|------|------|----------|
| `tool_name` | 一句话描述 | `param1`, `param2` |

### Step 6: 保存输出

将生成的 SKILL.md 保存到用户指定位置，默认为：

```
skills/<skill-name>/SKILL.md
```

### Step 7: 脚本封装（推荐）

对于工具数量 >= 3 个的 MCP 服务器，建议创建 `scripts/` 目录封装 bash 脚本，简化 agent 调用。

**目录结构：**

```
skills/<skill-name>/
  SKILL.md
  scripts/
    _common.sh      # 公共函数
    <tool1>.sh      # 每个工具一个脚本
    <tool2>.sh
```

**`_common.sh` 模板：**

```bash
#!/usr/bin/env bash
# 公共辅助函数

die() { echo "错误: $*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "缺少依赖: $1"; }
check_token() { [[ -n "${SERVICE_TOKEN:-}" ]] || die "SERVICE_TOKEN 未设置"; }

# 从 git remote 检测 owner/repo
parse_owner_repo() {
  # ... 解析 --owner/--repo 参数，fallback 到 git remote
}

# 调用 MCP 工具，自动处理错误
call_mcp() {
  local tool="$1"; shift
  local result
  result=$(npx mcporter call --stdio "<command>" --env TOKEN="$TOKEN" "$tool" "$@" 2>&1)
  [[ "$result" == Error:* ]] && die "${result#Error: }"
  echo "$result"
}
```

**脚本封装要点：**

1. 每个脚本使用 `set -euo pipefail` 严格模式
2. 支持 `--help` 显示用法
3. 支持 `--json` 输出原始 JSON
4. 自动从 git remote 检测 owner/repo
5. 用 jq 格式化输出为人类可读格式

**大 JSON 处理：**

某些 MCP 工具返回超大 JSON（>1MB），直接管道传递可能被截断。解决方案：

```bash
# 先写入临时文件，再用 jq 提取需要的字段
tmpfile=$(mktemp)
trap "rm -f '$tmpfile'" EXIT
npx mcporter call ... > "$tmpfile" 2>&1
jq '{field1, field2}' "$tmpfile"
```

**SKILL.md 更新：**

在生成的 SKILL.md 的 `Command Syntax` 部分，同时提供脚本调用和原始 mcporter 调用两种方式，优先推荐脚本。

## Output Format

生成的 SKILL.md 必须包含：

1. **Frontmatter** — name、description
2. **When To Use** — 至少 5 个使用场景
3. **Requirements** — 所有依赖项
4. **Hard Boundaries** — 安全约束
5. **Command Syntax** — 调用格式说明
6. **Common Workflows** — 至少 3 个工作流
7. **Tool Reference** — 所有工具的分类表格
8. **Environment Variables** — 环境变量表格（如有）
9. **Troubleshooting** — 常见错误（至少 3 条）

## Example

**输入：**

```
将 codecov-mcp 转换成 skill
```

**处理：**

```bash
npx mcporter list --stdio "npx -y codecov-mcp" --schema
```

**输出：**
生成 `skills/codecov-mcp/SKILL.md`，包含 37 个工具的说明和 9 个工作流。

## Error Handling

| 错误               | 解决方案                               |
| ------------------ | -------------------------------------- |
| mcporter 未安装    | 提示 `npm install -g mcporter`         |
| MCP 服务器无法启动 | 检查 command 是否正确，依赖是否安装    |
| 工具列表为空       | 检查服务器是否正常运行，是否有认证要求 |
| schema 获取失败    | 使用 `--env` 传递必要的环境变量        |

## Limitations

- 无法自动推断所有环境变量，可能需要用户补充
- 生成的工作流是基于工具描述的推导，可能需要人工调整
- 不支持需要 OAuth 认证的 MCP 服务器（需先完成认证）
