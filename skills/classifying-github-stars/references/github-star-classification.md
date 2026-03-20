# GitHub Stars 分类参考

这份参考文档的目标不是制造复杂 taxonomy，而是让 agent 在分类时保持稳定、一致、可复用。

## 分类原则

1. 优先复用已有 List 名，不轻易创建新名字
2. 每个仓库优先给 1 个主分类，必要时再补 1 个辅助分类
3. 遇到模糊仓库时，宁可少分，不要硬分
4. 名称保持短、稳定、可长期复用

## 推荐 List 命名

- `AI`
- `DevTools`
- `Infra`
- `DevOps`
- `Frontend`
- `Backend`
- `Data`
- `Database`
- `Security`
- `Python`
- `Go`
- `Rust`
- `JavaScript`
- `TypeScript`

## 判断顺序

### 1. topics

如果 topics 已经很明确，优先按 topics 判定。

例子：

- `llm` `rag` `prompt-engineering` -> `AI`
- `terraform` `kubernetes` `docker` -> `Infra` 或 `DevOps`
- `react` `nextjs` `vue` `svelte` -> `Frontend`
- `postgres` `mysql` `sqlite` `redis` -> `Database`
- `auth` `oauth` `cryptography` -> `Security`

### 2. language

语言适合作为辅助分类，不建议单独替代主题分类。

例子：

- AI SDK + Python -> `AI` + `Python`
- Kubernetes operator + Go -> `Infra` + `Go`

### 3. repo 名称和描述

当 topics 不充分时，再看名称和描述中的关键词。

关键词示例：

- `agent` `llm` `embedding` `model` -> `AI`
- `cli` `sdk` `tooling` `formatter` -> `DevTools`
- `api` `server` `gateway` `framework` -> `Backend`
- `ui` `component` `design-system` -> `Frontend`

## 模糊项处理

下面这些情况不要强行自动执行：

- 仅从名字看不出用途
- 同时符合 3 个以上分类
- 只是个人收藏或示例仓库，没有明显主题

做法：

- 放到人工复核清单
- 或仅保留语言分类，不写主分类

## 建议计划格式

```json
{
  "targetAccount": "zhangzqs",
  "listVisibility": "private",
  "repos": [
    {
      "repo": "openai/openai-python",
      "lists": ["AI", "Python"]
    }
  ]
}
```

## 执行建议

- 先对 10 到 20 个仓库做小批量 dry-run
- 看分类风格是否稳定
- 确认无误后再扩大范围
