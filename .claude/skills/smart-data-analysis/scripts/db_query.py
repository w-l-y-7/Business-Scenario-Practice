#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径 B：大数据集/多表关联 -> 入库(sqlite) 后做 SQL 聚合、关联或原始查询。

用法:
  从 CSV/Excel 文件建内存库再查（文件按参数顺序成为表 t0、t1、…）：
    python db_query.py --source a.csv [--source b.csv] --query profile
    python db_query.py --source a.csv --source b.csv --query join --on 城市
    python db_query.py --source a.csv --query top --by 金额 --n 10
    python db_query.py --source a.csv --query custom --sql "SELECT 城市, SUM(金额) FROM t0 GROUP BY 城市"
  或对已有 sqlite 库直接查（不建表，用库内真实表名写 SQL）：
    python db_query.py --db data.db --query custom --sql "SELECT * FROM mytable LIMIT 10"
    python db_query.py --db data.db --query profile

说明：profile 对每个表给出行数/列/缺失/类别数/数值描述（主要用 SQL 聚合，内存占用低）；
join 需 >=2 个 --source 且给 --on；输出 md 落在 --outdir。
"""
import argparse
import os
import re
import sqlite3
import sys

import pandas as pd

NUMERIC = {'INTEGER', 'REAL', 'NUMERIC', 'DOUBLE', 'FLOAT', 'DECIMAL'}


def load_frame(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        for enc in ('utf-8-sig', 'utf-8', 'gbk'):
            try:
                return pd.read_csv(path, encoding=enc, chunksize=None)
            except UnicodeDecodeError:
                continue
        sys.exit('ERROR 无法解码 %s' % path)
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(path)
    sys.exit('ERROR 仅支持 .csv/.xlsx/.xls 入库，当前: %s' % path)


def _ingest_impl(conn, path, name):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        try:
            first = True
            for df in pd.read_csv(path, chunksize=200000, encoding='utf-8-sig'):
                df.to_sql(name, conn, if_exists='replace' if first else 'append', index=False)
                first = False
        except UnicodeDecodeError:
            pd.read_csv(path, encoding='gbk').to_sql(name, conn, if_exists='replace', index=False)
    else:
        df = load_frame(path)
        df.to_sql(name, conn, if_exists='replace', index=False)


def profile_tables(conn, tables):
    out = []
    for t in tables:
        cnt = conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        cols = conn.execute('PRAGMA table_info("%s")' % t).fetchall()  # (cid,name,type,notnull,dflt,pk)
        out.append('### 表 %s（行数 %d）' % (t, cnt))
        numeric = [c for c in cols if (c[2] or '').upper() in NUMERIC]
        if cols:
            out.append('| 列 | 类型 | 缺失 | 类别数 |' + (' 数值列(min/max/avg) |' if numeric else ''))
            out.append('| --- | --- | --- | --- |' + (' --- |' if numeric else ''))
            for c in cols:
                cname, ctype = c[1], c[2] or 'TEXT'
                nulls = conn.execute('SELECT COUNT(*) - COUNT("%s") FROM "%s"' % (cname, t)).fetchone()[0]
                uniq = conn.execute('SELECT COUNT(DISTINCT "%s") FROM "%s"' % (cname, t)).fetchone()[0]
                if cname in [n[1] for n in numeric]:
                    mn = conn.execute('SELECT MIN("%s"), MAX("%s"), AVG("%s") FROM "%s"' % (cname, cname, cname, t)).fetchone()
                    agg = ' %s / %s / %s' % (fmt(mn[0]), fmt(mn[1]), fmt(mn[2]))
                else:
                    agg = ''
                out.append('| %s | %s | %d | %d |%s |' % (cname, ctype, nulls, uniq, agg))
        out.append('')
    return '\n'.join(out)


def fmt(x):
    if x is None:
        return 'NA'
    if isinstance(x, float):
        return '%.4g' % x
    return str(x)


def main():
    ap = argparse.ArgumentParser(description='大数据集入库聚合/关联查询')
    ap.add_argument('--source', action='append', default=[], help='可多次：CSV/Excel 文件')
    ap.add_argument('--db', help='已有的 sqlite 库文件（与 --source 二选一）')
    ap.add_argument('--query', choices=['profile', 'join', 'top', 'custom'], required=True)
    ap.add_argument('--on', help='join 用：两表关联列名')
    ap.add_argument('--by', help='top 用：排序数值列')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--sql', help='custom 用：原始 SQL')
    ap.add_argument('--outdir', default='output')
    a = ap.parse_args()

    if a.db and a.source:
        sys.exit('ERROR --db 与 --source 二选一')
    if not a.db and not a.source:
        sys.exit('ERROR 需 --source 或 --db')

    conn = sqlite3.connect(a.db) if a.db else sqlite3.connect(':memory:')
    map_lines = []
    tables = []
    if a.source:
        for i, p in enumerate(a.source):
            if not os.path.exists(p):
                sys.exit('ERROR 找不到 %s' % p)
            t = 't%d' % i
            _ingest_impl(conn, p, t)
            tables.append(t)
            map_lines.append('- %s -> 表 %s' % (os.path.basename(p), t))
    else:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        map_lines.append('- 已用现成库：%s' % a.db)

    body = []
    sql_used = ''
    if a.query == 'profile':
        body.append(profile_tables(conn, tables))
    elif a.query == 'join':
        if len(tables) < 2 or not a.on:
            sys.exit('ERROR join 需 >=2 个 --source 且给 --on')
        l, r = tables[0], tables[1]
        inner = conn.execute('SELECT COUNT(*) FROM "%s" a JOIN "%s" b ON a."%s" = b."%s"' % (l, r, a.on, a.on)).fetchone()[0]
        left_only = conn.execute('SELECT COUNT(*) FROM "%s" a LEFT JOIN "%s" b ON a."%s" = b."%s" WHERE b."%s" IS NULL' % (l, r, a.on, a.on, a.on)).fetchone()[0]
        right_only = conn.execute('SELECT COUNT(*) FROM "%s" a LEFT JOIN "%s" b ON a."%s" = b."%s" WHERE a."%s" IS NULL' % (r, l, a.on, a.on, a.on)).fetchone()[0]
        body.append('按列 `%s` 关联 `%s`(t0 左) 与 `%s`(t1 右)：' % (a.on, os.path.basename(a.source[0]), os.path.basename(a.source[1])))
        body.append('')
        body.append('- 内连接命中行：%d' % inner)
        body.append('- 仅左表有（右缺失）：%d' % left_only)
        body.append('- 仅右表有（左缺失）：%d' % right_only)
        sql_used = 'inner/left join on %s' % a.on
    elif a.query == 'top':
        if not a.by:
            sys.exit('ERROR top 需 --by 数值列')
        sql = 'SELECT * FROM "%s" ORDER BY "%s" DESC LIMIT %d' % (tables[0], a.by, a.n)
        rows = conn.execute(sql).fetchall()
        hdr = [d[0] for d in conn.execute(sql).description]
        body.append('`%s` 按 `%s` 降序 Top%d：' % (os.path.basename(a.source[0]), a.by, a.n))
        body.append('')
        body.append(to_md(hdr, rows))
        sql_used = sql
    elif a.query == 'custom':
        if not a.sql:
            sys.exit('ERROR custom 需 --sql')
        sql_used = a.sql
        try:
            cur = conn.execute(a.sql)
        except sqlite3.Error as e:
            sys.exit('ERROR SQL 执行失败：%s\n（可用表：%s）' % (e, ', '.join(tables)))
        if cur.description:
            rows = cur.fetchmany(50)
            hdr = [d[0] for d in cur.description]
            body.append('SQL 结果（最多 50 行）：')
            body.append('')
            body.append(to_md(hdr, rows))
        else:
            body.append('执行成功，影响行数：%d' % cur.rowcount)

    stem0 = re.sub(r'[^\w一-鿿-]+', '_', os.path.splitext(os.path.basename((a.source or ['x'])[0]))[0])
    os.makedirs(a.outdir, exist_ok=True)
    md = ['# 数据查询结果 · %s' % a.query, '', '表映射：'] + map_lines + ['', '使用的 SQL/逻辑：`%s`' % sql_used, '', body[0] if body else '']
    if len(body) > 1:
        md += body[1:]
    md_path = os.path.join(a.outdir, 'db_%s_%s.md' % (a.query, stem0))
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print('\n'.join(map_lines))
    print('SQL/逻辑：%s' % sql_used)
    print('OK -> %s' % md_path)
    for line in body:
        print(line[:1200].replace('\n', ' | ')[:1200])
    return 0


def to_md(hdr, rows):
    lines = ['| ' + ' | '.join(str(h) for h in hdr) + ' |']
    lines.append('| ' + ' | '.join(['---'] * len(hdr)) + ' |')
    for r in rows:
        lines.append('| ' + ' | '.join(fmt(v) for v in r) + ' |')
    return '\n'.join(lines)


if __name__ == '__main__':
    sys.exit(main())
