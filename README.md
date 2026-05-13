# myskills

一个面向 Claude Code 的轻量 Skills 仓库，提供开箱即用的 Agent Skills。

## 包含的 Skills

| Skill                      | 说明                                                                   |
| -------------------------- | ---------------------------------------------------------------------- |
| `classifying-github-stars` | 自动分析 GitHub Stars，生成分类计划并写入 GitHub Lists                 |
| `dev-personality-test`     | 面向程序员的全方位人格测试（MBTI / 大五 / 九型 / 霍兰德 / 程序员画像） |
| `codecov-mcp`              | 通过 mcporter 调用 codecov-mcp，查询 Codecov 代码覆盖率数据            |
| `mcp-to-mcporter-skill`    | 将任意 MCP 服务器转换为基于 mcporter 的 Claude Code skill              |

## 安装

推荐使用 skills.sh 一键安装：

```bash
# 安装全部 skills
npx skills add zzq/myskills

# 仅安装某个 skill
npx skills add zzq/myskills classifying-github-stars
npx skills add zzq/myskills dev-personality-test
```

安装完成后，skills 会被放置到 `~/.claude/skills/` 目录，在所有项目中均可使用。

### 手动安装

如果不使用 `npx skills`，也可以手动克隆：

```bash
git clone https://github.com/zzq/myskills.git
cp -r myskills/skills/* ~/.claude/skills/
```

## 使用方式

在 Claude Code 中直接用自然语言触发即可，例如：

- "帮我整理 GitHub Stars"
- "做一个程序员性格测试"
- "把 linear-mcp 转成 skill"

也可以用斜杠命令显式调用：

```text
/classifying-github-stars
/dev-personality-test
```

## 依赖

### classifying-github-stars

- [`gh`](https://cli.github.com/) — GitHub CLI
- [`jq`](https://jqlang.github.io/jq/) — JSON 处理工具
- 有效的 GitHub 登录态（`gh auth login`）

### dev-personality-test

无额外依赖。

### codecov-mcp

- Node.js >= 18
- Codecov API Access Token（从 [Codecov 控制台](https://app.codecov.io/account) 获取）
- mcporter 会自动安装 codecov-mcp（通过 npx）

### mcp-to-mcporter-skill

- Node.js >= 18
- mcporter（`npm install -g mcporter`）

## License

MIT
