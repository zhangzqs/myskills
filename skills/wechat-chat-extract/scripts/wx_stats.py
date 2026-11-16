#!/usr/bin/env python3
"""统计 wx_export.py 导出的 jsonl：消息量、双方占比、通话时长分布。

用法：
    python wx_stats.py <file.jsonl>              # 总览
    python wx_stats.py <file.jsonl> --by month   # 按月
    python wx_stats.py <file.jsonl> --by week    # 按周（ISO 周，周一起）
    python wx_stats.py <file.jsonl> --by day     # 按天
    python wx_stats.py <file.jsonl> --calls      # 通话明细与分布
    python wx_stats.py <file.jsonl> --json       # 结构化输出
"""
import argparse
import collections
import datetime
import json
import statistics
import sys


def hm(sec):
    h, rem = divmod(int(sec), 3600)
    return f"{h}h{rem // 60:02d}m" if h else f"{rem // 60}m{sec % 60:02d}s"


def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    for r in rows:
        r['dt'] = datetime.datetime.strptime(r['time'], '%Y-%m-%d %H:%M:%S')
    rows.sort(key=lambda r: r['dt'])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jsonl')
    ap.add_argument('--by', choices=['day', 'week', 'month'], help='按天/周/月汇总')
    ap.add_argument('--calls', action='store_true', help='通话统计')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    args = ap.parse_args()

    rows = load(args.jsonl)
    if not rows:
        sys.exit('文件为空')

    people = [p for p in dict.fromkeys(r['from'] for r in rows) if p]
    cnt = collections.Counter(r['from'] for r in rows if r['from'])
    total = sum(cnt.values())
    span = (rows[-1]['dt'] - rows[0]['dt']).days + 1
    out = {
        'total_rows': len(rows),
        'messages': total,
        'span_days': span,
        'range': [rows[0]['time'], rows[-1]['time']],
        'by_sender': dict(cnt),
        'share': {k: round(v / total * 100, 1) for k, v in cnt.items()},
    }

    if args.by:
        key = {'day': lambda d: d.strftime('%Y-%m-%d'),
               'week': lambda d: (d - datetime.timedelta(days=d.weekday())).strftime('%Y-%m-%d'),
               'month': lambda d: d.strftime('%Y-%m')}[args.by]
        bucket = collections.defaultdict(lambda: collections.Counter())
        for r in rows:
            if r['from']:
                bucket[key(r['dt'])][r['from']] += 1
        out['buckets'] = {k: dict(v) for k, v in sorted(bucket.items())}

    calls = [r for r in rows if r.get('call_sec')]
    if args.calls or True:
        if calls:
            secs = [c['call_sec'] for c in calls]
            tot = sum(secs)
            out['calls'] = {
                'count': len(calls),
                'total_sec': tot,
                'total_hours': round(tot / 3600, 1),
                'median_min': round(statistics.median(secs) / 60),
                'mean_min': round(tot / len(secs) / 60),
                'longest': [
                    {'time': c['time'], 'sec': c['call_sec']}
                    for c in sorted(calls, key=lambda x: -x['call_sec'])[:10]
                ],
            }
            per_day = collections.defaultdict(int)
            for c in calls:
                start = c['dt'] - datetime.timedelta(seconds=c['call_sec'])
                per_day[start.strftime('%Y-%m-%d')] += c['call_sec']
            out['calls']['by_day'] = {k: round(v / 3600, 2) for k, v in sorted(per_day.items())}
            per_month = collections.defaultdict(int)
            for c in calls:
                start = c['dt'] - datetime.timedelta(seconds=c['call_sec'])
                per_month[start.strftime('%Y-%m')] += c['call_sec']
            out['calls']['by_month'] = {k: round(v / 3600, 1) for k, v in sorted(per_month.items())}

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"总消息 {total} 条，{out['range'][0]} ~ {out['range'][1]}（{span} 天）")
    for p in people:
        print(f"   {p:16s} {cnt[p]:7d}  {cnt[p] / total * 100:5.1f}%")

    if args.by and 'buckets' in out:
        print(f"\n按{args.by}：")
        for k, v in out['buckets'].items():
            t = sum(v.values())
            detail = '  '.join(f"{p}:{v.get(p, 0)}" for p in people)
            print(f"   {k}  {t:6d}   {detail}")

    if 'calls' in out:
        c = out['calls']
        print(f"\n通话 {c['count']} 次，累计 {c['total_hours']} 小时"
              f"（中位 {c['median_min']} 分，平均 {c['mean_min']} 分）")
        print("   最长 5 次：")
        for x in c['longest'][:5]:
            print(f"      {x['time'][:16]}  {hm(x['sec'])}")
        print("   按月：")
        for k, v in c['by_month'].items():
            print(f"      {k}  {v:6.1f} 小时")


if __name__ == '__main__':
    main()
