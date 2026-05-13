# AGENTS.md

AI agent context for this repository.

## Project Overview

Claude Code Skills 仓库，提供开箱即用的 Agent Skills。Skills 以 `SKILL.md` 为载体，安装到 `~/.claude/skills/` 后通过自然语言或斜杠命令触发。

## Repository Structure

```text
skills/                         # Skill 源码目录
  <skill-name>/
    SKILL.md                    # Skill 定义（必需）
    scripts/*.sh                # 辅助 Shell 脚本（可选）
    references/*.md             # 参考文档（可选）
    evals/evals.json            # 评估用例（可选）
.agents/skills/                 # 本地可用 Skill（软链接）
  mcp-to-mcporter-skill -> ../../skills/mcp-to-mcporter-skill
.claude/skills -> ../.agents/skills   # Claude Code 发现入口
```

`.agents/skills/` 存放当前项目中可直接使用的 Skill 软链接，`.claude/skills` 指向它以便 Claude Code 自动发现。后续新增基于 mcporter 的 Skill 时，在 `.agents/skills/` 下创建软链接即可。

## SKILL.md 格式规范

必须包含 YAML frontmatter：

```yaml
---
name: skill-name
description: "触发描述，包含关键词和使用场景"
---
```

- `name`：小写 kebab-case，与目录名一致
- `description`：一句话描述触发条件

正文结构：When To Use、Requirements、Hard Boundaries、Command Syntax、Common Workflows、Tool Reference、Troubleshooting。

## 安装方式

```bash
npx skills add zzq/myskills              # 全部
npx skills add zzq/myskills <skill-name> # 单个
cp -r skills/<skill-name> ~/.claude/skills/  # 手动
```

## Skill 分类

| Skill                      | 类型           | 依赖                           |
| -------------------------- | -------------- | ------------------------------ |
| `classifying-github-stars` | Shell 脚本驱动 | `gh`, `jq`, GitHub 登录态      |
| `dev-personality-test`     | 纯指令型       | 无                             |
| `codecov-mcp`              | mcporter 调用  | Node.js >= 18, `CODECOV_TOKEN` |
| `mcp-to-mcporter-skill`    | mcporter 调用  | Node.js >= 18, `mcporter`      |

## mcporter 调用模式

基于 mcporter 的 Skill 使用 ad-hoc stdio 模式调用 MCP 服务器：

```bash
npx mcporter call --stdio "npx -y <package>" <tool_name> <param>:<value>
```

- 参数以 `key:value` 形式传入（冒号分隔，无等号）
- `--output json` 获取结构化输出
- mcporter 自动继承当前 shell 环境变量

## 添加新 Skill

**必须按以下流程创建**，不要手动编写 SKILL.md：

1. **需求分析** — 先调用 `/brainstorming` 进行需求探索和设计对齐
2. **创建 Skill** — 再调用 `/skill-creator` 完成 Skill 的创建、测试和迭代

如果 `/brainstorming` 未安装，停下来引导用户安装：`npx skills add zzq/myskills brainstorming` 或检查其是否作为全局 skill 可用。

手动创建仅在以下情况允许：修复已有 Skill 的 typo 或小改动。
