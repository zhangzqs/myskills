#!/usr/bin/env python3
"""微信 4.x (Windows) SQLCipher4 数据库解密 / 校验工具。

页布局（本工具已按真实 SQLCipher 4.12 校准）：

    page 1:  file[0:16] = salt
             ciphertext = file[16:PAGE-RESERVE]
             iv         = file[PAGE-RESERVE : PAGE-RESERVE+16]
             plaintext  = b"SQLite format 3\\0" + CBC_dec(ciphertext, iv)
    page N:  ciphertext = file[N*PAGE : (N+1)*PAGE-RESERVE]
             iv         = 该页最后 RESERVE 字节的前 16 字节
             plaintext  = CBC_dec(ciphertext, iv)

每页解密后 = (PAGE-RESERVE) 字节内容 + RESERVE 字节保留区（置零）。

用法：
    # 只校验密钥对不对（对任一 .db 都行，很快）
    python wx_decrypt.py --verify-only --data-dir <xwechat_files/账号目录> --passphrase <hex>

    # 解密全部库
    python wx_decrypt.py --data-dir <...> --passphrase <hex> --out ./dec

    # 只解密指定的库
    python wx_decrypt.py --data-dir <...> --passphrase <hex> --only message_1.db,contact.db
"""
import argparse
import glob
import hashlib
import os
import sys
import time

try:
    from Crypto.Cipher import AES
except ImportError:
    sys.exit("缺少依赖：pip install pycryptodome")

PAGE = 4096
RESERVE = 80
BODY = PAGE - RESERVE
MAGIC = b'SQLite format 3\x00'
KDF_ITER = 256000


def derive_key(passphrase: bytes, salt: bytes) -> bytes:
    """passphrase + 该库自己的 salt -> AES-256 key。"""
    return hashlib.pbkdf2_hmac('sha512', passphrase, salt, KDF_ITER, 32)


def verify_key(passphrase: bytes, db_path: str) -> bool:
    """校验 passphrase 是否适配该库。

    利用 SQLite 页头 64..80 字节恒为零这一事实：
        C[64:80] == AES_ECB_enc(key, C[48:64])
    与页版本（change counter）、IV 都无关，16 字节全等判定极可靠。
    """
    with open(db_path, 'rb') as f:
        head = f.read(PAGE)
    if len(head) < PAGE:
        return False
    key = derive_key(passphrase, head[0:16])
    return AES.new(key, AES.MODE_ECB).encrypt(head[48:64]) == head[64:80]


def cbc_dec(key: bytes, ct: bytes, iv: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).decrypt(ct)


def decrypt_db(src: str, dst: str, passphrase: bytes, log=print) -> int:
    size = os.path.getsize(src)
    npages = size // PAGE
    with open(src, 'rb') as f:
        head = f.read(PAGE)
    key = derive_key(passphrase, head[0:16])
    t0 = time.time()
    with open(src, 'rb') as fi, open(dst, 'wb') as fo:
        for pg in range(npages):
            raw = fi.read(PAGE)
            if len(raw) < PAGE:
                break
            out = bytearray(PAGE)
            if pg == 0:
                out[0:16] = MAGIC
                out[16:BODY] = cbc_dec(key, raw[16:BODY], raw[BODY:BODY + 16])
            else:
                out[0:BODY] = cbc_dec(key, raw[0:BODY], raw[BODY:BODY + 16])
            fo.write(out)
            if log and pg and pg % 50000 == 0:
                el = time.time() - t0
                log(f"    {pg}/{npages}  {el:.0f}s  {pg / el:.0f} pg/s")
    return npages


def find_account_dir(data_root: str):
    """定位账号目录（含 db_storage 的那一层）。"""
    if os.path.isdir(os.path.join(data_root, 'db_storage')):
        return data_root
    cands = []
    for p in glob.glob(os.path.join(data_root, '*', 'db_storage')):
        cands.append(os.path.dirname(p))
    if not cands:
        return None
    if len(cands) > 1:
        print("发现多个账号目录，请用 --data-dir 指定其中一个：")
        for c in cands:
            print("   ", c)
        return None
    return cands[0]


def main():
    ap = argparse.ArgumentParser(description="微信 4.x SQLCipher4 数据库解密")
    ap.add_argument('--data-dir', required=True,
                    help="账号目录（含 db_storage），或 xwechat_files 根目录")
    ap.add_argument('--passphrase', required=True,
                    help="32 字节 passphrase 的十六进制串（64 个 hex 字符）")
    ap.add_argument('--out', default='./dec', help="输出目录，默认 ./dec")
    ap.add_argument('--only', default='', help="只处理这些库，逗号分隔")
    ap.add_argument('--verify-only', action='store_true', help="只校验密钥，不解密")
    args = ap.parse_args()

    acct = find_account_dir(args.data_dir)
    if not acct:
        sys.exit("找不到含 db_storage 的账号目录")
    dbdir = os.path.join(acct, 'db_storage')

    try:
        passphrase = bytes.fromhex(args.passphrase.strip().lower())
    except ValueError:
        sys.exit("--passphrase 必须是十六进制串")
    if len(passphrase) != 32:
        sys.exit(f"passphrase 应为 32 字节（64 hex），当前 {len(passphrase)} 字节")

    dbs = sorted(glob.glob(os.path.join(dbdir, '*', '*.db')))
    dbs = [d for d in dbs if os.path.getsize(d) >= 8192]
    if args.only:
        want = {x.strip() for x in args.only.split(',') if x.strip()}
        dbs = [d for d in dbs if os.path.basename(d) in want]
    if not dbs:
        sys.exit("没有找到可处理的数据库")

    if args.verify_only:
        ok = [d for d in dbs if verify_key(passphrase, d)]
        print(f"校验通过 {len(ok)}/{len(dbs)} 个库")
        for d in ok[:5]:
            print("   OK", os.path.basename(d))
        if not ok:
            print("全部失败：passphrase 不对，或该库已轮换密钥/属于其它账号")
            sys.exit(2)
        return

    os.makedirs(args.out, exist_ok=True)
    done = fail = 0
    for src in dbs:
        dst = os.path.join(args.out, os.path.basename(src))
        size_mb = os.path.getsize(src) / 2 ** 20
        print(f"=== {os.path.basename(src)}  ({size_mb:.1f} MB)")
        if not verify_key(passphrase, src):
            print("    ! 密钥不匹配，跳过")
            fail += 1
            continue
        n = decrypt_db(src, dst, passphrase)
        print(f"    {n} 页 -> {dst}")
        done += 1
    print(f"\n完成 {done} 个，跳过 {fail} 个。输出目录：{os.path.abspath(args.out)}")


if __name__ == '__main__':
    main()
