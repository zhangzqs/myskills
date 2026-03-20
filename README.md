# myskills

一个轻量的 skills 仓库，当前包含一个用于自动化分类 GitHub Stars 的 skill。

## 内容

- `skills/classifying-github-stars`

## 依赖

- `gh`
- `jq`
- 有效的 GitHub 登录态

## 说明

这个仓库只包含 skill 及其最小辅助脚本，不包含完整 CLI。`classifying-github-stars` 默认先生成分类计划，再执行 GitHub Lists 写入。

