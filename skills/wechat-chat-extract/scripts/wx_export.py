#!/usr/bin/env python3
"""从已解密的微信 4.x 数据库中导出指定会话（单聊/群聊）的聊天记录。

用法：
    # 列出所有有消息的会话
    python wx_export.py --dec-dir ./dec --list

    # 按昵称导出（自动解析 username）
    python wx_export.py --dec-dir ./dec --user 铮铮 --out-dir ./out

    # 按 username 导出
    python wx_export.py --dec-dir ./dec --user 51684426160@chatroom --out-dir ./out

输出：
    <out-dir>/<名称>_聊天记录.txt    按日分节、人可读
    <out-dir>/<名称>_messages.jsonl  结构化，供 wx_stats.py 使用
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

try:
    import zstandard as zstd
except ImportError:
    sys.exit("缺少依赖：pip install zstandard")

ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'
_zdec = zstd.ZstdDecompressor()

BASE_TYPE = {
    1: '文本', 3: '图片', 34: '语音', 43: '视频', 47: '表情',
    48: '位置', 49: '应用消息', 42: '名片', 50: '通话', 10000: '系统',
}
APPMSG_TYPE = {
    '3': '音乐', '4': '链接', '5': '链接', '6': '文件', '8': '表情',
    '17': '位置', '19': '合并转发', '33': '小程序', '36': '小程序',
    '51': '视频号', '57': '引用', '62': '视频号', '63': '直播',
    '74': '文件', '87': '群公告', '2000': '转账', '2001': '红包',
}


def ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def rx1(pat, s, default=''):
    m = re.search(pat, s, re.S)
    return m.group(1).strip() if m else default


def unescape(s):
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&'))


def clean_cdata(s):
    s = s.strip()
    if s.startswith('<![CDATA[') and s.endswith(']]>'):
        s = s[9:-3]
    return s


def parse_appmsg(s, base_type, depth=0):
    """把 XML 类型内容压成一行可读文本。"""
    if not s or not s.lstrip().startswith('<'):
        return s.strip()
    title = clean_cdata(rx1(r'<title>(.*?)</title>', s))
    des = clean_cdata(rx1(r'<des>(.*?)</des>', s))
    if des in ('null', 'None'):
        des = ''
    t = rx1(r'<type>(\d+)</type>', s)
    kind = APPMSG_TYPE.get(t, '')

    quoted = ''
    if '<refermsg>' in s:
        blk = s[s.index('<refermsg>'):]
        rname = unescape(clean_cdata(rx1(r'<displayname>(.*?)</displayname>', blk)))
        inner = unescape(clean_cdata(rx1(r'<content>(.*?)</content>', blk)))
        if inner.lstrip().startswith('<'):
            if '<img' in inner:
                inner_txt = '[图片]'
            elif '<record' in inner:
                inner_txt = '[语音]'
            elif '<videomsg' in inner or '<video' in inner:
                inner_txt = '[视频]'
            elif '<emoji' in inner:
                inner_txt = '[表情]'
            else:
                inner_txt = clean_cdata(rx1(r'<title>(.*?)</title>', inner)) or \
                            re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', unescape(inner))).strip()[:120]
        else:
            inner_txt = inner
        inner_txt = re.sub(r'\s+', ' ', inner_txt).strip()[:200]
        quoted = f" ⟪引用 {rname}: {inner_txt}⟫" if inner_txt else f" ⟪引用 {rname}⟫"

    if kind == '引用':
        return (title + quoted) if title else (quoted.strip() or '[引用]')
    if kind == '图片':
        return '[图片]'
    if kind == '链接':
        return f"[链接] {title}" + (f" — {des}" if des else '')
    if kind == '文件':
        return f"[文件] {title}"
    if kind in ('小程序', '视频号', '直播', '音乐', '转账', '红包'):
        return f"[{kind}] {title}"
    if title or des:
        return f"[{kind or '分享'}] {title}" + (f" — {des}" if des else '')
    if '<emoji' in s:
        return '[表情]'
    if '<location' in s:
        return f"[位置] {rx1(r'<label>(.*?)</label>', s) or rx1(r'<poiname>(.*?)</poiname>', s)}"
    plain = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', s))).strip()
    return plain[:200]


def parse_voip(raw):
    """通话气泡 -> (显示文本, 秒数)。"""
    m = re.search(r'<msg><!\[CDATA\[(.*?)\]\]></msg>', raw, re.S)
    txt = (m.group(1) if m else '').strip()
    sec = None
    mm = re.search(r'(?:通话时长|通话中断)\s*([\d:]+)', txt)
    if mm:
        p = [int(x) for x in mm.group(1).split(':')]
        sec = p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]
        h, rem = divmod(sec, 3600)
        label = f"{h} 小时 {rem // 60} 分" if h else f"{rem // 60} 分 {sec % 60} 秒"
        return f"[通话] {label}", sec
    return f"[通话] {txt or '未接通'}", None


def load_contacts(dec_dir):
    p = os.path.join(dec_dir, 'contact.db')
    if not os.path.exists(p):
        return {}
    con = ro(p)
    out = {}
    for un, nn, rm in con.execute("select username, nick_name, remark from contact"):
        out[un] = (rm or '').strip() or (nn or '').strip() or un
    con.close()
    return out


def resolve_user(dec_dir, arg, contacts):
    if arg.endswith('@chatroom') or arg.startswith('wxid_') or '@' in arg:
        return arg
    hits = [u for u, name in contacts.items() if arg in name]
    if not hits:
        sys.exit(f"找不到匹配「{arg}」的联系人")
    if len(hits) > 1:
        print("多个匹配，使用第一个：")
        for u in hits:
            print(f"   {u}  {contacts.get(u)}")
    return hits[0]


def main():
    ap = argparse.ArgumentParser(description="导出微信聊天记录")
    ap.add_argument('--dec-dir', required=True, help="wx_decrypt.py 的输出目录")
    ap.add_argument('--user', help="昵称 / 备注 / username")
    ap.add_argument('--out-dir', default='./out')
    ap.add_argument('--tag', help="输出文件名前缀，默认用显示名")
    ap.add_argument('--list', action='store_true', help="列出有消息的会话")
    args = ap.parse_args()

    contacts = load_contacts(args.dec_dir)
    dbs = sorted(glob.glob(os.path.join(args.dec_dir, 'message_[0-9].db')))
    if not dbs:
        sys.exit(f"{args.dec_dir} 下没有 message_*.db")

    if args.list:
        rows = []
        for p in dbs:
            con = ro(p)
            for (t,) in con.execute(
                    "select name from sqlite_master where type='table' and name like 'Msg_%'"):
                try:
                    n = con.execute(f"select count(*) from {t}").fetchone()[0]
                except sqlite3.Error:
                    continue
                rows.append((n, t, os.path.basename(p)))
            con.close()
        md5map = {hashlib.md5(u.encode()).hexdigest(): u for u in contacts}
        for n, t, db in sorted(rows, reverse=True):
            h = t[4:]
            u = md5map.get(h, '(未知会话)')
            print(f"{n:8d}  {contacts.get(u, u):28s} {u:28s} {db}")
        return

    if not args.user:
        sys.exit("需要 --user 或 --list")

    un = resolve_user(args.dec_dir, args.user, contacts)
    display = contacts.get(un, un)
    is_group = un.endswith('@chatroom')
    table = 'Msg_' + hashlib.md5(un.encode()).hexdigest()
    print(f"会话 {un}（{display}）{'群聊' if is_group else '单聊'}  表 {table}")

    # 定位表在哪些分库
    found = []
    for p in dbs:
        con = ro(p)
        hit = con.execute("select count(*) from sqlite_master where type='table' and name=?",
                          (table,)).fetchone()[0]
        if hit:
            n = con.execute(f"select count(*) from {table}").fetchone()[0]
            found.append((p, n))
        con.close()
    if not found:
        sys.exit("没有找到该会话的消息表")
    for p, n in found:
        print(f"   {os.path.basename(p)}: {n} 条")

    # sender 映射
    senders = {}
    for p, _ in found:
        con = ro(p)
        for rid, u in con.execute("select rowid, user_name from Name2Id"):
            senders.setdefault(rid, u)
        con.close()

    rows = []
    for p, _ in found:
        con = ro(p)
        q = (f"select local_id, local_type, create_time, real_sender_id, "
             f"message_content, WCDB_CT_message_content from {table}")
        for lid, lt, ct, sid, mc, cct in con.execute(q):
            base = lt & 0xFFFFFFFF
            sub = lt >> 32
            if isinstance(mc, (bytes, bytearray)):
                b = bytes(mc)
                if cct == 4 or b[:4] == ZSTD_MAGIC:
                    try:
                        b = _zdec.decompress(b, max_output_size=32 * 1024 * 1024)
                    except zstd.ZstdError:
                        pass
                txt = b.decode('utf-8', 'replace')
            else:
                txt = mc or ''

            sender = senders.get(sid, '')
            if is_group:
                m = re.match(r'^([\w@.\-]{4,64}):\n', txt)
                if m:
                    sender = m.group(1)
                    txt = txt[m.end():]

            call_sec = None
            kind = 'text'
            if base == 50:
                msg, call_sec = parse_voip(txt)
                kind = 'call'
            elif base == 3:
                msg, kind = '[图片]', 'image'
            elif base == 34:
                msg, kind = '[语音]', 'voice'
            elif base == 43:
                msg, kind = '[视频]', 'video'
            elif base == 47:
                msg, kind = '[表情]', 'sticker'
            elif base == 10000:
                msg, kind = re.sub(r'<[^>]+>', '', txt)[:200].strip(), 'system'
            elif base == 49:
                msg, kind = parse_appmsg(txt, base), 'app'
            elif base == 1:
                msg = parse_appmsg(txt, base) if txt.lstrip().startswith('<') else txt.strip()
                kind = 'text'
            else:
                msg, kind = parse_appmsg(txt, base), 'other'

            msg = (msg or '').strip()
            if not msg:
                continue
            if '\n' in msg:
                msg = ' / '.join(x.strip() for x in msg.split('\n') if x.strip())
            if msg.count('<') > 2 and msg.count('>') > 2:
                msg = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', msg)).strip()

            if kind == 'system':
                who = ''
            elif is_group:
                who = contacts.get(sender, sender) if sender else ''
            elif not sender:
                who = display          # 兜底：拿不到 sender 就记对方
            elif sender == un:
                who = display          # 对方发的
            else:
                who = '我'             # 本机账号发的
            rows.append({'ct': ct, 'lid': lid, 'who': who, 'text': msg,
                         'kind': kind, 'call_sec': call_sec})
        con.close()

    rows.sort(key=lambda r: (r['ct'], r['lid']))
    tag = args.tag or re.sub(r'[\\/:*?"<>|]', '_', display)
    os.makedirs(args.out_dir, exist_ok=True)

    txt_path = os.path.join(args.out_dir, f'{tag}_聊天记录.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"# 与「{display}」({un}) 的聊天记录\n")
        f.write(f"# 共 {len(rows)} 条  "
                f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(rows[0]['ct']))} ~ "
                f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(rows[-1]['ct']))}\n\n")
        last = None
        for r in rows:
            t = time.localtime(r['ct'])
            day = time.strftime('%Y-%m-%d', t)
            if day != last:
                f.write(f"\n===== {day} =====\n")
                last = day
            line = f"[{time.strftime('%H:%M:%S', t)}] {r['who']}: {r['text']}" if r['who'] \
                else f"[{time.strftime('%H:%M:%S', t)}] {r['text']}"
            f.write(line + '\n')
    print(f"写出 {txt_path}  ({os.path.getsize(txt_path) / 2 ** 20:.2f} MB)")

    js = os.path.join(args.out_dir, f'{tag}_messages.jsonl')
    with open(js, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps({
                't': r['ct'],
                'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r['ct'])),
                'from': r['who'],
                'kind': r['kind'],
                'text': r['text'],
                **({'call_sec': r['call_sec']} if r['call_sec'] else {}),
            }, ensure_ascii=False) + '\n')
    print(f"写出 {js}  ({os.path.getsize(js) / 2 ** 20:.2f} MB)")


if __name__ == '__main__':
    main()
