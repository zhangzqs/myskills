# 微信 4.x（Windows）数据库格式

微信 4.x 的数据目录默认在 `Documents\xwechat_files\<wxid>_<hash>\`，与 3.x 的 `WeChat Files` 完全不同。

## 目录结构

```text
xwechat_files/
  <wxid>_xxxx/
    db_storage/
      message/          message_0.db ~ message_N.db、message_fts.db、media_*.db
      contact/          contact.db、contact_fts.db
      session/          session.db
      MMKV/             storage_common 等
      *.db、*.kvdb、*.material
    msg/                附件与媒体（按 MD5 分片）
    config/
  all_users/
```

判定版本：存在 `xwechat_files` 即为 4.x；3.x 是 `WeChat Files` + `Msg*.db`。

## 加密形态

- 真 SQLCipher 4（静态编译进 `Weixin.dll`，没有独立 `sqlcipher.dll`）。
- 参数：`kdf_iter=256000`、`PBKDF2-HMAC-SHA512`、`page_size=4096`、`reserve=80`、`hmac_sha512`。
- 文件头前 16 字节是 **salt**（不是 `SQLite format 3`）。
- 少部分库（`weclaw.db` 等）可能是明文，用 `head == b"SQLite format 3\0"` 判断。

### 页布局

每页 4096 字节，其中 80 字节保留区（16 字节 IV + 64 字节 HMAC）：

```text
page 1:  [0:16]      salt（取代了 "SQLite format 3\0"）
         [16:4016]   密文
         [4016:4032] IV
         [4032:4096] HMAC-SHA512

page N:  [N*4096 : N*4096+4016]  密文
         [+4016 : +4032]         IV
         [+4032 : +4096]         HMAC
```

解密：

```text
plain_p1[0:16]   = "SQLite format 3\0"
plain_p1[16:4016] = AES-256-CBC_dec(cipher[16:4016], iv)
plain_pN[0:4016]  = AES-256-CBC_dec(cipher[0:4016], iv)
解密后每页补齐 4016 内容 + 80 字节零
```

密钥派生：

```python
key = PBKDF2-HMAC-SHA512(passphrase_32B, salt=f"file[0:16]", iterations=256000, dklen=32)
```

**注意**：`passphrase` 是 32 字节口令，不是各库的 AES key。每个库用自己的 salt 派生各自的 key，所以一个 passphrase 能开所有库，但直接拿 passphrase 当 key 用会全部失败——这是最容易踩的坑。

### 快速校验（无 IV、无版本依赖）

SQLite 页头 64..80 字节恒为 0，因此：

```python
AES_ECB_enc(key, file[48:64]) == file[64:80]
```

16 字节全等，误判率可忽略。`wx_decrypt.py --verify-only` 用的就是这个。

## 表命名

会话消息表名 = `Msg_` + `md5(username)`：

- 单聊：`md5("wxid_xxxxxxxx")`
- 群聊：`md5("12345678901@chatroom")`
- 反查：`contact.db` 的 `contact(username, nick_name, remark)`，把所有 username 算一遍 md5 建反查表。

`Name2Id` 表把 `rowid` 映射到 `user_name`，消息表的 `real_sender_id` 指向它。和当前账号 `wxid` 相同即为本人。

## 消息表字段

```sql
CREATE TABLE Msg_xxx (
  local_id, server_id, local_type, sort_seq, real_sender_id,
  create_time,          -- 秒级时间戳
  status, upload_status, download_status, server_seq,
  origin_source, source,
  message_content,      -- 文本 / XML / 二进制，可能 zstd 压缩
  compress_content,
  packed_info_data,
  WCDB_CT_message_content,   -- 0=原样，4=zstd
  WCDB_CT_source
)
```

### 压缩

`WCDB_CT_message_content = 4`（或内容以 `28 B5 2F FD` 开头）表示 **zstd**：

```python
import zstandard as zstd
plain = zstd.ZstdDecompressor().decompress(blob, max_output_size=32 * 1024 * 1024)
```

### local_type

`local_type = (sub_type << 32) | base_type`，取低 32 位作基础类型：

| base | 含义 | | base | 含义 |
|---|---|---|---|---|
| 1 | 文本（含 XML 子类型） | | 43 | 视频 |
| 3 | 图片 | | 47 | 表情 |
| 34 | 语音 | | 48 | 位置 |
| 42 | 名片 | | 49 | 应用消息（链接/文件/小程序） |
| 50 | 通话 | | 10000 | 系统消息 |

常见子类型（在 XML 的 `<type>` 里，或高 32 位）：19 合并转发、33/36 小程序、57 引用回复、62 视频号。

### 群消息

群聊的 `message_content` 自带发送者前缀：

```text
wxid_xxxxxxxx:
正文内容
```

用 `^([\w@.\-]{4,64}):\n` 剥离。单聊没有这个前缀。

### 引用消息

`<appmsg><type>57</type>`，被引用内容在 `<refermsg>` 中：

```xml
<refermsg>
  <displayname>某人</displayname>
  <content><![CDATA[被引用的原文，可能本身又是一段 XML]]></content>
</refermsg>
```

`<content>` 里如果是 `<img>` / `<record>` / `<videomsg>`，说明引用的是图片/语音/视频，转成标签即可。

## 通话记录（voipmsg）

`local_type = 50`，内容是：

```xml
<voipmsg type="VoIPBubbleMsg"><VoIPBubbleMsg>
  <msg><![CDATA[通话时长 49:59]]></msg>
  <roomid>573032492549081836</roomid>
  <msg_type>100</msg_type>
  <timestamp>1785083071336</timestamp>
</VoIPBubbleMsg></voipmsg>
```

- `<msg>` 的取值：`通话时长 HH:MM:SS` / `通话时长 MM:SS`、`未应答`、`已取消`、`已在其它设备接听`、`通话中断 HH:MM:SS`
- **`<roomid>` 是每次通话的唯一标识**，用它去重（PC 与手机各存一份时会重复）
- 时长格式两段为「分:秒」，三段为「时:分:秒」
- `create_time` 是通话**结束**时间，要算「哪天打的」应用 `create_time - duration`
- 微信通话上限 12 小时，达到上限会产生 `通话中断 12:00:0x`

### PC 与手机记录不全的问题

- 在手机上接听的通话，PC 端可能只留一条「已在其它设备接听」，没有时长。
- 从手机迁移聊天记录到电脑后，`message_N.db` 会变大，通话记录条数可能翻倍。
- 因此**统计通话必须用迁移后的库**，否则会漏掉一大半。

## WAL

`message_N.db-wal` 的帧头是明文，页内容是加密的（布局同上，page 1 不带 salt 前缀的处理容易出错）。

直接解主库、跳过 WAL 最稳：只会丢失最后几百 KB 未 checkpoint 的增量。强行 apply WAL 若未正确处理 commit 帧的 `dbsize` 截断，会让库变成 `database disk image is malformed`。
