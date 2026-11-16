---
name: wechat-chat-extract
description: Use when the user wants to extract, export, back up, or analyze WeChat (微信 4.x on Windows) chat history — decrypting the SQLCipher databases, exporting a single chat or group to readable text/JSONL, or computing message and voice/video call statistics.
---

# 微信聊天记录提取

把微信 4.x（Windows）的 SQLCipher 加密数据库解开，导出成可读文本与结构化数据，并做消息量、通话时长的统计。

核心事实：**只需要一把 32 字节 passphrase 就能开全部库**。但它是 passphrase 不是 AES key，必须配合每个库自己的 salt 做 `PBKDF2-SHA512(..., 256000)` 派生——直接当 key 用会全部失败，这是最常见的坑。

## When To Use

- 导出某个人或某个群的完整聊天记录（文本、时间、发送者）
- 统计消息条数、双方占比、按月/周/天分布
- 统计语音/视频通话的次数、时长、单日曲线
- 备份自己的聊天记录为可长期保存的格式
- 分析聊天内容（性格、关系、习惯）前先拿到原始数据

## Requirements

- Windows + 微信 4.x（数据目录为 `Documents\xwechat_files`，4.2.x 已验证）
- Python 3.9+
- `pip install pycryptodome zstandard`
- 32 字节 passphrase 的十六进制串（见 `references/key-recovery.md`）

## Hard Boundaries

- **只处理本人账号、本人设备上的数据**。不代替他人提取，不处理他人账号目录。
- **只读原库**：`db_storage` 下的文件一律以 `mode=ro` 打开，解密结果写到独立目录，绝不回写微信目录。
- **不硬编码、不落盘明文密钥**：passphrase 从参数或环境变量传入，不写进脚本、不提交仓库、不在输出里打印完整值。
- 解密后的库含全部隐私内容，导出文件不要上传到任何外部服务，除非用户明确要求。
- 不修改、不删除微信的任何原始文件；需要 WAL 增量时也用副本操作。

## Files

- `scripts/wx_decrypt.py` — 校验 passphrase、解密数据库
- `scripts/wx_export.py` — 导出会话为 txt + jsonl；`--list` 可列出所有会话
- `scripts/wx_stats.py` — 统计消息分布与通话时长
- `references/wechat4-format.md` — 页布局、表名规则、local_type、zstd、通话记录格式
- `references/key-recovery.md` — passphrase 的来源、校验方式、实测排错

## Workflow

### 1. 定位账号目录

```bash
ls "$HOME/Documents/xwechat_files"          # 每个子目录是一个登录过的账号
```

含 `db_storage/` 的那一层就是账号目录。若无法确定是哪个账号，对比 `login/<wxid>` 目录名与 `db_storage` 同级目录名。

### 2. 拿到并校验 passphrase

先读 `references/key-recovery.md`。拿到 64 位 hex 后**先校验再解密**：

```bash
python scripts/wx_decrypt.py --verify-only \
  --data-dir "$HOME/Documents/xwechat_files/<wxid>_xxxx" \
  --passphrase <64hex>
```

输出 `校验通过 N/N 个库` 才继续。若全部失败，passphrase 不对或属于别的账号，不要盲目解密。

### 3. 解密

```bash
python scripts/wx_decrypt.py \
  --data-dir "$HOME/Documents/xwechat_files/<wxid>_xxxx" \
  --passphrase <64hex> \
  --out ./dec
```

默认解密 `db_storage/*/*.db` 中所有 ≥8KB 的库。只解常用的几个更快：

```bash
python scripts/wx_decrypt.py ... --only contact.db,session.db,message_0.db,message_1.db
```

大库速度约 3 万页/秒（800 MB 约 25 秒）。

### 4. 找会话

```bash
python scripts/wx_export.py --dec-dir ./dec --list
```

输出 `条数 / 昵称 / username / 所在分库`，按条数倒序。昵称来自 `contact.db` 的备注优先、昵称其次。

### 5. 导出

```bash
python scripts/wx_export.py --dec-dir ./dec --user <昵称或wxid> --out-dir ./out
```

产出：

- `<名称>_聊天记录.txt`：按日分节，`[时间] 发送者: 内容`，引用消息还原为 `⟪引用 某人: 原文⟫`
- `<名称>_messages.jsonl`：`{t, time, from, kind, text, call_sec?}`，供统计使用

群聊会自动剥离 `wxid_xxx:\n` 前缀并映射到备注名；单聊用 `real_sender_id` 区分「我」与对方。

### 6. 统计

```bash
python scripts/wx_stats.py ./out/xxx_messages.jsonl            # 总览 + 通话
python scripts/wx_stats.py ./out/xxx_messages.jsonl --by month # 按月
python scripts/wx_stats.py ./out/xxx_messages.jsonl --by week  # 按周
python scripts/wx_stats.py ./out/xxx_messages.jsonl --by day   # 按天
python scripts/wx_stats.py ./out/xxx_messages.jsonl --json     # 结构化
```

通话统计包含次数、累计时长、中位数、最长 N 次、按天/按月分布。按天曲线请用 `--json` 拿 `by_day` 再画图。

注意：**通话时长按「开始时间」归日**。`create_time` 是通话结束时间，跨零点的长通话（挂机睡觉）会算错日子。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| `校验通过 0/N` | passphrase 错或不属于该账号；见 `references/key-recovery.md` |
| 解密后 `database disk image is malformed` | 不要 apply WAL，重新只解主库（脚本默认就不处理 WAL） |
| `no such table: Msg_xxx` | 该会话不在这个分库；用 `--list` 确认在哪个 `message_N.db` |
| 消息是乱码 | 漏了 zstd 解压，检查 `WCDB_CT_message_content` |
| 通话时长明显偏少 | 库是手机迁移前的版本，PC 端只留了「已在其它设备接听」，需先从手机迁移聊天记录 |
| 只有最近几个月的消息 | 微信本地未保留更早记录，需在客户端「聊天记录迁移」中从手机导入 |
| 导出文件巨大（几十 MB） | 正常。引用消息与合并转发会展开为文本；只想看文字可用 `--json` 后自行过滤 `kind=text` |

## 版本适配

已在微信 **4.2.0.13**（Windows）实测。4.x 各小版本页布局一致；若某天 `--verify-only` 全通过但解出的库打不开，先怀疑 `reserve` 不再是 80——用内存中捕获的明文页头核对 `[20]` 字节，再调整 `wx_decrypt.py` 的 `RESERVE`。
