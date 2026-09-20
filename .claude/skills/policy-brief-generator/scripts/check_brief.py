#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政策简报草稿的机械项检查脚本（只查可程序化判定的项，不判数据真伪）。

用法:
  python check_brief.py --input PATH [--min 1500] [--max 2500]

检查项:
  1. 结构: 恰一个 `#` 一级标题; 正文只用二级标题(无 `###` 及以上);
     四个板块 `## 摘要/背景/分析/建议` 依序且各出现一次、内容非空;
     存在附录 `## 数据与引文溯源清单`(或 `## 溯源清单`)。
  2. 篇幅: 四个板块正文(不含溯源清单)总字数在 [min, max] 内。
     计字规则: 中文/CJK 与全角标点每个计 1, 连续 ASCII 字母数字串每条计 1, 空白与其余符号不计。
  3. 引用标注: 含数字+量词(如 20%、3亿元、5 倍、2 个百分点)的数据句应就近带 `〔#ID〕`;
     每个文中标记都必须在溯源清单里有对应行; 不留模板占位({{ / TODO)。
  4. 术语统一(可选): --terms '规范名=异体1,异体2' 若正文出现异体写法则报错。

返回码: 0=全部通过; 1=有未通过项; 2=参数/文件错误。
"""
import argparse
import re
import sys

CJK_CHAR = re.compile(r'[　-〿一-鿿＀-￯]')
ASCII_RUN = re.compile(r'[A-Za-z0-9]+')
HEADING = re.compile(r'^(#{1,6})[ \t]+(.*)$')
INLINE_MARK = re.compile(r'〔#([A-Za-z0-9\-]+)〕')
UNIT_TERMS = ['个百分点', '亿元', '万元', '万人次', 'bp', '倍', '%', '公里', '万吨']
UNIT_PAT = re.compile(r'\d[\d,\.]*\s*(?:' + '|'.join(re.escape(u) for u in sorted(UNIT_TERMS, key=len, reverse=True)) + r')')
ROW_MARK = re.compile(r'^\s*\|?\s*#([A-Za-z0-9\-]+)\s*\|')
PLACEHOLDER = re.compile(r'\{\{|TODO|〔待填|待插入')

CORE = ['摘要', '背景', '分析', '建议']
APPENDIX = ['数据与引文溯源清单', '溯源清单']


def normalize(h):
    return re.sub(r'[\W_]+', '', h)


def count_words(text):
    n = len(CJK_CHAR.findall(text))
    n += len(ASCII_RUN.findall(text))
    return n


def parse_blocks(lines):
    """返回 (结构列表, 标题后的正文区间)。"""
    blocks = []          # (level, canonical, raw, start_line)
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if m:
            blocks.append((len(m.group(1)), normalize(m.group(2).strip()), line.strip(), i))
    return blocks


def issues_from_file(path, lo, hi, terms):
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    lines = raw.splitlines()
    blocks = parse_blocks(lines)

    issues = []

    h1 = [b for b in blocks if b[0] == 1]
    if len(h1) != 1:
        issues.append('FAIL 结构: 全篇应有且只有 1 个一级标题 `#`，实际 %d 个' % len(h1))
    deep = [b for b in blocks if b[0] >= 3]
    if deep:
        issues.append('FAIL 结构: 出现 %d 处三级及以上标题（%s），简报正文只用两级 `##`' % (len(deep), deep[0][2]))

    canon = {}
    for b in blocks:
        if b[0] == 2:
            canon[b[1]] = b  # last wins on duplicate
    seen = []
    for key in CORE:
        if key in canon:
            seen.append(key)
        else:
            issues.append('FAIL 结构: 缺少板块 `## %s`' % key)
    if seen != CORE:
        issues.append('FAIL 结构: 四个板块未依序出现 摘要→背景→分析→建议（实际顺序: %s）' % (' → '.join(seen) or '空'))

    app = next((b for b in blocks if b[0] == 2 and b[1] in APPENDIX), None)
    if app is None:
        issues.append('FAIL 结构: 缺少附录 `## 数据与引文溯源清单`')

    # 各板块正文区间(非空判断 + 篇幅统计, 不含溯源清单)
    core_texts = {}
    for idx, b in enumerate(blocks):
        if b[0] != 2 or b[1] not in CORE:
            continue
        start = b[3] + 1
        end = next((x[3] for x in blocks[idx + 1:]), len(lines))
        body = '\n'.join(lines[start:end])
        core_texts[b[1]] = body
        if len(body.strip()) == 0:
            issues.append('FAIL 结构: 板块 `## %s` 内容为空' % b[1])

    core_total = sum(count_words(t) for t in core_texts.values())
    if not (lo <= core_total <= hi):
        issues.append('FAIL 篇幅: 正文(不含溯源清单) %d 字，超出允许范围 %d–%d' % (core_total, lo, hi))

    # 溯源清单行 ID
    row_ids = []
    appendix_ids_inline = {}
    if app is not None:
        for j in range(app[3] + 1, len(lines)):
            line = lines[j]
            m = ROW_MARK.match(line)
            if m and 'ID' != m.group(1).upper() and '出处' not in line:
                row_ids.append(m.group(1))

    # 引用标注: 数据句须带标记(跳过标题行与表格行)
    data_sent_missing = []
    for i, line in enumerate(lines):
        if HEADING.match(line) or line.lstrip().startswith('|'):
            continue
        if UNIT_PAT.search(line) and not INLINE_MARK.search(line):
            data_sent_missing.append((i + 1, line.strip()[:60]))
    if data_sent_missing:
        sample = '；'.join('第%d行: %s' % (n, s) for n, s in data_sent_missing[:3])
        issues.append('FAIL 引用: %d 处含数据量词但缺 `〔#ID〕` 标记（%s）' % (len(data_sent_missing), sample))

    used_ids = set()
    for m in INLINE_MARK.finditer(raw):
        used_ids.add(m.group(1))
    missing_row = sorted(used_ids - set(row_ids))
    if missing_row:
        issues.append('FAIL 引用: 文中标记 %s 在溯源清单中没有对应行' % missing_row)
    orphan_rows = sorted(set(row_ids) - used_ids)
    if orphan_rows:
        issues.append('WARN 引用: 溯源清单中 %s 行未被正文引用' % orphan_rows)

    if PLACEHOLDER.search(raw):
        issues.append('FAIL 格式: 草稿仍留有模板占位符({{ / TODO / 〔待填 等)，须全部替换成实际内容')

    if terms:
        for spec in terms:
            if '=' not in spec:
                continue
            canon_t, alts = spec.split('=', 1)
            for alt in alts.split(','):
                alt = alt.strip()
                if not alt:
                    continue
                if re.search(re.escape(alt), raw):
                    issues.append('FAIL 术语: 出现异体写法「%s」，应统一为「%s」' % (alt, canon_t))

    return issues, core_total, len(used_ids), len(row_ids)


def main():
    ap = argparse.ArgumentParser(description='政策简报机械项检查')
    ap.add_argument('--input', required=True, help='草稿 md 路径')
    ap.add_argument('--min', type=int, default=1500)
    ap.add_argument('--max', type=int, default=2500)
    ap.add_argument('--terms', nargs='*', default=[], help="术语统一: '规范名=异体1,异体2'")
    a = ap.parse_args()

    try:
        issues, total, used, rows = issues_from_file(a.input, a.min, a.max, a.terms)
    except FileNotFoundError:
        print('ERROR: 找不到文件 %s' % a.input)
        return 2
    except UnicodeDecodeError:
        print('ERROR: %s 不是 UTF-8 文本，无法解析' % a.input)
        return 2

    print('检查 %s' % a.input)
    print('  正文字数(不含溯源清单): %d (允许 %d–%d)' % (total, a.min, a.max))
    print('  文中标记 %d 个 / 溯源清单行 %d 条' % (used, rows))
    for it in issues:
        print('  ' + it)
    if issues:
        print('结论: 未通过（%d 项），需精修' % len(issues))
        return 1
    print('结论: 全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
