# 获取 passphrase

解密微信 4.x 数据库只需要一样东西：**32 字节的 passphrase**。拿到它，所有库一次全开。

## 它是什么

- 账号级主密钥，**登录时由服务端下发**，之后长期不变（实测同一把 key 跨三个月依然有效）。
- 每个库用 `PBKDF2-SHA512(passphrase, 该库 salt, 256000)` 派生各自的 AES key。
- 以 64 个十六进制字符的形式存在于工具配置里。
- **它不是 AES key 本身**。直接 `AES.new(passphrase)` 会全部失败。

## 途径一：读已有工具的配置（最快）

如果装过 CipherTalk 之类的解密工具，它会把抓到的 key 存在自己的配置库里。这个库是**明文 SQLite**：

```text
%APPDATA%\ciphertalk\ciphertalk-config.db
```

```python
import sqlite3, json
con = sqlite3.connect(r"%APPDATA%\ciphertalk\ciphertalk-config.db")
row = con.execute("select value from config where key='accounts'").fetchone()
for acc in json.loads(row[0]):
    print(acc.get('wxid'), acc.get('decryptKey'))   # 64 hex
```

拿到 `decryptKey` 后立刻用 `wx_decrypt.py --verify-only` 校验，再决定是否使用。

同类工具还有 WeFlow / MemoTrace / CipherTalk 的分支，配置存放位置各不相同，但都是明文 SQLite 或 JSON，用 `grep -ril "decryptKey\|db_key"` 在 `%APPDATA%` 下搜通常能找到。

## 途径二：运行时从进程取（不推荐）

在微信 4.2 上，这条路基本走不通，实测结论：

| 尝试 | 结果 |
|---|---|
| 扫内存里的 32 字节 key（逐字节，5 个布局模型，AES-128/256） | 0 命中 |
| 扫 64 位十六进制字符串 | 0 命中 |
| 扫 AES 密钥调度表反推（自检通过） | 0 命中 |
| 读 SQLCipher 的 `sqlcipher_ctx` 结构、顺着 salt 指针找 | 结构在，但 key 不在 |
| 磁盘配置 / MMKV / kvdb / `.material` | 0 命中 |
| 解 `login\<wxid>\key_info.dat`（179B protobuf） | DPAPI 全偏移失败 |

原因：passphrase 由服务端下发后**持久化在本地加密存储**，读库时解出、用完即清。空闲时刻内存里根本没有它。

只有两种方式可能奏效：趁打开库的瞬间高频采样（窗口必须真正活跃，且需要 C 级扫描器），或在 AES-NI 调用点下断点 dump 轮密钥（需注入调试器，有让微信崩溃/要求重新扫码的风险）。

CipherTalk 的 `wechat_key_tool.dll` 用的是另一套思路：在 `Weixin.dll` 里用代码签名定位「保管 key 的 getter」，再回内存读那个 `std::string`。但它在 4.2.0.13 上同样返回空 key（`markers=11, candidates=8, key=""`），说明新版把这条路也堵了。

## 途径三：手机端

部分安卓端工具能直接导出 passphrase。拿到 64 hex 后在电脑端复用即可，两端是同一把（同一账号）。

## 校验

拿到后先验证，不要盲目解密：

```bash
python scripts/wx_decrypt.py --verify-only --data-dir "<账号目录>" --passphrase <64hex>
```

判定依据是 `AES_ECB(key, file[48:64]) == file[64:80]`（页头 64..80 恒为零），无 IV 依赖、无版本依赖。

## 排错

| 现象 | 原因 |
|---|---|
| 所有库校验失败 | passphrase 不对；或该 key 属于另一个账号 |
| 部分库失败 | 该库密钥已轮换；或被其它进程独占锁住 |
| 解出的库 `database disk image is malformed` | 应用了 WAL 但没处理 commit 帧的 dbsize 截断，重新只解主库 |
| 解出库能打开但表为空 | 解的是 WAL 里的旧副本，重新从主库解 |
| `no such table: Msg_xxx` | 表名 md5 的输入不是明文 username，检查是否用了 `encrypt_username`；或该会话的消息在别的分库 |
| 消息内容是乱码 | 忘了处理 `WCDB_CT_message_content=4` 的 zstd |

## 边界

只对**本人账号**、**本人设备**上的数据做这些操作。passphrase 等同账号密码，不要写进代码、提交到仓库或贴在对话里。
